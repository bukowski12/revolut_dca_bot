# DCA Bot – BTC nákup na Revolut X

## Přehled projektu
Terminálový DCA (Dollar Cost Averaging) bot pro automatický nákup BTC na burze Revolut X.
Skládá se ze dvou částí:
- **Cron skript** – spouští se jednou denně, vyhodnotí strategii a provede nákupy
- **TUI dashboard** – interaktivní přehled v terminálu (Textual)

---

## Tech stack

| Účel | Knihovna |
|------|----------|
| TUI framework | `textual` |
| Candlestick graf | `plotext` |
| Revolut X API | `revolutx-crypto-api` (vlastní wrapper) |
| DB | `sqlite3` (built-in) |
| Env proměnné | `python-dotenv` |

---

## Struktura projektu

```
revolutx_crypto_api/          # existující repo
├── src/                      # Revolut API wrapper (beze změny)
├── pyproject.toml            # přidat – aby šel nainstalovat přes pip
├── dca_bot/
│   ├── db/
│   │   └── dca.db            # SQLite databáze
│   ├── strategy/
│   │   ├── models.py         # dataclassy pro strategii
│   │   ├── config.py         # čtení/zápis strategie z DB
│   │   └── executor.py       # logika vyhodnocení + spuštění nákupů
│   ├── dashboard/
│   │   ├── app.py            # Textual hlavní app
│   │   └── widgets/
│   │       ├── chart.py      # candlestick graf (plotext)
│   │       ├── balance.py    # výpis balance z burzy
│   │       ├── strategy.py   # zobrazení + inline editace strategie
│   │       └── orders.py     # aktivní + historické objednávky
│   ├── run_strategy.py       # entry point pro cron
│   ├── run_dashboard.py      # entry point pro TUI
│   └── requirements.txt
└── .env
```

---

## SQLite schéma

### Tabulka `strategy_rules`
```sql
CREATE TABLE strategy_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    drop_pct    REAL NOT NULL,      -- pokles v % (např. 3.0)
    amount_eur  REAL NOT NULL,      -- částka v EUR (např. 20.0)
    always_run  INTEGER NOT NULL DEFAULT 0,  -- 0/1 (provést vždy)
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);
```

### Tabulka `cron_runs`
```sql
CREATE TABLE cron_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date        TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD (idempotence)
    reference_price REAL NOT NULL,          -- cena BTC při spuštění
    ran_at          TEXT DEFAULT (datetime('now'))
);
```

### Tabulka `orders`
```sql
CREATE TABLE orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           INTEGER REFERENCES cron_runs(id),
    rule_id          INTEGER REFERENCES strategy_rules(id),
    order_type       TEXT NOT NULL,          -- 'limit' | 'market'
    trigger_reason   TEXT NOT NULL,          -- 'limit_placed' | 'always_run'
    amount_eur       REAL NOT NULL,
    limit_price      REAL,                   -- cílová cena pro limit order
    btc_price        REAL,                   -- skutečná cena plnění
    btc_amount       REAL,                   -- kolik BTC nakoupeno
    revolut_order_id TEXT,                   -- ID z Revolut API
    status           TEXT DEFAULT 'open',    -- 'open'|'filled'|'cancelled'|'failed'
    created_at       TEXT DEFAULT (datetime('now'))
);
```

---

## Logika cronu (`run_strategy.py`)

```
1. Zkontroluj tabulku cron_runs pro dnešní datum → pokud existuje, EXIT

2. VYŘÍZENÍ VČEREJŠÍCH ORDERŮ:
   Načti z DB všechny limit ordery se statusem 'open' (z předchozího dne)
   Pro každý:
     a. Zkontroluj status na burze přes Revolut API (podle revolut_order_id)
     b. Pokud 'filled':
        → aktualizuj status v DB na 'filled', zaznamenej btc_amount
     c. Pokud stále 'open' (nesplněn):
        → zruš order na burze (cancel order)
        → aktualizuj status v DB na 'cancelled'
        → pokud pravidlo má always_run=1:
           → market order za amount_eur, zapiš do DB jako 'filled'

3. NOVÉ ORDERY PRO DNEŠEK:
   Načti aktuální cenu BTC = reference_price
   Ulož nový záznam do cron_runs (datum, reference_price)
   Načti aktivní strategy_rules (active=1)
   Pro každé pravidlo:
     → vypočítej limit_price = reference_price * (1 - drop_pct / 100)
     → zadej limit order na burze za amount_eur na ceně limit_price
     → ulož do DB (status='open', revolut_order_id z odpovědi API)

4. Výsledek vypiš do stdout (pro cron log)
```

---

## Layout TUI dashboardu

```
┌─────────────────────────────────┬───────────────┐
│                                 │   BALANCE     │
│      CANDLESTICK GRAF           │   EUR: 500    │
│         (plotext)               │   BTC: 0.021  │
│                                 │───────────────│
│                                 │   STRATEGIE   │
│                                 │   [E] editovat│
│                                 │               │
│                                 │   3% → 20 EUR │
│                                 │   5% → 50 EUR │
│                                 │        [✓]vždy│
└─────────────────────────────────┴───────────────┘
│          OBJEDNÁVKY (aktivní + historické)       │
│  datum      důvod        EUR    BTC      status  │
│  2025-02-20 drop_condition 20  0.00023  filled   │
│  2025-02-19 always_run     50  0.00058  filled   │
└─────────────────────────────────────────────────┘
```

Poměry: levý panel 2/3, pravý panel 1/3, spodní panel 1/3 výšky.

---

## Inline editace strategie

Klávesové zkratky v panelu strategie:
- `E` – přepne do režimu editace (Static → Input widgety)
- `Enter` – uloží změny do DB
- `Esc` – zruší editaci
- `+` – přidá nové pravidlo
- `-` – odebere označené pravidlo
- `Tab` – přesun mezi poli

Editační režim:
```
STRATEGIE  (editace – Enter uloží, Esc zruší)
─────────────────────────────────────────────
Pravidlo 1:  pokles [_3_]%  →  [_20_] EUR  [ ] vždy
Pravidlo 2:  pokles [_5_]%  →  [_50_] EUR  [✓] vždy
─────────────────────────────────────────────
[Enter] Uložit  [Esc] Zrušit  [+] Přidat  [-] Odebrat
```

---

## pyproject.toml (přidat do rootu repozitáře)

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "revolutx-crypto-api"
version = "0.1.0"
description = "Revolut X Crypto API wrapper"
requires-python = ">=3.10"
dependencies = [
    "requests",
    "python-dotenv",
    "cryptography",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]
```

---

## dca_bot/requirements.txt

```
revolutx-crypto-api @ git+https://github.com/bukowski12/revolutx_crypto_api.git
textual>=0.47.0
plotext>=5.2.0
python-dotenv>=1.0.0
```

---

## .env

```
api_key=YOUR_API_KEY
private_key=YOUR_PRIVATE_KEY_BASE64_OR_HEX
```

---

## Cron nastavení (příklad)

```bash
# Každý den v 9:00
0 9 * * * cd /path/to/revolutx_crypto_api && python dca_bot/run_strategy.py >> /var/log/dca_bot.log 2>&1
```

---

## Pořadí implementace

1. `pyproject.toml` – zpřístupnění API wrapperu přes pip
2. `db/` + SQLite schéma – základ pro všechno ostatní
3. `strategy/models.py` + `config.py` – datové modely
4. `run_strategy.py` – cron logika (jádro botu)
5. `dashboard/widgets/` – jednotlivé widgety
6. `dashboard/app.py` – složení TUI dohromady
