import os
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
import asyncio
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bot import TwitchBot
from features.commands.analytics import AnalyticsCommands
from features.commands.base import BaseCommands
from features.points.commands import PointsCommands
from config.config import Config
from database.manager import initialize_database

def setup_logging():
    """Configure logging for the bot"""
    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    file_handler = RotatingFileHandler(
        filename=f'logs/bot_{datetime.now().strftime("%Y-%m-%d")}.log',
        maxBytes=5000000,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(log_format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def validate_environment():
    """Validate that all required environment variables are set"""
    try:
        Config.validate()
    except ValueError as e:
        logging.critical(f"Configuration error: {e}")
        sys.exit(1)

def setup_signal_handlers(bot):
    """Set up signal handlers for graceful shutdown"""
    import signal
    
    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

def handle_signals(bot):
    """Set up signal handlers for graceful shutdown"""
    def signal_handler(*args):
        asyncio.create_task(shutdown(bot))
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal_handler)

async def shutdown(bot, signal_received=None):
    """Handle graceful shutdown"""
    if signal_received:
        logging.info(f"Received signal: {signal_received}")
    logging.info("Initiating shutdown sequence...")
    await bot.close()

async def main():
    """Main entry point for the bot"""
    try:
        # Set up logging
        setup_logging()
        logging.info("Starting bot...")

        # Validate environment
        validate_environment()

        # Initialize database
        await initialize_database("sqlite+aiosqlite:///bot.db")

        # Initialize bot
        bot = TwitchBot()
        
        # Set up signal handlers
        handle_signals(bot)
        
        # Start the bot
        logging.info("Bot initialized, connecting to Twitch...")
        await bot.start()

    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        if 'bot' in locals():
            try:
                await bot.close()
            except Exception as close_error:
                logging.error(f"Error during bot shutdown: {close_error}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutdown initiated by user")
    except Exception as e:
        logging.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)