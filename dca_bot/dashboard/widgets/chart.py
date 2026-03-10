from textual.widgets import Static
import plotext as plt
from rich.text import Text
import logging
from typing import List

class ChartWidget(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.candles = []
        self._last_w = 0
        self._last_h = 0
        # Remove default padding to maximize chart size
        self.styles.padding = 0
        self.styles.overflow_x = "hidden"
        self.styles.overflow_y = "hidden"
        
    def on_mount(self) -> None:
        pass # App will call update_chart

    def update_chart(self, candles: List[dict] = None):
        logger = logging.getLogger("dca_bot_dashboard")
        if not candles:
            logger.info("ChartWidget: No candles provided")
            self.candles = []
            self.update("No chart data available")
        else:
            logger.info(f"ChartWidget: Storing {len(candles)} candles for render")
            self.candles = candles
            self._last_w = 0 # Force a rebuild when new data arrives
            self._rebuild_chart()

    def on_resize(self, event) -> None:
        if self.candles:
            self._rebuild_chart()

    def _rebuild_chart(self) -> None:
        if not self.candles:
            return
            
        # Textual's self.size inside provides accurate terminal layout dimensions
        w = max(self.size.width - 2, 10)
        h = max(self.size.height - 2, 5)
            
        # Prevent infinite resize loops by caching the dimensions we just drew
        if w == self._last_w and h == self._last_h:
            return
            
        self._last_w = w
        self._last_h = h
            
        try:
            dates = [c.get("timestamp") for c in self.candles]
            opens = [float(c.get("open")) for c in self.candles]
            highs = [float(c.get("high")) for c in self.candles]
            lows = [float(c.get("low")) for c in self.candles]
            closes = [float(c.get("close")) for c in self.candles]
            
            plt.clf()
            
            if w > 10 and h > 5:
                plt.plotsize(w, h)
            else:
                plt.plotsize(100, 30) # Safe default
            
            plt.theme("dark")
            plt.date_form("d/m/Y H:M")
            
            plt.candlestick(dates, {"Open": opens, "High": highs, "Low": lows, "Close": closes})
            

            
            plt.title("BTC-EUR")
            plt.grid(False, False)
            
            # Use Rich's Text to safely parse and display ANSI color codes from plotext
            self.update(Text.from_ansi(plt.build()))
        except Exception as e:
            logging.getLogger("dca_bot_dashboard").error(f"Chart render error: {e}", exc_info=True)
            self.update(Text.from_ansi("Chart Error"))
