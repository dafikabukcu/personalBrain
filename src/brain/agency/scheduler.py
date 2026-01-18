"""Scheduler for autonomous brain tasks."""

from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from brain.core.config import Config

logger = structlog.get_logger()


class BrainScheduler:
    """Scheduler for autonomous brain tasks."""

    def __init__(self, config: Config):
        self.config = config
        self.scheduler = AsyncIOScheduler(timezone=config.scheduler.timezone)
        self._briefing_callback = None
        self._reminder_callback = None

    def set_briefing_callback(self, callback) -> None:
        """Set callback for daily briefing."""
        self._briefing_callback = callback

    def set_reminder_callback(self, callback) -> None:
        """Set callback for reminder checks."""
        self._reminder_callback = callback

    def setup_jobs(self) -> None:
        """Set up scheduled jobs."""
        # Parse briefing time
        hour, minute = map(int, self.config.scheduler.briefing_time.split(":"))

        # Daily briefing
        if self._briefing_callback:
            self.scheduler.add_job(
                self._briefing_callback,
                CronTrigger(hour=hour, minute=minute),
                id="daily_briefing",
                replace_existing=True,
            )
            logger.info("scheduled_daily_briefing", time=self.config.scheduler.briefing_time)

        # Reminder check
        if self._reminder_callback:
            self.scheduler.add_job(
                self._reminder_callback,
                "interval",
                minutes=self.config.scheduler.reminder_check_interval,
                id="reminder_check",
                replace_existing=True,
            )
            logger.info(
                "scheduled_reminder_check",
                interval_minutes=self.config.scheduler.reminder_check_interval,
            )

    def start(self) -> None:
        """Start the scheduler."""
        self.setup_jobs()
        self.scheduler.start()
        logger.info("scheduler_started")

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
        logger.info("scheduler_stopped")

    def run_now(self, job_id: str) -> None:
        """Run a job immediately."""
        job = self.scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
