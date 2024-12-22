from dotenv import load_dotenv
from tradingview_ta import TA_Handler
import asyncio
from datetime import datetime
import logging
from telegram.ext import ApplicationBuilder, Application, JobQueue
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
import json
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bollinger_bands.log"), logging.StreamHandler()],
)

load_dotenv()

# Telegram Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Store active monitoring sessions
SESSIONS_FILE = "active_sessions.json"

# Function to load sessions from file
def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, 'r') as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Error loading sessions: {e}")
    return set()

# Function to save sessions to file
def save_sessions(sessions):
    try:
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(list(sessions), f)
    except Exception as e:
        logging.error(f"Error saving sessions: {e}")

class BollingerBandAlert:
    def __init__(self, symbol, exchange="OKX", screener="crypto", interval="1h"):
        self.symbol = symbol
        self.exchange = exchange
        self.screener = screener
        self.interval = interval

    def get_analysis(self):
        handler = TA_Handler(
            symbol=self.symbol,
            exchange=self.exchange,
            screener=self.screener,
            interval=self.interval,
        )
        return handler.get_analysis()

    async def check_signals(self, context: ContextTypes.DEFAULT_TYPE, chat_id: str):
        try:
            analysis = self.get_analysis()
            logging.info(f"Checking signals for {self.symbol}")

            # Get indicators
            indicators = analysis.indicators
            current_price = indicators["close"]
            bb_upper = indicators["BB.upper"]
            bb_lower = indicators["BB.lower"]
            rsi = indicators["RSI"]

            # Strong SHORT signal
            if current_price >= bb_upper and rsi >= 70:
                message = (
                    f"🔴 {self.symbol} SHORT SIGNAL!\n\n"
                    f"💰 Current Price: ${current_price:,.2f}\n"
                    f"📊 BB Upper: ${bb_upper:,.2f}\n"
                    f"📈 RSI (14): {rsi:.2f}\n\n"
                    f"⚠️ Overbought conditions detected!\n"
                    f"📉 Potential reversal opportunity"
                )
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=message, 
                    parse_mode="HTML"
                )

            # Strong LONG signal
            elif current_price <= bb_lower and rsi <= 30:
                message = (
                    f"🟢 {self.symbol} LONG SIGNAL!\n\n"
                    f"💰 Current Price: ${current_price:,.2f}\n"
                    f"📊 BB Lower: ${bb_lower:,.2f}\n"
                    f"📈 RSI (14): {rsi:.2f}\n\n"
                    f"⚠️ Oversold conditions detected!\n"
                    f"📈 Potential reversal opportunity"
                )
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=message, 
                    parse_mode="HTML"
                )

        except Exception as e:
            logging.error(f"Error monitoring {self.symbol}: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    
    await update.message.reply_text(
        f"👋 Welcome {user_name} to the Crypto Alert Bot! 🤖\n\n"
        "🎯 Available Commands:\n"
        "▶️ /start_monitoring - Begin tracking crypto pairs\n"
        "⏹️ /stop_monitoring - Stop tracking\n"
        "❓ /help - Show all commands\n\n"
        "🔔 Start monitoring to receive price alerts!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎯 Available Commands:\n\n"
        "👋 /start - Restart the bot\n"
        "▶️ /start_monitoring - Begin tracking crypto pairs\n"
        "⏹️ /stop_monitoring - Stop tracking\n"
        "❓ /help - Show this help message\n\n"
        "📊 The bot monitors:\n"
        "• BTC/USDT\n"
        "• ETH/USDT\n\n"
        "📈 Signals are based on:\n"
        "• Bollinger Bands\n"
        "• RSI Indicator"
    )

async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    # Check if already monitoring
    if chat_id in active_sessions:
        await update.message.reply_text("⚠️ Monitoring is already active!")
        return
    
    # Create monitors for different crypto pairs
    monitors = [BollingerBandAlert("BTCUSDT"), BollingerBandAlert("ETHUSDT")]
    
    # Store monitors in context
    context.chat_data['monitors'] = monitors
    
    # Schedule the monitoring job
    job = context.job_queue.run_repeating(
        check_all_signals, 
        interval=60,
        first=1,
        chat_id=chat_id,
        data={'monitors': monitors, 'chat_id': chat_id}
    )
    context.chat_data['monitoring_job'] = job
    
    # Add to active sessions and save
    active_sessions.add(chat_id)
    save_sessions(active_sessions)
    
    await update.message.reply_text(
        "✅ Started monitoring crypto pairs!\n\n"
        "🔍 Tracking:\n"
        "• BTC/USDT\n"
        "• ETH/USDT\n\n"
        "⏰ Checking every minute for:\n"
        "📈 Long opportunities\n"
        "📉 Short opportunities\n\n"
        "🔔 You'll receive alerts when signals appear!"
    )
    logging.info(f"Started monitoring for chat_id: {chat_id}")

async def stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    if chat_id in active_sessions:
        if 'monitoring_job' in context.chat_data:
            context.chat_data['monitoring_job'].schedule_removal()
            del context.chat_data['monitoring_job']
        active_sessions.remove(chat_id)
        save_sessions(active_sessions)
        await update.message.reply_text(
            "🛑 Monitoring stopped!\n\n"
            "▶️ Use /start_monitoring to resume tracking"
        )
        logging.info(f"Stopped monitoring for chat_id: {chat_id}")
    else:
        await update.message.reply_text(
            "⚠️ No active monitoring to stop!\n\n"
            "▶️ Use /start_monitoring to begin tracking"
        )

async def check_all_signals(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    monitors = job_data['monitors']
    chat_id = job_data['chat_id']
    
    # Only process if the session is still active
    if chat_id in active_sessions:
        for monitor in monitors:
            await monitor.check_signals(context, chat_id)

async def main():
    # Load saved sessions
    global active_sessions
    active_sessions = load_sessions()
    
    # Initialize the application with job queue
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    
    # Initialize job queue
    job_queue = JobQueue()
    job_queue.set_application(application)
    
    # Add command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('start_monitoring', start_monitoring))
    application.add_handler(CommandHandler('stop_monitoring', stop_monitoring))
    
    # Start monitoring for all saved sessions
    for chat_id in active_sessions:
        monitors = [BollingerBandAlert("BTCUSDT"), BollingerBandAlert("ETHUSDT")]
        job_queue.run_repeating(
            check_all_signals,
            interval=60,
            first=1,
            chat_id=chat_id,
            data={'monitors': monitors, 'chat_id': chat_id}
        )
    
    # Initialize and start everything
    await application.initialize()
    await job_queue.start()
    await application.start()
    await application.updater.start_polling()
    
    try:
        # Keep the application running indefinitely
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Handle graceful shutdown
        logging.info("Shutting down...")
        await application.stop()
        await job_queue.stop()

if __name__ == '__main__':
    asyncio.run(main())

