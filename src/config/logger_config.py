from datetime import datetime
import logging
import os

os.makedirs("../logs", exist_ok=True)
log_filename = datetime.now().strftime("../logs/%Y-%m-%d.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)
