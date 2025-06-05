import logging

from .daily_log_file_handler import DailyLogFileHandler

file_handler = DailyLogFileHandler(log_dir="logs")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, stream_handler],
)

log = logging.getLogger(__name__)
