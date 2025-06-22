import os
import requests
from config.logger_config import log
from datetime import datetime

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", None)


class DiscordRestClient:
    def __init__(self):
        self._log_buffer = ""

    def _send_message(message: str):
        if not DISCORD_WEBHOOK_URL:
            log.warning("[Discord] No webhook URL configured. Skipping notification.")
            return
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
            if response.status_code == 204:
                log.info("[Discord] Notification sent successfully.")
            else:
                log.error(
                    f"[Discord] Failed to send notification. Status: {response.status_code}"
                )
        except Exception as e:
            log.error(f"[Discord Error] An error occurred: {e}")

    def push_log_buffer(self, message: str):
        """
        Buffers log messages to be sent later.
        """
        log.info(message)
        now = datetime.now().strftime("%H:%M:%S")
        self._log_buffer += f"{now} - {message}\n"

    def flush_log_buffer(self):
        """
        Sends the buffered log messages as a single notification.
        """
        if self._log_buffer:
            self._send_message(self._log_buffer)
            self._log_buffer = ""
        else:
            log.info("[Discord] No messages to send in the buffer.")
