from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


# ---------- Scheduled Emails ----------

class ScheduledEmailBase(BaseModel):
    name: str
    subject: str
    body: str
    is_html: bool = False
    recipients: List[EmailStr]
    cc: Optional[List[EmailStr]] = None
    schedule_type: str  # once | interval | cron
    run_date: Optional[datetime] = None
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v):
        if v not in ("once", "interval", "cron"):
            raise ValueError("schedule_type must be one of: once, interval, cron")
        return v


class ScheduledEmailCreate(ScheduledEmailBase):
    pass


class ScheduledEmailUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    is_html: Optional[bool] = None
    recipients: Optional[List[EmailStr]] = None
    cc: Optional[List[EmailStr]] = None
    is_active: Optional[bool] = None
    run_date: Optional[datetime] = None
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None


class ScheduledEmailOut(ScheduledEmailBase):
    id: int
    is_active: bool
    created_at: datetime
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmailLogOut(BaseModel):
    id: int
    subject: str
    recipients: List[str]
    status: str
    error_message: Optional[str] = None
    sent_at: datetime

    model_config = {"from_attributes": True}


# ---------- Alerts ----------

class AlertBase(BaseModel):
    name: str
    alert_type: str  # webhook_status | keyword_present | keyword_missing | response_time
    target_url: str
    check_interval_seconds: int = 300
    expected_status: Optional[int] = 200
    keyword: Optional[str] = None
    threshold_ms: Optional[float] = None
    recipients: List[EmailStr]
    cooldown_seconds: int = 1800

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v):
        allowed = ("webhook_status", "keyword_present", "keyword_missing", "response_time")
        if v not in allowed:
            raise ValueError(f"alert_type must be one of: {', '.join(allowed)}")
        return v


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    target_url: Optional[str] = None
    check_interval_seconds: Optional[int] = None
    expected_status: Optional[int] = None
    keyword: Optional[str] = None
    threshold_ms: Optional[float] = None
    recipients: Optional[List[EmailStr]] = None
    cooldown_seconds: Optional[int] = None
    is_active: Optional[bool] = None


class AlertOut(AlertBase):
    id: int
    is_active: bool
    created_at: datetime
    last_checked_at: Optional[datetime] = None
    last_triggered_at: Optional[datetime] = None
    last_status: Optional[str] = None

    model_config = {"from_attributes": True}


class AlertLogOut(BaseModel):
    id: int
    triggered: bool
    message: str
    notified: bool
    checked_at: datetime

    model_config = {"from_attributes": True}
