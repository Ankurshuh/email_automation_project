"""
Streamlit dashboard for the Email Automation & Alerts Platform.

Talks to the FastAPI backend (app/main.py) over HTTP — run that separately:
    uvicorn app.main:app --reload

Then run this dashboard:
    streamlit run streamlit_app.py
"""

from datetime import datetime, date, time as dtime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Email Automation & Alerts", page_icon="📬", layout="wide")

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = "http://127.0.0.1:8000"


def api_url(path: str) -> str:
    return st.session_state.api_base_url.rstrip("/") + path


def api_get(path: str, **kwargs):
    try:
        resp = requests.get(api_url(path), timeout=10, **kwargs)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"Can't reach the API at {st.session_state.api_base_url}. Is the FastAPI server running?"
    except requests.exceptions.HTTPError as exc:
        return None, _extract_error(exc.response)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def api_post(path: str, json_body: dict):
    try:
        resp = requests.post(api_url(path), json=json_body, timeout=10)
        resp.raise_for_status()
        return resp.json() if resp.content else {}, None
    except requests.exceptions.ConnectionError:
        return None, f"Can't reach the API at {st.session_state.api_base_url}. Is the FastAPI server running?"
    except requests.exceptions.HTTPError as exc:
        return None, _extract_error(exc.response)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def api_patch(path: str, json_body: dict):
    try:
        resp = requests.patch(api_url(path), json=json_body, timeout=10)
        resp.raise_for_status()
        return resp.json() if resp.content else {}, None
    except requests.exceptions.ConnectionError:
        return None, f"Can't reach the API at {st.session_state.api_base_url}. Is the FastAPI server running?"
    except requests.exceptions.HTTPError as exc:
        return None, _extract_error(exc.response)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def api_delete(path: str):
    try:
        resp = requests.delete(api_url(path), timeout=10)
        resp.raise_for_status()
        return True, None
    except requests.exceptions.ConnectionError:
        return False, f"Can't reach the API at {st.session_state.api_base_url}. Is the FastAPI server running?"
    except requests.exceptions.HTTPError as exc:
        return False, _extract_error(exc.response)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _extract_error(response) -> str:
    try:
        detail = response.json().get("detail")
        return str(detail) if detail else f"HTTP {response.status_code}"
    except Exception:  # noqa: BLE001
        return f"HTTP {response.status_code}"


def split_emails(raw: str):
    return [e.strip() for e in raw.split(",") if e.strip()]


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📬 Automation Platform")
    st.session_state.api_base_url = st.text_input("API base URL", st.session_state.api_base_url)

    health, health_err = api_get("/health")
    if health_err:
        st.error("⚠️ Backend unreachable")
    else:
        st.success(f"✅ Backend healthy · scheduler running: {health.get('scheduler_running')}")

    st.divider()
    page = st.radio(
        "Navigate",
        ["📧 Scheduled Emails", "➕ New Email", "🚨 Alerts", "➕ New Alert"],
    )

# ---------------------------------------------------------------------------
# Page: Scheduled Emails list
# ---------------------------------------------------------------------------

