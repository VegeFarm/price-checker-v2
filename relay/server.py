from __future__ import annotations

import hmac
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException

load_dotenv()

from naver_api import RelayNaverError, fetch_products  # noqa: E402

RELAY_SHARED_KEY = os.getenv('RELAY_SHARED_KEY', '').strip()

app = FastAPI(title='Price Checker Naver Fixed-IP Relay', docs_url=None, redoc_url=None)


def _authorize(x_relay_key: str | None) -> None:
    if not RELAY_SHARED_KEY:
        raise HTTPException(status_code=500, detail='RELAY_SHARED_KEY가 설정되지 않았습니다.')
    if not x_relay_key or not hmac.compare_digest(x_relay_key, RELAY_SHARED_KEY):
        raise HTTPException(status_code=401, detail='중계 서버 인증키가 올바르지 않습니다.')


@app.get('/health')
def health() -> dict[str, bool]:
    return {'ok': True}


@app.get('/v1/products')
def products(x_relay_key: str | None = Header(default=None)) -> dict:
    _authorize(x_relay_key)
    try:
        items = fetch_products()
        return {'count': len(items), 'products': items}
    except RelayNaverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
