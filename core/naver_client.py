from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

try:
    import bcrypt
except ImportError:  # requirements 설치 전에도 모듈 구조 확인 가능
    bcrypt = None

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import (
    NAVER_ACCOUNT_ID,
    NAVER_COMMERCE_CLIENT_ID,
    NAVER_COMMERCE_CLIENT_SECRET,
    NAVER_TOKEN_TYPE,
    NAVER_USE_DISCOUNTED_PRICE,
)

BASE_URL = 'https://api.commerce.naver.com/external'
TOKEN_URL = f'{BASE_URL}/v1/oauth2/token'
PRODUCT_SEARCH_URL = f'{BASE_URL}/v1/products/search'


class MissingNaverCredentialsError(RuntimeError):
    pass


class NaverCommerceAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, code: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class CommerceProduct:
    name: str
    channel_product_no: str
    origin_product_no: str
    seller_management_code: str
    sale_price: int | None
    discounted_price: int | None
    status_type: str

    @property
    def effective_price(self) -> int | None:
        if NAVER_USE_DISCOUNTED_PRICE and self.discounted_price and self.discounted_price > 0:
            return self.discounted_price
        return self.sale_price


def generate_client_secret_sign(client_id: str, client_secret: str, timestamp: int) -> str:
    if bcrypt is None:
        raise RuntimeError('bcrypt 패키지가 없습니다. pip install -r requirements.txt를 실행해 주세요.')
    password = f'{client_id}_{timestamp}'.encode('utf-8')
    hashed = bcrypt.hashpw(password, client_secret.encode('utf-8'))
    return base64.b64encode(hashed).decode('utf-8')


def _safe_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _error_from_response(response: requests.Response) -> NaverCommerceAPIError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    code = str(body.get('code', ''))
    message = str(body.get('message', '')).strip() or response.text.strip() or '네이버 커머스 API 요청에 실패했습니다.'
    trace_id = body.get('traceId')
    if trace_id:
        message = f'{message} (traceId: {trace_id})'
    return NaverCommerceAPIError(message, status_code=response.status_code, code=code)


def create_http_session() -> requests.Session:
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
    session.headers.update({'Accept': 'application/json;charset=UTF-8'})
    return session


