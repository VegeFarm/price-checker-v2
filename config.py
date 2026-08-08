import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path('.') / '.env', override=False)

NAVER_COMMERCE_CLIENT_ID = os.getenv('NAVER_COMMERCE_CLIENT_ID', '').strip()
NAVER_COMMERCE_CLIENT_SECRET = os.getenv('NAVER_COMMERCE_CLIENT_SECRET', '').strip()
NAVER_TOKEN_TYPE = os.getenv('NAVER_TOKEN_TYPE', 'SELF').strip().upper() or 'SELF'
NAVER_ACCOUNT_ID = os.getenv('NAVER_ACCOUNT_ID', '').strip()
NAVER_USE_DISCOUNTED_PRICE = os.getenv('NAVER_USE_DISCOUNTED_PRICE', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}

# Render처럼 호출 IP가 유동적인 환경에서는, 네이버에 이미 허용된 고정 IP 서버를
# 중계(relay)로 사용할 수 있습니다. NAVER_RELAY_URL이 있으면 직접 네이버 API를
# 호출하지 않고 중계 서버를 통해 상품 목록을 가져옵니다.
NAVER_RELAY_URL = os.getenv('NAVER_RELAY_URL', '').strip().rstrip('/')
NAVER_RELAY_KEY = os.getenv('NAVER_RELAY_KEY', '').strip()
NAVER_RELAY_TIMEOUT = int(os.getenv('NAVER_RELAY_TIMEOUT', '90').strip() or '90')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///local.db').strip()
