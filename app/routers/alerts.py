from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.scheduler import _run_alert_check, schedule_alert_job, unschedule_job

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("/", response_model=schemas.AlertOut, status_code=201)
def create_alert(payload: schemas.AlertCreate, db: Session = Depends(get_db)):
    _validate_alert_fields(payload)

    alert = models.Alert(
        name=payload.name,
        alert_type=payload.alert_type,
        target_url=payload.target_url,
        check_interval_seconds=payload.check_interval_seconds,
        expected_status=payload.expected_status,
        keyword=payload.keyword,
        threshold_ms=payload.threshold_ms,
        recipients=payload.recipients,
        cooldown_seconds=payload.cooldown_seconds,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    alert.job_id = schedule_alert_job(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/", response_model=List[schemas.AlertOut])
def list_alerts(db: Session = Depends(get_db)):
    return db.query(models.Alert).order_by(models.Alert.id.desc()).all()


@router.get("/{alert_id}", response_model=schemas.AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, alert_id)


@router.patch("/{alert_id}", response_model=schemas.AlertOut)
def update_alert(alert_id: int, payload: schemas.AlertUpdate, db: Session = Depends(get_db)):
    alert = _get_or_404(db, alert_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)

    if alert.is_active:
        alert.job_id = schedule_alert_job(alert)
    else:
        unschedule_job(alert.job_id)
    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = _get_or_404(db, alert_id)
    unschedule_job(alert.job_id)
    db.delete(alert)
    db.commit()


@router.post("/{alert_id}/test")
def test_alert(alert_id: int, db: Session = Depends(get_db)):
    _get_or_404(db, alert_id)
    _run_alert_check(alert_id)
    return {"detail": "Alert check executed immediately. See /alerts/{id}/logs for the result."}


@router.get("/{alert_id}/logs", response_model=List[schemas.AlertLogOut])
def get_alert_logs(alert_id: int, db: Session = Depends(get_db)):
    _get_or_404(db, alert_id)
    return (
        db.query(models.AlertLog)
        .filter(models.AlertLog.alert_id == alert_id)
        .order_by(models.AlertLog.id.desc())
        .all()
    )


def _get_or_404(db: Session, alert_id: int) -> models.Alert:
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _validate_alert_fields(payload: schemas.AlertCreate):
    if payload.alert_type in ("keyword_present", "keyword_missing") and not payload.keyword:
        raise HTTPException(400, "keyword is required for this alert_type")
    if payload.alert_type == "response_time" and not payload.threshold_ms:
        raise HTTPException(400, "threshold_ms is required for alert_type=response_time")
