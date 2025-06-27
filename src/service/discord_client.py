from datetime import datetime

import requests

from config.logger_config import log


class DiscordClient:
    def __init__(self, url: str):
        self.url = url
        self._log_buffer = ""

    def _send_message(self, message: str):
        try:
            response = requests.post(self.url, json={"content": message})
            if response.status_code == 204:
                return
            else:
                log.error(
                    f"[Discord] Failed to send notification. Status: {response.status_code}"
                )
        except Exception as e:
            log.error(f"[Discord] An error occurred: {e}")

    def push_log_buffer(self, message: str, log_level: str = "info"):
        """
        Buffers log messages to be sent later.
        """
        if log_level.lower() == "info":
            log.info(message)
        elif log_level.lower() == "warning":
            log.warning(message)
        elif log_level.lower() == "error":
            log.error(message)
        else:
            log.debug(message)
        now = datetime.now().strftime("%H:%M:%S")
        self._log_buffer += f"{now} - {log_level.upper()} - {message}\n"

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
        files = {"file": ("image.jpg", buffer, "image/jpeg")}
        try:
            response = requests.post(self.url, files=files)
            if response.status_code == 200:
                return
            else:
                log.error(
                    f"[Discord] Failed to send image. Status: {response.status_code}"
                )
        except Exception as e:
            log.error(f"[Discord] An error occurred while sending image: {e}")
            return None
