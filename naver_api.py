from __future__ import annotations

import base64
import os
import time
from typing import Any

import bcrypt
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

BASE_URL = 'https://api.commerce.naver.com/external'
TOKEN_URL = f'{BASE_URL}/v1/oauth2/token'
PRODUCT_SEARCH_URL = f'{BASE_URL}/v1/products/search'

CLIENT_ID = os.getenv('NAVER_COMMERCE_CLIENT_ID', '').strip()
CLIENT_SECRET = os.getenv('NAVER_COMMERCE_CLIENT_SECRET', '').strip()
TOKEN_TYPE = (os.getenv('NAVER_TOKEN_TYPE', 'SELF').strip() or 'SELF').upper()
ACCOUNT_ID = os.getenv('NAVER_ACCOUNT_ID', '').strip()
USE_DISCOUNTED = os.getenv('NAVER_USE_DISCOUNTED_PRICE', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}


class RelayNaverError(RuntimeError):
    pass


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.7,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset({'GET', 'POST'}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def _sign(timestamp: int) -> str:
    password = f'{CLIENT_ID}_{timestamp}'.encode('utf-8')
    hashed = bcrypt.hashpw(password, CLIENT_SECRET.encode('utf-8'))
    return base64.b64encode(hashed).decode('utf-8')


def _error(response: requests.Response) -> RelayNaverError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    message = str(body.get('message', '') or response.text or '네이버 커머스 API 요청 실패').strip()
    trace_id = body.get('traceId')
    if trace_id:
        message = f'{message} (traceId: {trace_id})'
    return RelayNaverError(message)


def _token(session: requests.Session) -> str:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RelayNaverError('중계 서버의 NAVER_COMMERCE_CLIENT_ID / NAVER_COMMERCE_CLIENT_SECRET이 비어 있습니다.')
    if TOKEN_TYPE not in {'SELF', 'SELLER'}:
        raise RelayNaverError('NAVER_TOKEN_TYPE은 SELF 또는 SELLER만 사용할 수 있습니다.')
    if TOKEN_TYPE == 'SELLER' and not ACCOUNT_ID:
        raise RelayNaverError('NAVER_TOKEN_TYPE=SELLER일 때 NAVER_ACCOUNT_ID가 필요합니다.')

    timestamp = int(time.time() * 1000)
    payload: dict[str, str] = {
        'client_id': CLIENT_ID,
        'timestamp': str(timestamp),
        'grant_type': 'client_credentials',
        'client_secret_sign': _sign(timestamp),
        'type': TOKEN_TYPE,
    }
    if TOKEN_TYPE == 'SELLER':
        payload['account_id'] = ACCOUNT_ID

    response = session.post(
        TOKEN_URL,
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=20,
    )
    if not response.ok:
        raise _error(response)
    token = str(response.json().get('access_token', '') or '').strip()
    if not token:
        raise RelayNaverError('네이버 인증 응답에 access_token이 없습니다.')
    return token


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def fetch_products(page_size: int = 500, max_pages: int = 200) -> list[dict[str, Any]]:
    session = _session()
    token = _token(session)
    products: list[dict[str, Any]] = []
    page = 1

    while page <= max_pages:
        response = session.post(
            PRODUCT_SEARCH_URL,
            json={'page': page, 'size': min(max(page_size, 1), 500), 'orderType': 'NO'},
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json;charset=UTF-8',
            },
            timeout=30,
        )
        if not response.ok:
            raise _error(response)
        data = response.json()

        contents = data.get('contents') or data.get('content') or []
        for origin in contents:
            if not isinstance(origin, dict):
                continue
            origin_no = str(origin.get('originProductNo', '') or '')
            for channel in origin.get('channelProducts') or []:
                if not isinstance(channel, dict):
                    continue
                if channel.get('channelServiceType') not in (None, '', 'STOREFARM'):
                    continue
                sale_price = _safe_int(channel.get('salePrice'))
                discounted_price = _safe_int(channel.get('discountedPrice'))
                products.append({
                    'name': str(channel.get('name', '') or '').strip(),
                    'channel_product_no': str(channel.get('channelProductNo', '') or ''),
                    'origin_product_no': str(channel.get('originProductNo', '') or origin_no),
                    'seller_management_code': str(channel.get('sellerManagementCode', '') or '').strip(),
                    'sale_price': sale_price,
                    'discounted_price': discounted_price,
                    'effective_price': discounted_price if USE_DISCOUNTED and discounted_price and discounted_price > 0 else sale_price,
                    'status_type': str(channel.get('statusType', '') or '').strip(),
                })

        total_pages = _safe_int(data.get('totalPages'))
        if bool(data.get('last', False)) or (total_pages is not None and page >= total_pages):
            break
        if not contents:
            break
        page += 1

    if page > max_pages:
        raise RelayNaverError(f'상품 페이지가 {max_pages}페이지를 초과하여 중단했습니다.')
    return products