class NaverCommerceClient:
    def __init__(
        self,
        client_id: str = NAVER_COMMERCE_CLIENT_ID,
        client_secret: str = NAVER_COMMERCE_CLIENT_SECRET,
        token_type: str = NAVER_TOKEN_TYPE,
        account_id: str = NAVER_ACCOUNT_ID,
        session: requests.Session | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise MissingNaverCredentialsError(
                'NAVER_COMMERCE_CLIENT_ID / NAVER_COMMERCE_CLIENT_SECRET 환경변수를 먼저 넣어주세요.'
            )
        token_type = token_type.upper()
        if token_type not in {'SELF', 'SELLER'}:
            raise ValueError('NAVER_TOKEN_TYPE은 SELF 또는 SELLER만 사용할 수 있습니다.')
        if token_type == 'SELLER' and not account_id:
            raise ValueError('NAVER_TOKEN_TYPE=SELLER일 때 NAVER_ACCOUNT_ID가 필요합니다.')

        self.client_id = client_id
        self.client_secret = client_secret
        self.token_type = token_type
        self.account_id = account_id
        self.session = session or create_http_session()
        self._access_token = ''
        self._token_expires_at = 0.0

    def get_access_token(self, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._access_token and now < self._token_expires_at - 300:
            return self._access_token

        timestamp = int(now * 1000)
        payload = {
            'client_id': self.client_id,
            'timestamp': str(timestamp),
            'grant_type': 'client_credentials',
            'client_secret_sign': generate_client_secret_sign(
                self.client_id, self.client_secret, timestamp
            ),
            'type': self.token_type,
        }
        if self.token_type == 'SELLER':
            payload['account_id'] = self.account_id

        response = self.session.post(
            TOKEN_URL,
            data=payload,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=20,
        )
        if not response.ok:
            raise _error_from_response(response)

        data = response.json()
        token = str(data.get('access_token', '')).strip()
        if not token:
            raise NaverCommerceAPIError('네이버 인증 응답에 access_token이 없습니다.')
        expires_in = _safe_int(data.get('expires_in')) or 10800
        self._access_token = token
        self._token_expires_at = now + expires_in
        return token

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(2):
            token = self.get_access_token(force_refresh=attempt > 0)
            response = self.session.post(
                url,
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                timeout=30,
            )
            if response.status_code == 401 and attempt == 0:
                try:
                    code = str(response.json().get('code', ''))
                except ValueError:
                    code = ''
                if code == 'GW.AUTHN' or not code:
                    continue
            if not response.ok:
                raise _error_from_response(response)
            return response.json()
        raise NaverCommerceAPIError('네이버 인증 토큰 갱신 후에도 요청이 거부되었습니다.', status_code=401)

    def list_products(self, page_size: int = 500, max_pages: int = 200) -> list[CommerceProduct]:
        products: list[CommerceProduct] = []
        page = 1
        while page <= max_pages:
            data = self._post_json(
                PRODUCT_SEARCH_URL,
                {'page': page, 'size': min(max(page_size, 1), 500), 'orderType': 'NO'},
            )
            products.extend(flatten_products(data))

            total_pages = _safe_int(data.get('totalPages'))
            is_last = bool(data.get('last', False))
            if is_last or (total_pages is not None and page >= total_pages):
                break

            raw_contents = data.get('contents') or data.get('content') or []
            if not raw_contents:
                break
            page += 1

        if page > max_pages:
            raise NaverCommerceAPIError(f'상품 페이지가 {max_pages}페이지를 초과하여 조회를 중단했습니다.')
        return products


def flatten_products(data: dict[str, Any]) -> list[CommerceProduct]:
    flattened: list[CommerceProduct] = []
    contents = data.get('contents') or data.get('content') or []
    for origin in contents:
        if not isinstance(origin, dict):
            continue
        origin_product_no = str(origin.get('originProductNo', '') or '')
        channel_products = origin.get('channelProducts') or []
        for channel in channel_products:
            if not isinstance(channel, dict):
                continue
            if channel.get('channelServiceType') not in (None, '', 'STOREFARM'):
                continue
            flattened.append(CommerceProduct(
                name=str(channel.get('name', '') or '').strip(),
                channel_product_no=str(channel.get('channelProductNo', '') or ''),
                origin_product_no=str(channel.get('originProductNo', '') or origin_product_no),
                seller_management_code=str(channel.get('sellerManagementCode', '') or '').strip(),
                sale_price=_safe_int(channel.get('salePrice')),
                discounted_price=_safe_int(channel.get('discountedPrice')),
                status_type=str(channel.get('statusType', '') or '').strip(),
            ))
    return flattened


def normalize_for_match(text: str) -> str:
    text = str(text or '').lower()
    text = re.sub(r'([0-9]+)\s*(kg|g|ml|l|개|입|팩|단|통)', r'\1\2', text)
    text = re.sub(r'[^0-9a-z가-힣]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _tokens(text: str) -> list[str]:
    return [token for token in normalize_for_match(text).split(' ') if token]


def _numeric_unit_tokens(tokens: list[str]) -> set[str]:
    return {token for token in tokens if re.search(r'\d', token)}


def match_product(
    products: list[CommerceProduct],
    search_keyword: str,
    target_product_id: str = '',
) -> CommerceProduct | None:
    target = str(target_product_id or '').strip()
    if target:
        for product in products:
            if target in {product.channel_product_no, product.origin_product_no, product.seller_management_code}:
                return product

    keyword_norm = normalize_for_match(search_keyword)
    keyword_tokens = _tokens(search_keyword)
    if not keyword_norm or not keyword_tokens:
        return None
    required_numbers = _numeric_unit_tokens(keyword_tokens)

    status_priority = {'SALE': 6, 'OUTOFSTOCK': 4, 'WAIT': 2}
    candidates: list[tuple[float, CommerceProduct]] = []
    for product in products:
        name_norm = normalize_for_match(product.name)
        name_tokens = _tokens(product.name)
        if not name_norm:
            continue
        if required_numbers and not required_numbers.issubset(set(name_tokens)):
            continue

        token_hits = sum(1 for token in keyword_tokens if token in name_norm)
        token_ratio = token_hits / len(keyword_tokens)
        sequence_ratio = SequenceMatcher(None, keyword_norm, name_norm).ratio()
        if keyword_norm == name_norm:
            text_score = 100.0
        elif keyword_norm in name_norm:
            text_score = 90.0
        else:
            text_score = token_ratio * 70 + sequence_ratio * 20

        if token_ratio < 0.6 and sequence_ratio < 0.65:
            continue
        score = text_score + status_priority.get(product.status_type, 0)
        candidates.append((score, product))

    if not candidates:
        return None
    candidates.sort(key=lambda pair: (pair[0], pair[1].effective_price or -1), reverse=True)
    return candidates[0][1]


def format_product_price(product: CommerceProduct | None) -> str:
    if product is None or product.effective_price is None:
        return ''
    return f'{product.effective_price:,}'
