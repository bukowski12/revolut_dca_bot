import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from revolutx_crypto_api.client import RevolutXClient
from revolutx_crypto_api.market_data.get_ticker import get_ticker
from dca_bot.strategy.config import DBConfig
from dca_bot.strategy.executor import StrategyExecutor
from dca_bot.strategy.models import CronRun

def setup_logging():
    # Get absolute path for log file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(base_dir, "dca_bot.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )

def main():
    setup_logging()
    logger = logging.getLogger("dca_bot_cron")
    
    load_dotenv()
    api_key = os.getenv("api_key")
    private_key = os.getenv("private_key")
    
    if not api_key or not private_key:
        logger.error("Missing API key or Private key in .env")
        return

    db = DBConfig()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Idempotence check
    force = "--force" in sys.argv
    if not force and db.get_cron_run_for_date(today_str):
        logger.info(f"Bot already ran today ({today_str}). Exiting. Use --force to override.")
        return
    elif force:
        logger.info("Force flag detected. Skipping idempotency check.")

    # 2. Initialize API and Executor
    try:
        client = RevolutXClient(api_key=api_key, private_key=private_key)
        executor = StrategyExecutor(client, db)
        
        # 3. Process yesterday's open orders
        executor.process_yesterday_orders()
        
        # 4. Fetch current BTC price
        # get_ticker in this library returns all tickers or needs filtering?
        # Based on get_ticker.py, it sends GET to /market-data/ticker
        tickers_resp = get_ticker(client)
        tickers = tickers_resp.get("data", []) if isinstance(tickers_resp, dict) else tickers_resp
        
        # We need BTC-EUR. In /tickers it might be BTC/EUR or BTC-EUR. 
        # Debug output showed COW/USD, so let's check for both or normalize.
        btc_eur_ticker = next((t for t in tickers if t.get("symbol") in ["BTC-EUR", "BTC/EUR"]), None)
        if not btc_eur_ticker:
            logger.error(f"Could not find BTC-EUR ticker. Available symbols: {[t.get('symbol') for t in tickers[:5]]}")
            return
            
        reference_price = float(btc_eur_ticker.get("last_price", btc_eur_ticker.get("price")))
        
        # 5. Create or Update cron run
        existing_run = db.get_cron_run_for_date(today_str)
        if existing_run:
            run_id = existing_run.id
            # Update reference price of existing run if forcing
            with db._get_connection() as conn:
                conn.execute("UPDATE cron_runs SET reference_price = ?, ran_at = datetime('now') WHERE id = ?", (reference_price, run_id))
            logger.info(f"Updated existing cron run entry (ID: {run_id})")
        else:
            cron_run = CronRun(run_date=today_str, reference_price=reference_price)
            run_id = db.create_cron_run(cron_run)
            logger.info(f"Created new cron run entry (ID: {run_id})")
        
        # 6. Execute new strategy rules
        executor.execute_new_strategy(reference_price, run_id)
        
        logger.info("Cron job finished successfully.")
        
    except Exception as e:
        logger.error(f"Fatal error during cron run: {e}")

if __name__ == "__main__":
    main()
