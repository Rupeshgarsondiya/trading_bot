📈 Binance Futures Testnet Trading Bot
Author: Rupesh Garsondiya

This is a simplified crypto trading bot built for the
Junior Python Developer – Crypto Trading Bot assignment.

🚀 Features
1. Market Orders
python3 basic_bot.py --api-key <KEY> --api-secret <SECRET> market --symbol BTCUSDT --side BUY --qty 0.002

2. Limit Orders
python3 basic_bot.py --api-key <KEY> --api-secret <SECRET> limit --symbol BTCUSDT --side SELL --qty 0.002 --price 90000 --tif GTC

3. TWAP Strategy (Bonus)

Executes multiple market slices over time.

python3 basic_bot.py --api-key <KEY> --api-secret <SECRET> twap --symbol BTCUSDT --side BUY --total-qty 0.008 --slices 4 --duration 12

🧱 Project Structure
trading-bot/
│ basic_bot.py
│ README.md
│ requirements.txt
│ .gitignore
│ logs/
│   basicbot.log
│ screenshots/
│   market_order.png
│   limit_order.png
│   twap_orders.png

📝 Logging

All API requests, responses, and errors are logged to:

basicbot.log


This file is included in /logs folder for review.

🛠 Installation
pip install -r requirements.txt

🧪 Testing Example
python3 basic_bot.py --api-key <KEY> --api-secret <SECRET> info
