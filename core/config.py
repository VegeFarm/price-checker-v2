import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path('.') / '.env', override=False)

NAVER_COMMERCE_CLIENT_ID = os.getenv('NAVER_COMMERCE_CLIENT_ID', '').strip()
NAVER_COMMERCE_CLIENT_SECRET = os.getenv('NAVER_COMMERCE_CLIENT_SECRET', '').strip()
NAVER_TOKEN_TYPE = os.getenv('NAVER_TOKEN_TYPE', 'SELF').strip().upper() or 'SELF'
NAVER_ACCOUNT_ID = os.getenv('NAVER_ACCOUNT_ID', '').strip()
NAVER_USE_DISCOUNTED_PRICE = os.getenv('NAVER_USE_DISCOUNTED_PRICE', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///local.db').strip()
