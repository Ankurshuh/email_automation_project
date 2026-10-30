"""
Scheduling engine module.

A thin, swappable wrapper around APScheduler. Calling code only ever talks
to `SchedulerEngine` -- so the underlying scheduler (in-process APScheduler
today, Celery Beat later, per the Milestone 1 architecture) can change
without touching any caller.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("automation.scheduler_engine")


class SchedulerEngine:
    """Core scheduling engine: register jobs, check their next run time, cancel them."""

    def __init__(self):
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler engine started")

    def shutdown(self, wait: bool = False) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("Scheduler engine stopped")

    def schedule_once(self, job_id: str, run_at: datetime, func: Callable, *args: Any, **kwargs: Any) -> str:
        """Schedule `func` to run exactly once, at `run_at`."""
        self._scheduler.add_job(
            func, trigger=DateTrigger(run_date=run_at), id=job_id,
            args=args, kwargs=kwargs, replace_existing=True, misfire_grace_time=300,
        )
        return job_id

    def schedule_interval(self, job_id: str, seconds: int, func: Callable, *args: Any, **kwargs: Any) -> str:
        """Schedule `func` to run every `seconds` seconds, forever."""
        self._scheduler.add_job(
            func, trigger=IntervalTrigger(seconds=seconds), id=job_id,
            args=args, kwargs=kwargs, replace_existing=True, misfire_grace_time=60,
        )
        return job_id

    def schedule_cron(self, job_id: str, cron_expression: str, func: Callable, *args: Any, **kwargs: Any) -> str:
        """Schedule `func` on a 5-field crontab expression."""
        self._scheduler.add_job(
            func, trigger=CronTrigger.from_crontab(cron_expression), id=job_id,
            args=args, kwargs=kwargs, replace_existing=True, misfire_grace_time=300,
        )
        return job_id

    def cancel(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    def next_run_time(self, job_id: str) -> Optional[datetime]:
        """Returns None once a one-time job has fired, or if job_id doesn't exist."""
        job = self._scheduler.get_job(job_id)
        if job and job.next_run_time:
            return job.next_run_time.replace(tzinfo=None)
        return None
