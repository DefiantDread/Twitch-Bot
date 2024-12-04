# config/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv('TWITCH_BOT_TOKEN')
    CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
    CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
    BOT_PREFIX = os.getenv('BOT_PREFIX', '!')
    CHANNEL_NAME = os.getenv('CHANNEL_NAME')
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
    
    # Feature Flags
    ENABLE_MODERATION = os.getenv('ENABLE_MODERATION', 'True').lower() == 'true'
    ENABLE_CUSTOM_COMMANDS = os.getenv('ENABLE_CUSTOM_COMMANDS', 'True').lower() == 'true'
    
    # Moderation Settings
    MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', 500))
    LINK_PROTECTION = os.getenv('LINK_PROTECTION', 'True').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required_fields = ['BOT_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET', 'CHANNEL_NAME']
        missing_fields = [field for field in required_fields if not getattr(cls, field)]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")