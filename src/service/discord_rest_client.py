from datetime import datetime

import requests

from config.logger_config import log


class DiscordRestClient:
    def __init__(self, url):
        self.url = url
        self._log_buffer = ""

    def _send_message(self, message: str):
        if not self.url:
            log.warning("[Discord] No webhook URL configured. Skipping notification.")
            return
        try:
            response = requests.post(self.url, json={"content": message})
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

    def send_image(self, buffer):
        if not self.url:
            log.warning(
                "[Discord] No webhook URL configured. Skipping image notification."
            )
            return
        files = {"file": ("image.jpg", buffer, "image/jpeg")}
        try:
            response = requests.post(self.url, files=files)
            if response.status_code == 200:
                log.info("[Discord] Renko plot sent successfully.")
            else:
                log.error(
                    f"[Discord] Failed to send plot. Status: {response.status_code}"
                )
            return response
        except Exception as e:
            log.error(f"[Discord Error] An error occurred while sending image: {e}")
            return None
