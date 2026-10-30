import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


class ScheduleType(str, enum.Enum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


class AlertType(str, enum.Enum):
    WEBHOOK_STATUS = "webhook_status"
    KEYWORD_PRESENT = "keyword_present"
    KEYWORD_MISSING = "keyword_missing"
    RESPONSE_TIME = "response_time"


class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    is_html = Column(Boolean, default=False)
    recipients = Column(JSON, nullable=False)   # list[str]
    cc = Column(JSON, nullable=True)             # list[str] | None

    schedule_type = Column(String(20), nullable=False)
    run_date = Column(DateTime, nullable=True)           # ONCE
    interval_seconds = Column(Integer, nullable=True)    # INTERVAL
    cron_expression = Column(String(100), nullable=True)  # CRON

    is_active = Column(Boolean, default=True)
    job_id = Column(String(100), nullable=True, unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    logs = relationship("EmailLog", back_populates="scheduled_email", cascade="all, delete-orphan")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    scheduled_email_id = Column(Integer, ForeignKey("scheduled_emails.id"), nullable=True)
    subject = Column(String(500))
    recipients = Column(JSON)
    status = Column(String(20))          # sent | failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)

    scheduled_email = relationship("ScheduledEmail", back_populates="logs")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    alert_type = Column(String(30), nullable=False)
    target_url = Column(String(1000), nullable=False)
    check_interval_seconds = Column(Integer, default=300)

    expected_status = Column(Integer, nullable=True, default=200)
    keyword = Column(String(500), nullable=True)
    threshold_ms = Column(Float, nullable=True)

    recipients = Column(JSON, nullable=False)
    cooldown_seconds = Column(Integer, default=1800)

    is_active = Column(Boolean, default=True)
    job_id = Column(String(100), nullable=True, unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)
    last_triggered_at = Column(DateTime, nullable=True)
    last_status = Column(String(20), nullable=True)   # ok | triggered | error

    logs = relationship("AlertLog", back_populates="alert", cascade="all, delete-orphan")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"))
    triggered = Column(Boolean, default=False)
    message = Column(Text)
    notified = Column(Boolean, default=False)
    checked_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", back_populates="logs")
