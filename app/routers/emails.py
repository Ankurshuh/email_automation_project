from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.scheduler import get_next_run_time, schedule_email_job, unschedule_job

router = APIRouter(prefix="/emails", tags=["Scheduled Emails"])


@router.post("/", response_model=schemas.ScheduledEmailOut, status_code=201)
def create_scheduled_email(payload: schemas.ScheduledEmailCreate, db: Session = Depends(get_db)):
    _validate_schedule_fields(payload)

    email = models.ScheduledEmail(
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
        is_html=payload.is_html,
        recipients=payload.recipients,
        cc=payload.cc,
        schedule_type=payload.schedule_type,
        run_date=payload.run_date,
        interval_seconds=payload.interval_seconds,
        cron_expression=payload.cron_expression,
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    email.job_id = schedule_email_job(email)
    email.next_run_at = get_next_run_time(email.job_id)
    db.commit()
    db.refresh(email)
    return email


@router.get("/", response_model=List[schemas.ScheduledEmailOut])
def list_scheduled_emails(db: Session = Depends(get_db)):
    return db.query(models.ScheduledEmail).order_by(models.ScheduledEmail.id.desc()).all()


@router.get("/{email_id}", response_model=schemas.ScheduledEmailOut)
def get_scheduled_email(email_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, email_id)


@router.patch("/{email_id}", response_model=schemas.ScheduledEmailOut)
def update_scheduled_email(email_id: int, payload: schemas.ScheduledEmailUpdate, db: Session = Depends(get_db)):
    email = _get_or_404(db, email_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(email, field, value)
    db.commit()
    db.refresh(email)

    if email.is_active:
        email.job_id = schedule_email_job(email)
        email.next_run_at = get_next_run_time(email.job_id)
    else:
        unschedule_job(email.job_id)
        email.next_run_at = None
    db.commit()
    db.refresh(email)
    return email


@router.delete("/{email_id}", status_code=204)
def delete_scheduled_email(email_id: int, db: Session = Depends(get_db)):
    email = _get_or_404(db, email_id)
    unschedule_job(email.job_id)
    db.delete(email)
    db.commit()


@router.post("/{email_id}/pause", response_model=schemas.ScheduledEmailOut)
def pause_scheduled_email(email_id: int, db: Session = Depends(get_db)):
    email = _get_or_404(db, email_id)
    email.is_active = False
    unschedule_job(email.job_id)
    email.next_run_at = None
    db.commit()
    db.refresh(email)
    return email


@router.post("/{email_id}/resume", response_model=schemas.ScheduledEmailOut)
def resume_scheduled_email(email_id: int, db: Session = Depends(get_db)):
    email = _get_or_404(db, email_id)
    email.is_active = True
    email.job_id = schedule_email_job(email)
    email.next_run_at = get_next_run_time(email.job_id)
    db.commit()
    db.refresh(email)
    return email


@router.get("/{email_id}/logs", response_model=List[schemas.EmailLogOut])
def get_email_logs(email_id: int, db: Session = Depends(get_db)):
    _get_or_404(db, email_id)
    return (
        db.query(models.EmailLog)
        .filter(models.EmailLog.scheduled_email_id == email_id)
        .order_by(models.EmailLog.id.desc())
        .all()
    )


def _get_or_404(db: Session, email_id: int) -> models.ScheduledEmail:
    email = db.query(models.ScheduledEmail).filter(models.ScheduledEmail.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Scheduled email not found")
    return email


def _validate_schedule_fields(payload: schemas.ScheduledEmailCreate):
    if payload.schedule_type == "once":
        if not payload.run_date:
            raise HTTPException(400, "run_date is required for schedule_type=once")
        if payload.run_date < datetime.utcnow():
            raise HTTPException(400, "run_date must be in the future")
    if payload.schedule_type == "interval" and not payload.interval_seconds:
        raise HTTPException(400, "interval_seconds is required for schedule_type=interval")
    if payload.schedule_type == "cron" and not payload.cron_expression:
        raise HTTPException(400, "cron_expression is required for schedule_type=cron")
