from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical
import logging

class BalanceWidget(Vertical):
    BORDER_TITLE = "Balance"
    def compose(self) -> ComposeResult:
        with Vertical(classes="balance-row"):
            yield Static("EUR Total: 0.00", id="balance-eur-total", classes="total")
            yield Static("EUR Avail: 0.00", id="balance-eur-avail", classes="available")
            yield Static("EUR Resrv: 0.00", id="balance-eur-resrv", classes="reserved")
        with Vertical(classes="balance-row"):
            yield Static("BTC Total: 0.00000000", id="balance-btc-total", classes="total")
            yield Static("BTC Avail: 0.00000000", id="balance-btc-avail", classes="available")
            yield Static("BTC Resrv: 0.00000000", id="balance-btc-resrv", classes="reserved")

    def update_balance(self, eur_total: float, eur_avail: float, eur_resrv: float, btc_total: float, btc_avail: float, btc_resrv: float):
        self.query_one("#balance-eur-total").update(f"EUR Total: {eur_total:.2f}")
        self.query_one("#balance-eur-avail").update(f"EUR Avail: {eur_avail:.2f}")
        self.query_one("#balance-eur-resrv").update(f"EUR Resrv: {eur_resrv:.2f}")
        self.query_one("#balance-btc-total").update(f"BTC Total: {btc_total:.8f}")
        self.query_one("#balance-btc-avail").update(f"BTC Avail: {btc_avail:.8f}")
        self.query_one("#balance-btc-resrv").update(f"BTC Resrv: {btc_resrv:.8f}")
        self.logger = logging.getLogger("dca_bot_dashboard")
        self.logger.info(f"BalanceWidget updated: EUR={eur_total}/{eur_avail}/{eur_resrv}, BTC={btc_total}/{btc_avail}/{btc_resrv}")
