import json
import traceback
import certifi
import websocket
from PyQt5.QtCore import QThread, pyqtSignal

class FinnhubWebsocketClient(QThread):
    """
    Connects to wss://ws.finnhub.io for real-time trade updates.
    Requires a free API key from finnhub.io.
    """
    
    # Emits dict: {"symbol": str, "p": float, "v": float, "t": int}
    trade_received = pyqtSignal(dict)
    
    # Emits string messages (errors, connection status)
    status_changed = pyqtSignal(str)

    def __init__(self, api_key: str, symbols: list):
        super().__init__()
        self.api_key = api_key
        self.symbols = symbols
        self.ws = None
        self._is_running = False

    def run(self):
        self._is_running = True
        websocket.enableTrace(False)
        url = f"wss://ws.finnhub.io?token={self.api_key}"
        
        self.status_changed.emit("Connecting to Finnhub WebSocket...")
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.ws.on_open = self.on_open
        
        # Use certifi to avoid SSL errors on some Linux distros
        self.ws.run_forever(sslopt={"ca_certs": certifi.where()})
        
        self.status_changed.emit("WebSocket Thread Exiting.")
        self._is_running = False

    def stop(self):
        self._is_running = False
        if self.ws:
            self.ws.close()

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("type") == "trade":
                for trade in data.get("data", []):
                    # trade format: {'p': 150.5, 's': 'AAPL', 't': 1612345678000, 'v': 100}
                    payload = {
                        "symbol": trade.get("s"),
                        "p": trade.get("p"),
                        "v": trade.get("v"),
                        "t": trade.get("t")
                    }
                    self.trade_received.emit(payload)
            elif data.get("type") == "ping":
                pass # Heartbeat
        except Exception as e:
            pass # Ignore malformed json

    def on_error(self, ws, error):
        self.status_changed.emit(f"WS Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.status_changed.emit("WS Closed.")

    def on_open(self, ws):
        self.status_changed.emit("WS Connected! Subscribing to US symbols...")
        # Subscribe to all provided symbols
        for sym in self.symbols:
            # Finnhub expects plain US symbols (e.g. AAPL, not AAPL.US)
            # We filter out non-US symbols here if needed, but the caller should supply clean symbols
            clean_sym = sym.split(".")[0] if not sym.startswith("^") else sym
            msg = {"type": "subscribe", "symbol": clean_sym}
            ws.send(json.dumps(msg))
