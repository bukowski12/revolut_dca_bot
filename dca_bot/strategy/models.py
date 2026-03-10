from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class StrategyRule:
    id: Optional[int] = None
    drop_pct: int = 0
    amount_eur: int = 0
    always_run: bool = False
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class CronRun:
    id: Optional[int] = None
    run_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    reference_price: float = 0.0
    ran_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Order:
    id: Optional[int] = None
    run_id: Optional[int] = None
    rule_id: Optional[int] = None
    order_type: str = "limit"  # 'limit' | 'market'
    trigger_reason: str = "limit_placed"  # 'limit_placed' | 'always_run'
    amount_eur: float = 0.0
    limit_price: Optional[float] = None
    btc_price: Optional[float] = None
    btc_amount: Optional[float] = None
    revolut_order_id: Optional[str] = None
    status: str = "open"  # 'open'|'filled'|'cancelled'|'failed'
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
