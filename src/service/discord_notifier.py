import aiohttp
from config.logger_config import log
from config.env_config import DISCORD_WEBHOOK_URL
from datetime import datetime


class DiscordNotifier:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url or DISCORD_WEBHOOK_URL
        self._log_buffer = ""

    async def _send_message(self, message: str):
        if not self.webhook_url:
            log.warning("[Discord] No webhook URL configured. Skipping notification.")
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json={"content": message}
                ) as response:
                    if response.status == 204:
                        log.info("[Discord] Notification sent successfully.")
                    else:
                        log.error(
                            f"[Discord] Failed to send notification. Status: {response.status}"
                        )
        except Exception as e:
            log.error(f"[Discord Error] An error occurred: {e}")

    def push_log_buffer(self, message: str):
        """
        Buffers log messages to be sent later.
        """
        now = datetime.now().strftime("%H:%M:%S")
        self._log_buffer += f"{now} - {message}\n"

    async def flush_log_buffer(self):
        """
        Sends the buffered log messages as a single notification.
        """
        if self._log_buffer:
            await self._send_message(self._log_buffer)
            self._log_buffer = ""
        else:
            log.info("[Discord] No messages to send in the buffer.")
