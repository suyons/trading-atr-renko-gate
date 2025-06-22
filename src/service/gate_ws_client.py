import hashlib
import hmac
import json
import os
import time
import threading
from websocket import WebSocketApp

from config.logger_config import log

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
GATE_WS_TEST_URL = os.getenv("GATE_WS_TEST_URL")
SYMBOL = os.getenv("SYMBOL")


event = threading.Event()


class GateWsClient(WebSocketApp):
    def __init__(self, url, message_handler=None, **kwargs):
        super(GateWsClient, self).__init__(
            url, on_message=self._on_message, on_open=self._on_open, **kwargs
        )
        self.message_handler = message_handler

    def _send_ping(self):
        while not event.wait(10):
            self.last_ping_tm = time.time()
            if self.sock:
                try:
                    self.sock.ping()
                except Exception as ex:
                    log.warning("send_ping routine terminated: {}".format(ex))
                    break
                try:
                    self._request("futures.ping", auth_required=False)
                except Exception as e:
                    raise e

    def _request(self, channel, event=None, payload=None, auth_required=True):
        current_time = int(time.time())
        data = {
            "time": current_time,
            "channel": channel,
            "event": event,
            "payload": payload,
        }
        if auth_required:
            message = "channel=%s&event=%s&time=%d" % (channel, event, current_time)
            data["auth"] = {
                "method": "api_key",
                "KEY": API_KEY,
                "SIGN": self.get_sign(message),
            }
        data = json.dumps(data)
        log.info("request: %s", data)
        self.send(data)

    def get_sign(self, message):
        h = hmac.new(SECRET_KEY.encode("utf8"), message.encode("utf8"), hashlib.sha512)
        return h.hexdigest()

    def subscribe(self, channel, payload=None, auth_required=True):
        self._request(channel, "subscribe", payload, auth_required)

    def unsubscribe(self, channel, payload=None, auth_required=True):
        self._request(channel, "unsubscribe", payload, auth_required)

    def _on_message(self, ws, message):
        # handle message received
        if self.message_handler:
            self.message_handler.handle_message(message)

    def _on_open(self, ws):
        # subscribe to channels interested
        log.info("websocket connected")
        self.subscribe("futures.tickers", [SYMBOL], False)


if __name__ == "__main__":
    log.info("Starting Gate WebSocket Client...")
    ws_client = GateWsClient(url=GATE_WS_TEST_URL)
    ws_client.run_forever()
    event.set()  # Stop the ping thread when the main thread exits
    log.info("Gate WebSocket Client stopped.")
