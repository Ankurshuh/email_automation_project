import logging
from datetime import datetime

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app import models
from app.database import SessionLocal
from app.email_service import EmailSendError, send_email

logger = logging.getLogger("automation.scheduler")

scheduler = BackgroundScheduler()


# ---------------------------------------------------------------------------
# Scheduled emails
# ---------------------------------------------------------------------------

def _run_scheduled_email(email_id: int):
    db = SessionLocal()
    try:
        email = db.query(models.ScheduledEmail).filter(models.ScheduledEmail.id == email_id).first()
        if not email or not email.is_active:
            return

        status, error = "sent", None
        try:
            send_email(
                subject=email.subject,
                body=email.body,
                recipients=email.recipients,
                is_html=email.is_html,
                cc=email.cc,
            )
        except EmailSendError as exc:
            status, error = "failed", str(exc)

        email.last_run_at = datetime.utcnow()
        email.next_run_at = get_next_run_time(email.job_id)

        # One-time jobs deactivate themselves after firing
        if email.schedule_type == models.ScheduleType.ONCE.value:
            email.is_active = False

        db.add(models.EmailLog(
            scheduled_email_id=email.id,
            subject=email.subject,
            recipients=email.recipients,
            status=status,
            error_message=error,
        ))
        db.commit()
    finally:
        db.close()


def schedule_email_job(email: models.ScheduledEmail) -> str:
    job_id = f"email_{email.id}"

    if email.schedule_type == models.ScheduleType.ONCE.value:
        trigger = DateTrigger(run_date=email.run_date)
    elif email.schedule_type == models.ScheduleType.INTERVAL.value:
        trigger = IntervalTrigger(seconds=email.interval_seconds)
    elif email.schedule_type == models.ScheduleType.CRON.value:
        trigger = CronTrigger.from_crontab(email.cron_expression)
    else:
        raise ValueError(f"Unknown schedule_type: {email.schedule_type}")

    scheduler.add_job(
        _run_scheduled_email,
        trigger=trigger,
        args=[email.id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )
    return job_id


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def _evaluate_alert(alert: models.Alert):
    """Runs the actual check for an alert. Returns (triggered: bool, message: str)."""
    try:
        start = datetime.utcnow()
        resp = httpx.get(alert.target_url, timeout=15, follow_redirects=True)
        elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000
    except Exception as exc:  # noqa: BLE001 - any network failure counts as a trigger
        return True, f"Check failed for {alert.target_url}: {exc}"

    if alert.alert_type == models.AlertType.WEBHOOK_STATUS.value:
        expected = alert.expected_status or 200
        if resp.status_code != expected:
            return True, f"{alert.target_url} returned status {resp.status_code}, expected {expected}."
        return False, f"{alert.target_url} OK ({resp.status_code})"

    if alert.alert_type == models.AlertType.KEYWORD_PRESENT.value:
        if alert.keyword and alert.keyword in resp.text:
            return True, f"Keyword '{alert.keyword}' found on {alert.target_url}."
        return False, f"Keyword '{alert.keyword}' not present on {alert.target_url}."

    if alert.alert_type == models.AlertType.KEYWORD_MISSING.value:
        if alert.keyword and alert.keyword not in resp.text:
            return True, f"Keyword '{alert.keyword}' missing from {alert.target_url}."
        return False, f"Keyword '{alert.keyword}' present on {alert.target_url}."

    if alert.alert_type == models.AlertType.RESPONSE_TIME.value:
        threshold = alert.threshold_ms or 1000
        if elapsed_ms > threshold:
            return True, (
                f"{alert.target_url} responded in {elapsed_ms:.0f}ms, "
                f"exceeding threshold of {threshold:.0f}ms."
            )
        return False, f"{alert.target_url} responded in {elapsed_ms:.0f}ms."

    return False, "Unknown alert type."


def _run_alert_check(alert_id: int):
    db = SessionLocal()
    try:
        alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
        if not alert or not alert.is_active:
            return

        triggered, message = _evaluate_alert(alert)
        alert.last_checked_at = datetime.utcnow()
        alert.last_status = "triggered" if triggered else "ok"

        notified = False
        if triggered:
            cooldown_ok = (
                alert.last_triggered_at is None
                or (datetime.utcnow() - alert.last_triggered_at).total_seconds() >= alert.cooldown_seconds
            )
            if cooldown_ok:
                try:
                    send_email(
                        subject=f"[ALERT] {alert.name}",
                        body=message,
                        recipients=alert.recipients,
                    )
                    notified = True
                    alert.last_triggered_at = datetime.utcnow()
                except EmailSendError as exc:
                    message += f" (notification failed: {exc})"

        db.add(models.AlertLog(
            alert_id=alert.id,
            triggered=triggered,
            message=message,
            notified=notified,
        ))
        db.commit()
    finally:
        db.close()


def schedule_alert_job(alert: models.Alert) -> str:
    job_id = f"alert_{alert.id}"
    scheduler.add_job(
        _run_alert_check,
        trigger=IntervalTrigger(seconds=alert.check_interval_seconds),
        args=[alert.id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=60,
    )
    return job_id


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def unschedule_job(job_id: str):
    if job_id and scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def get_next_run_time(job_id: str):
    job = scheduler.get_job(job_id) if job_id else None
    if job and job.next_run_time:
        return job.next_run_time.replace(tzinfo=None)
    return None


def start_scheduler():
    if not scheduler.running:
        scheduler.start()


def load_jobs_from_db():
    """Re-register all active emails/alerts as jobs on application startup."""
    db = SessionLocal()
    try:
        active_emails = db.query(models.ScheduledEmail).filter(
            models.ScheduledEmail.is_active == True  # noqa: E712
        ).all()
        for email in active_emails:
            if (
                email.schedule_type == models.ScheduleType.ONCE.value
                and email.run_date
                and email.run_date < datetime.utcnow()
            ):
                continue  # don't resurrect a missed one-time send
            try:
                job_id = schedule_email_job(email)
                email.job_id = job_id
                email.next_run_at = get_next_run_time(job_id)
            except Exception:
                logger.exception("Failed to schedule email id=%s", email.id)

        active_alerts = db.query(models.Alert).filter(
            models.Alert.is_active == True  # noqa: E712
        ).all()
        for alert in active_alerts:
            try:
                alert.job_id = schedule_alert_job(alert)
            except Exception:
                logger.exception("Failed to schedule alert id=%s", alert.id)

        db.commit()
    finally:
        db.close()
