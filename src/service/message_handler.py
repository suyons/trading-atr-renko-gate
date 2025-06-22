from config.logger_config import log


class MessageHandler:
    def __init__(self):
        self.message = None

    def handle_message(self, message: str):
        """
        Handles incoming messages by parsing JSON and storing the message.
        """
        try:
            self.message = message
            log.info(f"[Socket] Received message: {self.message}")
        except Exception as e:
            log.error(f"[Socket] Error handling message: {e}")
            self.message = None