if page == "📧 Scheduled Emails":
    st.header("Scheduled Emails")

    emails, err = api_get("/emails/")
    if err:
        st.error(err)
    elif not emails:
        st.info("No scheduled emails yet. Create one from the sidebar.")
    else:
        for email in emails:
            status = "🟢 active" if email["is_active"] else "⏸️ paused"
            with st.expander(f"{email['name']} — {status} — {email['schedule_type']}"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Subject:** {email['subject']}")
                    st.write(f"**Recipients:** {', '.join(email['recipients'])}")
                    if email.get("cc"):
                        st.write(f"**CC:** {', '.join(email['cc'])}")
                    st.write(f"**Body:**")
                    if email["is_html"]:
                        st.code(email["body"], language="html")
                    else:
                        st.text(email["body"])

                    if email["schedule_type"] == "once":
                        st.write(f"**Run date:** {email.get('run_date') or '—'}")
                    elif email["schedule_type"] == "interval":
                        st.write(f"**Every:** {email.get('interval_seconds')} seconds")
                    elif email["schedule_type"] == "cron":
                        st.write(f"**Cron:** `{email.get('cron_expression')}`")

                    st.write(f"**Next run:** {email.get('next_run_at') or '—'}")
                    st.write(f"**Last run:** {email.get('last_run_at') or 'never'}")

                with col2:
                    eid = email["id"]
                    if email["is_active"]:
                        if st.button("Pause", key=f"pause_{eid}"):
                            _, e = api_post(f"/emails/{eid}/pause", {})
                            if e:
                                st.error(e)
                            else:
                                st.rerun()
                    else:
                        if st.button("Resume", key=f"resume_{eid}"):
                            _, e = api_post(f"/emails/{eid}/resume", {})
                            if e:
                                st.error(e)
                            else:
                                st.rerun()

                    if st.button("Delete", key=f"delete_{eid}", type="secondary"):
                        ok, e = api_delete(f"/emails/{eid}")
                        if e:
                            st.error(e)
                        else:
                            st.rerun()

                logs, log_err = api_get(f"/emails/{email['id']}/logs")
                if not log_err and logs:
                    st.write("**Send history:**")
                    df = pd.DataFrame(logs)[["sent_at", "status", "error_message"]]
                    st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Page: New Email
# ---------------------------------------------------------------------------

elif page == "➕ New Email":
    st.header("Schedule a New Email")

    with st.form("new_email_form"):
        name = st.text_input("Internal name", placeholder="Weekly status report")
        subject = st.text_input("Subject", placeholder="Weekly Status")
        body = st.text_area("Body", height=150, placeholder="Here is your weekly status...")
        is_html = st.checkbox("Body is HTML")
        recipients_raw = st.text_input("Recipients (comma-separated)", placeholder="team@example.com, lead@example.com")
        cc_raw = st.text_input("CC (comma-separated, optional)")

        schedule_type = st.selectbox("Schedule type", ["once", "interval", "cron"])

        run_date, interval_seconds, cron_expression = None, None, None
        if schedule_type == "once":
            c1, c2 = st.columns(2)
            run_date_val = c1.date_input("Run date", value=date.today())
            run_time_val = c2.time_input("Run time", value=dtime(9, 0))
            run_date = datetime.combine(run_date_val, run_time_val).isoformat()
        elif schedule_type == "interval":
            interval_seconds = st.number_input("Interval (seconds)", min_value=1, value=3600, step=60)
        elif schedule_type == "cron":
            cron_expression = st.text_input(
                "Cron expression (5-field crontab syntax)",
                value="0 9 * * 1",
                help="minute hour day-of-month month day-of-week — e.g. '0 9 * * 1' = every Monday at 9am",
            )

        submitted = st.form_submit_button("Create scheduled email", type="primary")

        if submitted:
            payload = {
                "name": name,
                "subject": subject,
                "body": body,
                "is_html": is_html,
                "recipients": split_emails(recipients_raw),
                "cc": split_emails(cc_raw) or None,
                "schedule_type": schedule_type,
                "run_date": run_date,
                "interval_seconds": int(interval_seconds) if interval_seconds else None,
                "cron_expression": cron_expression,
            }
            if not name or not subject or not body or not payload["recipients"]:
                st.error("Name, subject, body, and at least one recipient are required.")
            else:
                result, err = api_post("/emails/", payload)
                if err:
                    st.error(err)
                else:
                    st.success(f"Created '{result['name']}' — next run: {result.get('next_run_at') or 'pending'}")

# ---------------------------------------------------------------------------
# Page: Alerts list
# ---------------------------------------------------------------------------

elif page == "🚨 Alerts":
    st.header("Alerts")

    alerts, err = api_get("/alerts/")
    if err:
        st.error(err)
    elif not alerts:
        st.info("No alerts yet. Create one from the sidebar.")
    else:
        for alert in alerts:
            status_icon = {"ok": "🟢", "triggered": "🔴"}.get(alert.get("last_status"), "⚪")
            active = "active" if alert["is_active"] else "paused"
            with st.expander(f"{status_icon} {alert['name']} — {alert['alert_type']} — {active}"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Target:** {alert['target_url']}")
                    st.write(f"**Checks every:** {alert['check_interval_seconds']} seconds")
                    st.write(f"**Cooldown between alerts:** {alert['cooldown_seconds']} seconds")
                    st.write(f"**Recipients:** {', '.join(alert['recipients'])}")

                    if alert["alert_type"] == "webhook_status":
                        st.write(f"**Expected status:** {alert.get('expected_status')}")
                    elif alert["alert_type"] in ("keyword_present", "keyword_missing"):
                        st.write(f"**Keyword:** {alert.get('keyword')}")
                    elif alert["alert_type"] == "response_time":
                        st.write(f"**Threshold:** {alert.get('threshold_ms')} ms")

                    st.write(f"**Last checked:** {alert.get('last_checked_at') or 'never'}")
                    st.write(f"**Last triggered:** {alert.get('last_triggered_at') or 'never'}")

                with col2:
                    aid = alert["id"]
                    if st.button("Run check now", key=f"test_{aid}"):
                        _, e = api_post(f"/alerts/{aid}/test", {})
                        if e:
                            st.error(e)
                        else:
                            st.success("Check executed")
                            st.rerun()

                    if st.button("Delete", key=f"delalert_{aid}", type="secondary"):
                        ok, e = api_delete(f"/alerts/{aid}")
                        if e:
                            st.error(e)
                        else:
                            st.rerun()

                logs, log_err = api_get(f"/alerts/{alert['id']}/logs")
                if not log_err and logs:
                    st.write("**Check history:**")
                    df = pd.DataFrame(logs)[["checked_at", "triggered", "notified", "message"]]
                    st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Page: New Alert
# ---------------------------------------------------------------------------

elif page == "➕ New Alert":
    st.header("Create a New Alert")

    with st.form("new_alert_form"):
        name = st.text_input("Alert name", placeholder="Production homepage uptime")
        target_url = st.text_input("Target URL", placeholder="https://your-site.com")
        alert_type = st.selectbox(
            "Alert type",
            ["webhook_status", "keyword_present", "keyword_missing", "response_time"],
            format_func=lambda v: {
                "webhook_status": "HTTP status check",
                "keyword_present": "Keyword must be present",
                "keyword_missing": "Keyword must be missing",
                "response_time": "Response time threshold",
            }[v],
        )

        expected_status, keyword, threshold_ms = None, None, None
        if alert_type == "webhook_status":
            expected_status = st.number_input("Expected status code", min_value=100, max_value=599, value=200)
        elif alert_type in ("keyword_present", "keyword_missing"):
            keyword = st.text_input("Keyword to check for")
        elif alert_type == "response_time":
            threshold_ms = st.number_input("Threshold (milliseconds)", min_value=1.0, value=1000.0)

        check_interval_seconds = st.number_input("Check every (seconds)", min_value=10, value=300, step=10)
        cooldown_seconds = st.number_input("Cooldown between alert emails (seconds)", min_value=0, value=1800, step=60)
        recipients_raw = st.text_input("Recipients (comma-separated)", placeholder="oncall@example.com")

        submitted = st.form_submit_button("Create alert", type="primary")

        if submitted:
            payload = {
                "name": name,
                "alert_type": alert_type,
                "target_url": target_url,
                "check_interval_seconds": int(check_interval_seconds),
                "expected_status": int(expected_status) if expected_status else None,
                "keyword": keyword,
                "threshold_ms": float(threshold_ms) if threshold_ms else None,
                "recipients": split_emails(recipients_raw),
                "cooldown_seconds": int(cooldown_seconds),
            }
            if not name or not target_url or not payload["recipients"]:
                st.error("Name, target URL, and at least one recipient are required.")
            else:
                result, err = api_post("/alerts/", payload)
                if err:
                    st.error(err)
                else:
                    st.success(f"Created alert '{result['name']}'")
