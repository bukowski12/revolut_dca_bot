import logging
import sqlite3
import uuid
from typing import List, Optional
from revolutx_crypto_api.client import RevolutXClient
from revolutx_crypto_api.orders.get_order import get_order
from revolutx_crypto_api.orders.cancel_order import cancel_order
from revolutx_crypto_api.orders.place_order import place_order
from .models import StrategyRule, CronRun, Order
from .config import DBConfig

class StrategyExecutor:
    def __init__(self, api_client: RevolutXClient, db: DBConfig):
        self.api_client = api_client
        self.db = db
        self.logger = logging.getLogger(__name__)

    def process_yesterday_orders(self):
        self.logger.info("Processing open orders from previous runs...")
        open_orders = self.db.get_open_orders()
        for order in open_orders:
            try:
                # 1. Check status on exchange
                status_resp = get_order(self.api_client, order.revolut_order_id)
                # Handle potential 'data' wrapper
                order_data = status_resp.get("data") if "data" in status_resp else status_resp
                status = order_data.get("status") or order_data.get("state")

                if status == "filled":
                    order.status = "filled"
                    order.btc_amount = float(order_data.get("filled_amount", 0))
                    order.btc_price = float(order_data.get("average_price", 0))
                    self.db.update_order(order)
                    self.logger.info(f"Order {order.id} was filled.")
                elif status in ["open", "new", "pending", "placed"]:
                    # 2. Cancel if still open/pending
                    cancel_order(self.api_client, order.revolut_order_id)
                    order.status = "cancelled"
                    self.db.update_order(order)
                    self.logger.info(f"Order {order.id} was still open (status={status}), cancelled it.")
                    
                    # 3. If always_run, execute market order
                    rule = self._get_rule_by_id(order.rule_id)
                    if rule and rule.always_run:
                        self.logger.info(f"Rule {rule.id} has always_run=True, executing market order.")
                        order_config = {
                            "client_order_id": str(uuid.uuid4()),
                            "symbol": "BTC-EUR",
                            "side": "BUY",
                            "order_configuration": {
                                "market": {
                                    "quote_size": str(order.amount_eur)
                                }
                            }
                        }
                        # Note: Check API spec for exact market buy config if this fails
                        market_resp = place_order(self.api_client, order_config)
                        
                        new_order = Order(
                            run_id=order.run_id,
                            rule_id=order.rule_id,
                            order_type="market",
                            trigger_reason="always_run",
                            amount_eur=order.amount_eur,
                            btc_amount=float(market_resp.get("data", {}).get("filled_amount", 0)),
                            btc_price=float(market_resp.get("data", {}).get("average_price", 0)),
                            revolut_order_id=market_resp.get("data", {}).get("venue_order_id"),
                            status="filled"
                        )
                        self.db.create_order(new_order)
                else:
                    self.logger.warning(f"Order {order.id} has unexpected status: {status}, skipping.")
                    order.status = str(status) if status else order.status
                    self.db.update_order(order)

            except Exception as e:
                self.logger.error(f"Error processing order {order.id}: {e}")

    def execute_new_strategy(self, reference_price: float, run_id: int):
        self.logger.info(f"Executing new strategy rules for today. Reference price: {reference_price}")
        rules = self.db.get_active_rules()
        for rule in rules:
            try:
                limit_price = reference_price * (1 - rule.drop_pct / 100)
                self.logger.info(f"Rule {rule.id}: Placing limit order at {limit_price:.2f} EUR (drop {rule.drop_pct}%)")
                
                quantity = rule.amount_eur / limit_price
                # Round to 8 decimal places (standard for BTC)
                quantity_str = f"{quantity:.8f}"
                
                order_config = {
                    "client_order_id": str(uuid.uuid4()),
                    "symbol": "BTC-EUR",
                    "side": "BUY",
                    "order_configuration": {
                        "limit": {
                            "base_size": quantity_str,
                            "price": f"{limit_price:.2f}"
                        }
                    }
                }
                resp = place_order(self.api_client, order_config)
                
                new_order = Order(
                    run_id=run_id,
                    rule_id=rule.id,
                    order_type="limit",
                    trigger_reason="limit_placed",
                    amount_eur=rule.amount_eur,
                    limit_price=limit_price,
                    revolut_order_id=resp.get("data", {}).get("venue_order_id"),
                    status="open"
                )
                self.db.create_order(new_order)
            except Exception as e:
                self.logger.error(f"Error executing rule {rule.id}: {e}")

    def cancel_all_open_orders(self):
        self.logger.info("Cancelling all open orders...")
        open_orders = self.db.get_open_orders()
        for order in open_orders:
            try:
                self.logger.info(f"Cancelling order {order.revolut_order_id} (DB ID: {order.id})")
                cancel_order(self.api_client, order.revolut_order_id)
                order.status = "cancelled"
                self.db.update_order(order)
            except Exception as e:
                self.logger.error(f"Error cancelling order {order.id}: {e}")

    def _get_rule_by_id(self, rule_id: int) -> Optional[StrategyRule]:
        with self.db._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM strategy_rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            return StrategyRule(**dict(row)) if row else None
