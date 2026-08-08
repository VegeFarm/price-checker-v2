import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path('.') / '.env', override=False)

NAVER_COMMERCE_CLIENT_ID = os.getenv('NAVER_COMMERCE_CLIENT_ID', '').strip()
NAVER_COMMERCE_CLIENT_SECRET = os.getenv('NAVER_COMMERCE_CLIENT_SECRET', '').strip()
NAVER_TOKEN_TYPE = os.getenv('NAVER_TOKEN_TYPE', 'SELF').strip().upper() or 'SELF'
NAVER_ACCOUNT_ID = os.getenv('NAVER_ACCOUNT_ID', '').strip()
NAVER_USE_DISCOUNTED_PRICE = os.getenv('NAVER_USE_DISCOUNTED_PRICE', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}

# 기존 재고자동화와 같은 중계 서버 규격을 사용합니다.
# RELAY_BASE_URL + RELAY_SHARED_TOKEN이 있으면 Render는 네이버를 직접 호출하지 않고
# 기존 중계 서버의 /naver/products/search 엔드포인트를 호출합니다.
# 예전 V2 환경변수(NAVER_RELAY_URL/NAVER_RELAY_KEY)도 호환용으로 계속 인식합니다.
RELAY_BASE_URL = (os.getenv('RELAY_BASE_URL') or os.getenv('NAVER_RELAY_URL') or '').strip().rstrip('/')
RELAY_SHARED_TOKEN = (os.getenv('RELAY_SHARED_TOKEN') or os.getenv('NAVER_RELAY_KEY') or '').strip()
RELAY_TIMEOUT = int((os.getenv('RELAY_TIMEOUT') or os.getenv('NAVER_RELAY_TIMEOUT') or '90').strip() or '90')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///local.db').strip()
