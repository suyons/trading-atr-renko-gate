import logging
import os
from datetime import datetime


class DailyLogFileHandler(logging.Handler):
    def __init__(self, log_dir="logs"):
        super().__init__()
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.current_date = datetime.now().date()
        self._open_new_file()

    def _open_new_file(self):
        if hasattr(self, "stream") and self.stream:
            self.stream.close()
        filename = self.current_date.strftime("%Y-%m-%d.log")
        self.baseFilename = os.path.join(self.log_dir, filename)
        self.stream = open(self.baseFilename, "a", encoding="utf-8")

    def emit(self, record):
        now = datetime.now().date()
        if now != self.current_date:
            self.current_date = now
            self._open_new_file()
        msg = self.format(record)
        self.stream.write(msg + "\n")
        self.stream.flush()

    def close(self):
        if self.stream:
            self.stream.close()
        super().close()
