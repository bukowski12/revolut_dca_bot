from textual.app import ComposeResult
from textual.widgets import Static, Input, Button, Checkbox, ListItem, ListView, RadioSet, RadioButton
from textual.containers import Vertical, Horizontal
from textual.message import Message
from dca_bot.strategy.models import StrategyRule
from dca_bot.strategy.executor import StrategyExecutor
from dca_bot.strategy import cron_manager
import subprocess
import os
import sys
from typing import List

class StrategyRuleWidget(Static):
    class Changed(Message):
        def __init__(self, rule: StrategyRule):
            super().__init__()
            self.rule = rule

    def __init__(self, rule: StrategyRule, editing: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.rule = rule
        self.editing = editing

    def compose(self) -> ComposeResult:
        if self.editing:
            with Vertical(classes="rule-edit-container"):
                with Horizontal(classes="rule-row-edit"):
                    yield Static("Drop:", classes="label")
                    yield Input(value=str(self.rule.drop_pct), classes="input-pct")
                    yield Static("%", classes="unit")
                    yield Static("Amount:", classes="label")
                    yield Input(value=str(self.rule.amount_eur), classes="input-amt")
                    yield Static("EUR", classes="unit")
                    yield Button("X", variant="error", classes="delete-btn-rule")
                yield Checkbox("[b]Market Order If Price Don't Drop To End of FREQ[/b]", value=self.rule.always_run, classes="checkbox-always")
        else:
            with Vertical(classes="rule-display-container"):
                with Horizontal(classes="rule-row"):
                    yield Static("Buy at", classes="label")
                    yield Static(f"{int(self.rule.drop_pct):>4}%", classes="pct")
                    yield Static("price drop for", classes="label")
                    yield Static(f"{int(self.rule.amount_eur):>6}", classes="amt")
                    yield Static("EUR", classes="unit")
                if self.rule.always_run:
                    yield Static("Or At The End of FREQ", classes="always")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.has_class("delete-btn-rule") or event.button.has_class("delete-btn-small"):
            # Signal parent to remove this widget/rule
            self.post_message(self.DeleteRequest(self))

    class DeleteRequest(Message):
        def __init__(self, widget: 'StrategyRuleWidget'):
            super().__init__()
            self.widget = widget

    def get_updated_rule(self) -> StrategyRule:
        """Helper to get current state from inputs."""
        if not self.editing:
            return self.rule
        
        try:
            self.rule.drop_pct = int(float(self.query_one(".input-pct", Input).value))
            self.rule.amount_eur = int(float(self.query_one(".input-amt", Input).value))
            # Fetch always_run status from Checkbox
            self.rule.always_run = self.query_one(".checkbox-always", Checkbox).value
            return self.rule
        except ValueError:
            raise ValueError(f"Invalid values in rule: {self.rule}")

class StrategyWidget(Vertical):
    #BORDER_SUBTITLE = "Strategy"
    BORDER_TITLE = "Strategy"
    def compose(self) -> ComposeResult:
        with Horizontal(id="activate-btn-container"):
            yield Button("Activate", id="activate-btn", classes="activate", flat=True)
        #yield Static("STRATEGY [E] edit", classes="header")
        with Horizontal(id="freq-display-row", classes="freq-row"):
            yield Static("Order Frequency: ", classes="label")
            yield Static("daily", id="freq-value", classes="value")
        with Horizontal(id="freq-edit-row", classes="freq-row"):
            yield Static("Order Frequency: ", classes="label")
            with RadioSet(id="freq-radioset"):
                yield RadioButton("daily", id="radio-daily", value=True)
                yield RadioButton("weekly", id="radio-weekly")
                yield RadioButton("monthly", id="radio-monthly")
        yield Vertical(id="rules-container")
        with Horizontal(id="strategy-footer", classes="hidden"):
            yield Button("Add Order", id="add-order-btn", flat=True)
            yield Button("Save Strategy", variant="success", id="save-strategy-btn", flat=True)
            yield Button("Cancel", variant="primary", id="cancel-strategy-btn", flat=True)

    def update_rules(self, rules: List[StrategyRule], editing: bool = False, frequency: str = "daily"):
        container = self.query_one("#rules-container")
        container.remove_children()
        footer = self.query_one("#strategy-footer")
        
        freq_display = self.query_one("#freq-display-row")
        freq_edit = self.query_one("#freq-edit-row")
        
        if editing:
            footer.display = True
            freq_display.display = False
            freq_edit.display = True
            
            # Update radio buttons to match current frequency
            rs = self.query_one("#freq-radioset", RadioSet)
            # Use 'with rs.prevent(RadioSet.Changed):' if needed, but here we just want to set state
            for button in rs.query(RadioButton):
                button.value = (button.label.plain == frequency)
        else:
            footer.display = False
            freq_display.display = True
            freq_edit.display = False
            self.query_one("#freq-value").update(frequency.capitalize())

        # Update Activate/Deactivate button
        activate_btn = self.query_one("#activate-btn", Button)
        if not rules:
            activate_btn.label = "Activate"
            activate_btn.disabled = True
            activate_btn.remove_class("deactivate")
            activate_btn.add_class("activate")
        else:
            activate_btn.disabled = False
            if cron_manager.is_cron_active():
                activate_btn.label = "Deactivate"
                activate_btn.remove_class("activate")
                activate_btn.add_class("deactivate")
            else:
                activate_btn.label = "Activate"
                activate_btn.remove_class("deactivate")
                activate_btn.add_class("activate")

        for rule in rules:
            container.mount(StrategyRuleWidget(rule, editing=editing))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-order-btn":
            container = self.query_one("#rules-container")
            new_rule = StrategyRule(drop_pct=0, amount_eur=0)
            container.mount(StrategyRuleWidget(new_rule, editing=True))
        
        elif event.button.id == "save-strategy-btn":
            rules_to_save = []
            container = self.query_one("#rules-container")
            
            try:
                for widget in container.query(StrategyRuleWidget):
                    updated_rule = widget.get_updated_rule()
                    # Basic validation
                    if updated_rule.drop_pct <= 0 and not updated_rule.always_run:
                        self.app.notify(f"Error: Drop % must be > 0 for all rules.", severity="error")
                        return
                    if updated_rule.amount_eur <= 0:
                        self.app.notify(f"Error: Amount must be > 0 for all rules.", severity="error")
                        return
                    rules_to_save.append(updated_rule)
                
                # Save frequency setting
                rs = self.query_one("#freq-radioset", RadioSet)
                selected_radio = next((r for r in rs.query(RadioButton) if r.value), None)
                if selected_radio:
                    self.app.db.set_setting("order_frequency", selected_radio.label.plain)

                # Batch update DB
                self.app.db.clear_rules()
                for r in rules_to_save:
                    self.app.db.add_rule(r)
                
                self.app.editing_strategy = False
                self.app.action_refresh()
                self.app.notify("Strategy saved successfully!")
            except ValueError as e:
                self.app.notify(str(e), severity="error")

        elif event.button.id == "cancel-strategy-btn":
            self.app.action_cancel_edit()
        
        elif event.button.id == "activate-btn":
            if cron_manager.is_cron_active():
                cron_manager.remove_cron_job()
                # Also cancel any open orders
                if self.app.api_client:
                    executor = StrategyExecutor(self.app.api_client, self.app.db)
                    executor.cancel_all_open_orders()
                    self.app.notify("Strategy deactivated (cron removed & orders cancelled)")
                    # Give API a tiny moment to reflect cancellation before refresh
                    import time
                    time.sleep(0.5)
                else:
                    self.app.notify("Strategy deactivated (cron removed), but couldn't cancel orders (API client not ready)")
            else:
                cron_manager.add_cron_job()
                self.app.notify("Strategy activated (cron added)")
                
                # Trigger immediate run
                try:
                    # Get path to run_strategy.py relative to this file
                    # File is in dca_bot/dashboard/widgets/strategy.py
                    # We need 4 dirnames to get to root/
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                    script_path = os.path.join(base_dir, "run_strategy.py")
                    python_exe = sys.executable # Path to current venv python
                    
                    self.app.logger.info(f"Triggering initial strategy run: {python_exe} {script_path} --force")
                    self.app.notify("Executing initial run...")
                    
                    # Run it in background/subprocess
                    subprocess.Popen([python_exe, script_path, "--force"], 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL,
                                   cwd=base_dir) # Ensure correct CWD
                except Exception as run_e:
                    self.app.logger.error(f"Initial run trigger failed: {run_e}")
                    self.app.notify(f"Initial run failed: {run_e}", severity="error")
            
            self.app.action_refresh()

    def on_strategy_rule_widget_delete_request(self, message: StrategyRuleWidget.DeleteRequest) -> None:
        # If editing, just remove from UI (it will be "saved" later)
        # If not editing, delete from DB immediately
        if self.app.editing_strategy:
            message.widget.remove()
        else:
            if message.widget.rule.id is not None:
                self.app.db.delete_rule(message.widget.rule.id)
            self.app.action_refresh()

