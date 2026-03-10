import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer
from .widgets.balance import BalanceWidget
from .widgets.strategy import StrategyWidget
from .widgets.orders import OrdersWidget
from .widgets.chart import ChartWidget
from dca_bot.strategy.config import DBConfig
from dca_bot.strategy.models import StrategyRule, Order
from revolutx_crypto_api.client import RevolutXClient
from revolutx_crypto_api.balance.get_all_balances import get_balances
from revolutx_crypto_api.market_data.get_candles import get_candles
from revolutx_crypto_api.orders.get_active_orders import get_active_orders
from revolutx_crypto_api.orders.get_historical_orders import get_historical_orders
import os
from dotenv import load_dotenv

class DCABotApp(App):
    CSS_PATH = "app.css" # I will create this file to keep app.py clean
    TITLE = "DCA Bot"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("e", "edit_strategy", "Edit"),
        ("r", "refresh", "Refresh"),
        ("escape", "cancel_edit", "Cancel")
    ]

    def on_mount(self) -> None:
        load_dotenv()
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename="dashboard.log"
        )
        self.logger = logging.getLogger("dca_bot_dashboard")
        self.logger.info("Dashboard starting...")
        
        self.db = DBConfig()
        self.api_key = os.getenv("api_key")
        self.private_key = os.getenv("private_key")
        
        if not self.api_key or not self.private_key:
            self.logger.warning("Missing API keys in .env")
            self.notify("Missing API keys in .env", severity="error")
            self.api_client = None
        else:
            self.logger.info("API Client initialized.")
            self.api_client = RevolutXClient(self.api_key, self.private_key)
            
        self.editing_strategy = False
        self.action_refresh()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Horizontal(id="main-row"):
                with Vertical(id="left-panel"):
                    yield ChartWidget(id="chart")
                    yield OrdersWidget(id="orders")
                with Vertical(id="right-panel"):
                    yield BalanceWidget(id="balance")
                    yield StrategyWidget(id="strategy")
        yield Footer()

    def action_refresh(self) -> None:
        self.logger.info("action_refresh triggered")
        if not self.api_client:
            self.logger.warning("api_client is None, skipping refresh")
            return

        try:
            # 1. Update Strategy (Rules + Frequency)
            self.logger.info("Refreshing strategy rules and frequency...")
            rules = self.db.get_active_rules()
            if self.editing_strategy and not rules:
                rules = [StrategyRule(id=None, drop_pct=0, amount_eur=0)]
            freq = self.db.get_setting("order_frequency", "daily")
            self.query_one(StrategyWidget).update_rules(rules, editing=self.editing_strategy, frequency=freq)
            
            # 2. Update Balances (Live)
            self.logger.info("Fetching balances from API...")
            balances = get_balances(self.api_client)
            self.logger.info(f"Balances received: {len(balances)}")
            
            # API keys: currency, available, reserved, total
            eur_bal = next((b for b in balances if b.get("currency") == "EUR"), {"total": "0.00", "available": "0.00", "reserved": "0.00"})
            btc_bal = next((b for b in balances if b.get("currency") == "BTC"), {"total": "0.00000000", "available": "0.00000000", "reserved": "0.00000000"})
            
            self.logger.info(f"EUR total: {eur_bal.get('total')}, avail: {eur_bal.get('available')}, resrv: {eur_bal.get('reserved')}")
            self.logger.info(f"BTC total: {btc_bal.get('total')}, avail: {btc_bal.get('available')}, resrv: {btc_bal.get('reserved')}")
            
            self.query_one(BalanceWidget).update_balance(
                float(eur_bal.get("total", 0)), 
                float(eur_bal.get("available", 0)),
                float(eur_bal.get("reserved", 0)),
                float(btc_bal.get("total", 0)),
                float(btc_bal.get("available", 0)),
                float(btc_bal.get("reserved", 0))
            )
            
            # 3. Update Chart (Live)
            self.logger.info("Fetching candles from API...")
            # Interval must be int for some parts of logic, or string. Docs said example '5'.
            # If 0 received, maybe try a different symbol or just wait.
            candles = get_candles(self.api_client, symbol="BTC-EUR", interval="60")
            
            # The API returns a dictionary with 'data' key
            if isinstance(candles, dict):
                candles = candles.get("data", candles.get("candles", []))
            
            self.logger.info(f"Candles received: {len(candles)}")
            
            normalized_candles = []
            if len(candles) > 0:
                # Normalize keys if necessary: Revolut docs use 'start', 'open', 'high', 'low', 'close', 'volume'
                for c in candles:
                    ts = c.get("start") or c.get("timestamp")
                    if isinstance(ts, (int, float)):
                        if ts > 3000000000:  # Assumed milliseconds
                            ts_str = datetime.fromtimestamp(ts / 1000.0).strftime('%d/%m/%Y %H:%M')
                        else:
                            ts_str = datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M')
                    else:
                        ts_str = str(ts)
                        
                    normalized_candles.append({
                        "timestamp": ts_str,
                        "open": float(c.get("open")),
                        "high": float(c.get("high")),
                        "low": float(c.get("low")),
                        "close": float(c.get("close"))
                    })
            else:
                self.logger.info("Falling back to Binance API for chart data...")
                try:
                    binance_resp = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCEUR&interval=1h&limit=50", timeout=5)
                    if binance_resp.ok:
                        b_data = binance_resp.json()
                        for c in b_data:
                            ts_str = datetime.fromtimestamp(c[0] / 1000.0).strftime('%d/%m/%Y %H:%M')
                            normalized_candles.append({
                                "timestamp": ts_str,
                                "open": float(c[1]),
                                "high": float(c[2]),
                                "low": float(c[3]),
                                "close": float(c[4])
                            })
                        self.logger.info(f"Binance fallback successful: {len(normalized_candles)} candles")
                except Exception as e:
                    self.logger.error(f"Binance fallback failed: {e}")
            
            self.query_one(ChartWidget).update_chart(normalized_candles)
            
            # 4. Update Orders (Live + Cross-ref)
            self.logger.info("Fetching orders from API...")
            act_resp = get_active_orders(self.api_client)
            hist_resp = get_historical_orders(self.api_client)
            
            active_orders = act_resp.get("data", []) if isinstance(act_resp, dict) else []
            historical_orders = hist_resp.get("data", []) if isinstance(hist_resp, dict) else []
            
            self.logger.info(f"Active orders: {len(active_orders)}")
            self.logger.info(f"Historical orders: {len(historical_orders)}")
            
            all_api_orders = active_orders + historical_orders
            
            # Get Bot orders from DB to cross-reference
            bot_order_ids = set()
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT revolut_order_id FROM orders WHERE revolut_order_id IS NOT NULL")
                bot_order_ids = {row[0] for row in cursor.fetchall()}
            
            processed_orders = []
            for ao in all_api_orders:
                is_bot = ao.get("id") in bot_order_ids or ao.get("client_order_id") in bot_order_ids
                
                # Convert milliseconds timestamp to string
                dt_str = ""
                if ao.get("created_date"):
                    dt_str = datetime.fromtimestamp(ao.get("created_date")/1000).strftime('%Y-%m-%d %H:%M')
                
                price = float(ao.get("price", ao.get("limit_price", 0)))
                amount = float(ao.get("quantity", 0))
                value = price * amount

                processed_orders.append({
                    "date": dt_str,
                    "symbol": ao.get("symbol", ""),
                    "type": ao.get("type", ""),
                    "side": ao.get("side", ""),
                    "amount": amount,
                    "price": price,
                    "value": value,
                    "status": ao.get("status", ""),
                    "source": "Bot" if is_bot else "Manual"
                })
            
            # Sort by date descending
            processed_orders.sort(key=lambda x: x["date"], reverse=True)
            self.query_one(OrdersWidget).update_orders_live(processed_orders[:50])
            self.logger.info("action_refresh completed successfully")

        except Exception as e:
            self.logger.error(f"Refresh failed: {e}", exc_info=True)
            self.notify(f"Refresh failed: {e}", severity="error")

    def action_edit_strategy(self) -> None:
        self.editing_strategy = not self.editing_strategy
        self.action_refresh()

    def action_cancel_edit(self) -> None:
        self.editing_strategy = False
        self.action_refresh()

if __name__ == "__main__":
    app = DCABotApp()
    app.run()
