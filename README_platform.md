# Email Automation & Alerts Platform

A FastAPI backend for:

1. **Scheduled emails** — send once at a specific time, on a recurring interval, or on a cron schedule.
2. **Alerts** — periodically check a URL (status code, keyword present/missing, response time) and email you when something's wrong, with a cooldown so you don't get spammed.

Jobs run in-process via [APScheduler](https://apscheduler.readthedocs.io/) and are re-registered automatically on every startup, so restarting the app doesn't lose your schedules — they're stored in SQLite (or any SQLAlchemy-supported database).

## 1. Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env with your real SMTP credentials
```

For Gmail: enable 2FA on the account, then create an **App Password** at
https://myaccount.google.com/apppasswords and use that as `SMTP_PASSWORD` (not your normal login password).

## 2. Run

```bash
uvicorn app.main:app --reload
```

Interactive API docs (try every endpoint from the browser): **http://127.0.0.1:8000/docs**

## 2b. Optional: Streamlit dashboard

A point-and-click UI (`streamlit_app.py`) is included for managing scheduled emails and alerts without touching the API directly. It's a separate process that talks to the FastAPI backend over HTTP, so keep the backend running and start it in another terminal:

```bash
pip install -r requirements-ui.txt
streamlit run streamlit_app.py
```

Opens at **http://127.0.0.1:8501**. Use the sidebar to point it at a different API URL if the backend isn't on `127.0.0.1:8000` (e.g. a deployed instance). Pages: view/pause/resume/delete scheduled emails with send history, a form to create new ones, and the same for alerts (plus a "run check now" button and per-alert check history).

## 3. Core concepts

### Scheduled emails (`/emails`)

| `schedule_type` | Required field | Behavior |
|---|---|---|
| `once` | `run_date` (ISO datetime) | Sends once, then deactivates itself |
| `interval` | `interval_seconds` | Repeats forever every N seconds |
| `cron` | `cron_expression` (5-field crontab syntax) | Repeats on a cron schedule |

Example — send a report every Monday at 9am:

```bash
curl -X POST http://127.0.0.1:8000/emails/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly status report",
    "subject": "Weekly Status",
    "body": "<h1>Status</h1><p>All green.</p>",
    "is_html": true,
    "recipients": ["team@example.com"],
    "schedule_type": "cron",
    "cron_expression": "0 9 * * 1"
  }'
```

Other endpoints: `GET /emails/`, `GET /emails/{id}`, `PATCH /emails/{id}`, `DELETE /emails/{id}`,
`POST /emails/{id}/pause`, `POST /emails/{id}/resume`, `GET /emails/{id}/logs`.

### Alerts (`/alerts`)

| `alert_type` | Extra required field | Triggers when |
|---|---|---|
| `webhook_status` | `expected_status` (default 200) | Response status code ≠ expected |
| `keyword_present` | `keyword` | Keyword found in the response body |
| `keyword_missing` | `keyword` | Keyword absent from the response body |
| `response_time` | `threshold_ms` | Response takes longer than the threshold |

Example — alert if a site goes down, checked every minute, at most one email per 30 minutes:

```bash
curl -X POST http://127.0.0.1:8000/alerts/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production homepage",
    "alert_type": "webhook_status",
    "target_url": "https://your-site.com",
    "expected_status": 200,
    "check_interval_seconds": 60,
    "cooldown_seconds": 1800,
    "recipients": ["oncall@example.com"]
  }'
```

Other endpoints: `GET /alerts/`, `GET /alerts/{id}`, `PATCH /alerts/{id}`, `DELETE /alerts/{id}`,
`POST /alerts/{id}/test` (run the check immediately), `GET /alerts/{id}/logs`.

## 4. Project structure

```
streamlit_app.py        Optional dashboard UI (talks to the API over HTTP)
requirements-ui.txt      streamlit, requests, pandas
app/
├── main.py            FastAPI app, startup/shutdown lifecycle
├── config.py           Settings loaded from .env
├── database.py          SQLAlchemy engine/session
├── models.py             ScheduledEmail, EmailLog, Alert, AlertLog
├── schemas.py             Pydantic request/response models
├── email_service.py        SMTP sending
├── scheduler.py             APScheduler jobs for emails + alert checks
└── routers/
    ├── emails.py           /emails endpoints
    └── alerts.py            /alerts endpoints
```

## 5. Notes on scaling this up

- **Multiple processes / workers**: this setup runs the scheduler in-process, so it assumes a single worker. Running `uvicorn` with `--workers > 1` (or multiple containers) would register and fire each job multiple times. For production with multiple instances, swap `BackgroundScheduler` for APScheduler's `SQLAlchemyJobStore` pointed at a shared database plus a distributed lock, or move to a dedicated task queue (Celery + Redis/RabbitMQ, or `arq`).
- **Retries**: failed sends are logged (`status: failed`, with `error_message`) but not automatically retried. Add a retry policy in `email_service.py` or re-queue failed jobs if that matters for your use case.
- **Templating**: email bodies are sent as-is. For templated content, render with Jinja2 before passing `body` into the API, or add a `template_id` field.
- **Auth**: there's no authentication on the API yet — add it (API key header, OAuth, etc.) before exposing this beyond localhost.
