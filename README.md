# Revolut DCA Bot

A fully automated, customizable **Dollar Cost Averaging (DCA)** bot built for the **Revolut X API**. This bot helps you gradually build your cryptocurrency portfolio securely and consistently, with intelligent features for both regular recurring buys and opportunistic buying on price dips.

The bot includes a beautiful **TUI (Text-Based User Interface) dashboard** that runs directly in your terminal, making it easy to manage your investment strategies, track your current portfolio, and review past orders.

## Features

- **TUI Dashboard:** A sleek, fully featured terminal-based dashboard built with `textual` for real-time portfolio management. 
- **Chart Visualizations:** View pricing charts drawn right in your terminal with `plotext`.
- **Customizable Strategy:** Define your custom DCA strategy depending on price drops or fixed intervals (daily, weekly, monthly).
- **Rule-Based Execution:** Set multiple rules (e.g., "Buy €10 if price drops by 5%", "Buy €20 if price drops by 10%").
- **Fixed Frequency Fallback:** Option to execute a market order at the end of your frequency period (e.g., the end of the day or week) if the targeted price drop did not occur, ensuring you never miss a DCA cycle.
- **Idempotency checks:** Prevents identical orders from firing multiple times in a single cycle. Includes a `--force` flag for immediate manual triggering.
- **Background Automation:** Seamless cron job management directly from the dashboard to run your strategy automatically in the background.

## Technology Stack

- **Python 3.x**
- [revolutx-crypto-api](https://github.com/bukowski12/revolutx_crypto_api) (API Wrapper for Revolut X)
- [Textual](https://github.com/Textualize/textual) (TUI framework)
- [Plotext](https://github.com/piccolomo/plotext) (Terminal plotting library)

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repository-url>
   cd revolut_dca_bot
   ```

2. **Create a virtual environment & install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Setup:**
   Create a `.env` file in the project root containing your **Revolut X** API and Private keys.
   ```env
   api_key=your_revolut_api_key_here
   private_key=your_revolut_private_key_here
   ```

## Usage

### 1. Launching the Dashboard

To view your portfolio, monitor charts, and configure your DCA strategy, launch the Textual dashboard:

```bash
python run_dashboard.py
```

From inside the dashboard, you can:
- **View balances:** See your total, available, and reserved balances.
- **Manage Strategy:** Add new tiered buying rules based on price drop percentages and set your order frequency.
- **Activate/Deactivate Bot:** Add or remove the background cron job that automates the execution of your strategy.

### 2. Manual Strategy Execution

You can run your DCA strategy manually without the dashboard or the background cron job:

```bash
python run_strategy.py
```

If you wish to bypass the idempotency checks (which restrict the bot from running again if it has already successfully completed its run for the current frequency window):

```bash
python run_strategy.py --force
```

## How It Works

1. **Idempotency:** When the `run_strategy.py` script starts, it first checks a local SQLite database to see if it has already run successfully for the scheduled period. If it has, it exits smoothly (unless forced).
2. **Current Price Eval:** The bot fetches the current market prices (e.g. `BTC-EUR`) via the Revolut X client.
3. **Execution Logic:** It then assesses the price change and checks against your active rules. Limit matching orders are placed via Revolut, and leftover un-executed "Always" fallbacks are safely evaluated.
4. **Log Tracing:** All background operations are thoroughly logged to `dca_bot.log` and dashboard actions to `dashboard.log`.

## Contributing

Contributions, issues, and feature requests are welcome!

## License

[MIT License](LICENSE)
