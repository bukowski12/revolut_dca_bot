import sqlite3
import os
from typing import List, Optional
from .models import StrategyRule, CronRun, Order

class DBConfig:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Get the directory of this file (dca_bot/strategy/)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, "dca_bot", "db", "dca.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # strategy_rules
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                drop_pct    INTEGER NOT NULL,
                amount_eur  INTEGER NOT NULL,
                always_run  INTEGER NOT NULL DEFAULT 0,
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """)

            # Migration for strategy_rules: Convert drop_pct and amount_eur from REAL to INTEGER
            cursor.execute("PRAGMA table_info(strategy_rules)")
            columns = cursor.fetchall()
            
            needs_migration = False
            for col in columns:
                if col[1] == 'drop_pct' and col[2] == 'REAL':
                    needs_migration = True
                    break
                if col[1] == 'amount_eur' and col[2] == 'REAL':
                    needs_migration = True
                    break

            if needs_migration:
                print("Migrating strategy_rules table: changing drop_pct and amount_eur to INTEGER.")
                # 1. Rename the old table
                cursor.execute("ALTER TABLE strategy_rules RENAME TO old_strategy_rules")

                # 2. Create the new table with the correct schema (already done by the CREATE TABLE IF NOT EXISTS above,
                # but we re-execute it here to ensure it's created if it was dropped for some reason, or if this is the first run)
                cursor.execute("""
                CREATE TABLE strategy_rules (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    drop_pct    INTEGER NOT NULL,
                    amount_eur  INTEGER NOT NULL,
                    always_run  INTEGER NOT NULL DEFAULT 0,
                    active      INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT DEFAULT (datetime('now'))
                )
                """)

                # 3. Copy data from the old table to the new table, casting REAL to INTEGER
                cursor.execute("""
                INSERT INTO strategy_rules (id, drop_pct, amount_eur, always_run, active, created_at)
                SELECT id, CAST(drop_pct AS INTEGER), CAST(amount_eur AS INTEGER), always_run, active, created_at
                FROM old_strategy_rules
                """)

                # 4. Drop the old table
                cursor.execute("DROP TABLE old_strategy_rules")
                print("Migration complete for strategy_rules.")
            
            # cron_runs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cron_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date        TEXT NOT NULL UNIQUE,
                reference_price REAL NOT NULL,
                ran_at          TEXT DEFAULT (datetime('now'))
            )
            """)
            
            # orders
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id           INTEGER REFERENCES cron_runs(id),
                rule_id          INTEGER REFERENCES strategy_rules(id),
                order_type       TEXT NOT NULL,
                trigger_reason   TEXT NOT NULL,
                amount_eur       REAL NOT NULL,
                limit_price      REAL,
                btc_price        REAL,
                btc_amount       REAL,
                revolut_order_id TEXT,
                status           TEXT DEFAULT 'open',
                created_at       TEXT DEFAULT (datetime('now'))
            )
            """)

            # settings
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            )
            """)
            
            # Default settings
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('order_frequency', 'daily')")

            conn.commit()

    def get_active_rules(self) -> List[StrategyRule]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM strategy_rules WHERE active = 1")
            return [StrategyRule(**dict(row)) for row in cursor.fetchall()]

    def add_rule(self, rule: StrategyRule):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO strategy_rules (drop_pct, amount_eur, always_run, active)
            VALUES (?, ?, ?, ?)
            """, (rule.drop_pct, rule.amount_eur, 1 if rule.always_run else 0, 1 if rule.active else 1))
            conn.commit()

    def get_cron_run_for_date(self, date_str: str) -> Optional[CronRun]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cron_runs WHERE run_date = ?", (date_str,))
            row = cursor.fetchone()
            return CronRun(**dict(row)) if row else None

    def create_cron_run(self, cron_run: CronRun) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO cron_runs (run_date, reference_price)
            VALUES (?, ?)
            """, (cron_run.run_date, cron_run.reference_price))
            conn.commit()
            return cursor.lastrowid

    def get_open_orders(self) -> List[Order]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE status IN ('open', 'new', 'pending')")
            return [Order(**dict(row)) for row in cursor.fetchall()]

    def update_rule(self, rule: StrategyRule):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE strategy_rules SET 
                drop_pct = ?, 
                amount_eur = ?, 
                always_run = ?,
                active = ?
            WHERE id = ?
            """, (rule.drop_pct, rule.amount_eur, 1 if rule.always_run else 0, 1 if rule.active else 0, rule.id))
            conn.commit()

    def delete_rule(self, rule_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM strategy_rules WHERE id = ?", (rule_id,))
            conn.commit()

    def update_order(self, order: Order):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE orders SET 
                btc_price = ?, 
                btc_amount = ?, 
                status = ?,
                revolut_order_id = ?
            WHERE id = ?
            """, (order.btc_price, order.btc_amount, order.status, order.revolut_order_id, order.id))
            conn.commit()

    def create_order(self, order: Order):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO orders (run_id, rule_id, order_type, trigger_reason, amount_eur, limit_price, revolut_order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (order.run_id, order.rule_id, order.order_type, order.trigger_reason, 
                  order.amount_eur, order.limit_price, order.revolut_order_id, order.status))
            conn.commit()

    def clear_rules(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM strategy_rules")
            conn.commit()

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
