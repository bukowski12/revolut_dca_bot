from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.containers import Vertical
from dca_bot.strategy.models import Order
from typing import List

class OrdersWidget(Vertical):
    BORDER_TITLE = "Orders"
    def compose(self) -> ComposeResult:
        yield DataTable(id="orders-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        # Using larger proportional widths to fill the space (simulating percentages)
        table.add_column("Time placed", width=25)
        table.add_column("Pair", width=10)
        table.add_column("Type", width=15)
        table.add_column("Price", width=15)
        table.add_column("Quantity", width=20)
        table.add_column("Value", width=15)
        table.add_column("Status", width=12)
        table.add_column("Source", width=12)
        table.expand = True
        table.zebra_stripes = True

    def update_orders_live(self, orders: List[dict]):
        table = self.query_one(DataTable)
        table.clear()
        for o in orders:
            # Differentiate by side for price/amount
            price = f"{o['price']:.2f}"
            amount = f"{o['amount']:.8f}"
            
            table.add_row(
                o["date"],
                o["symbol"],
                f"{o['side']} {o['type']}",
                price,
                amount,
                f"{o['value']:.2f}",
                o["status"],
                o["source"]
            )
