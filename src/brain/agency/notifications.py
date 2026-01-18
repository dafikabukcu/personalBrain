"""Notification service for desktop and n8n webhook."""

import httpx
import structlog

from brain.core.config import Config

logger = structlog.get_logger()


class NotificationService:
    """Send notifications via desktop and/or n8n webhook."""

    def __init__(self, config: Config):
        self.config = config
        self.enabled = config.notifications.enabled
        self.desktop_enabled = config.notifications.desktop
        self.n8n_enabled = config.notifications.n8n.enabled
        self.n8n_webhook_url = config.n8n_webhook_url or config.notifications.n8n.webhook_url

    async def send(
        self,
        title: str,
        message: str,
        notification_type: str = "info",
    ) -> None:
        """Send a notification."""
        if not self.enabled:
            return

        if self.desktop_enabled:
            await self._send_desktop(title, message)

        if self.n8n_enabled and self.n8n_webhook_url:
            await self._send_n8n(title, message, notification_type)

    async def _send_desktop(self, title: str, message: str) -> None:
        """Send desktop notification."""
        try:
            from plyer import notification

            notification.notify(
                title=title,
                message=message[:256],  # plyer has length limits
                app_name="Personal Brain",
                timeout=10,
            )
            logger.debug("desktop_notification_sent", title=title)
        except Exception as e:
            logger.warning("desktop_notification_failed", error=str(e))

    async def _send_n8n(
        self,
        title: str,
        message: str,
        notification_type: str,
    ) -> None:
        """Send notification to n8n webhook."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.n8n_webhook_url,
                    json={
                        "title": title,
                        "message": message,
                        "type": notification_type,
                        "source": "personal-brain",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.debug("n8n_notification_sent", title=title)
        except Exception as e:
            logger.warning("n8n_notification_failed", error=str(e))

    async def send_briefing(self, briefing) -> None:
        """Send daily briefing notification."""
        tasks_count = len(briefing.tasks_due)
        reminders_count = len(briefing.reminders)

        title = f"Daily Briefing - {briefing.date.strftime('%B %d')}"
        message = f"{tasks_count} tasks due, {reminders_count} reminders"

        if briefing.summary:
            message += f"\n\n{briefing.summary[:200]}"

        await self.send(title, message, notification_type="briefing")

    async def send_reminder(self, reminder) -> None:
        """Send a reminder notification."""
        await self.send(
            title="Reminder",
            message=reminder.content,
            notification_type="reminder",
        )
