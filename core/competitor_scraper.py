from __future__ import annotations

import json
import random
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class CompetitorFetchError(RuntimeError):
    pass


_BLOCK_MARKERS = (
    '비정상적인 접근',
    '비정상 접근',
    '자동입력 방지',
    'captcha',
    '접근이 제한',
    '서비스 이용이 제한',
)


def _normalize_price(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        amount = int(float(value))
        return amount if amount > 0 else None
    text = str(value).replace(',', '').replace('원', '').strip()
    match = re.search(r'(\d{2,})', text)
    if not match:
        return None
    amount = int(match.group(1))
    return amount if amount > 0 else None


def _walk_json_for_price(obj) -> int | None:
    preferred = ('discountedPrice', 'salePrice', 'lowPrice', 'price')
    if isinstance(obj, dict):
        for key in preferred:
            if key in obj:
                price = _normalize_price(obj.get(key))
                if price:
                    return price
        offers = obj.get('offers')
        if offers is not None:
            price = _walk_json_for_price(offers)
            if price:
                return price
        for value in obj.values():
            price = _walk_json_for_price(value)
            if price:
                return price
    elif isinstance(obj, list):
        for value in obj:
            price = _walk_json_for_price(value)
            if price:
                return price
    return None


def extract_price_from_html(html: str) -> int | None:
    soup = BeautifulSoup(html, 'html.parser')

    # 1) JSON-LD: 상품 상세 페이지에서 가장 안정적으로 노출되는 구조 중 하나입니다.
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        raw = script.string or script.get_text() or ''
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        price = _walk_json_for_price(payload)
        if price:
            return price

    # 2) 가격 메타 태그
    meta_keys = (
        ('property', 'product:price:amount'),
        ('property', 'og:price:amount'),
        ('name', 'product:price:amount'),
        ('name', 'price'),
    )
    for attr, key in meta_keys:
        tag = soup.find('meta', attrs={attr: key})
        if tag:
            price = _normalize_price(tag.get('content'))
            if price:
                return price

    # 3) 페이지에 포함된 상태 JSON. 특정 CSS 선택자에 의존하지 않도록 키 이름만 좁게 찾습니다.
    patterns = (
        r'"discountedPrice"\s*:\s*"?(\d[\d,]*)"?',
        r'"salePrice"\s*:\s*"?(\d[\d,]*)"?',
        r'"lowPrice"\s*:\s*"?(\d[\d,]*)"?',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            price = _normalize_price(match.group(1))
            if price:
                return price

    return None


class CompetitorPriceFetcher:
    """등록된 네이버 상품 상세 URL을 낮은 빈도로 확인합니다.

    CAPTCHA/차단을 우회하지 않습니다. 차단 페이지가 감지되면 해당 상품만 실패로 처리합니다.
    """

    def __init__(self, min_delay: float = 2.0, max_delay: float = 5.0, timeout: int = 20):
        self.min_delay = max(0.0, float(min_delay))
        self.max_delay = max(self.min_delay, float(max_delay))
        self.timeout = int(timeout)
        self._last_request_at: float | None = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        if parsed.scheme not in {'http', 'https'} or not host:
            raise CompetitorFetchError('상품 URL 형식이 올바르지 않습니다.')
        # 관리자 화면에 저장된 URL을 서버가 직접 요청하므로 SSRF 방지를 위해 네이버 계열만 허용합니다.
        if not (host == 'naver.com' or host.endswith('.naver.com') or host == 'naver.me' or host.endswith('.naver.me')):
            raise CompetitorFetchError('현재는 네이버 상품 URL만 지원합니다.')

    def _wait_between_requests(self) -> None:
        if self._last_request_at is None:
            return
        target_delay = random.uniform(self.min_delay, self.max_delay)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)

    def _fetch_once(self, url: str) -> int:
        self._wait_between_requests()
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as exc:
            self._last_request_at = time.monotonic()
            raise CompetitorFetchError(f'페이지 연결 실패: {exc}') from exc
        self._last_request_at = time.monotonic()

        # 리다이렉트 뒤에도 네이버 계열 URL인지 다시 확인합니다.
        self._validate_url(response.url)

        if response.status_code >= 400:
            raise CompetitorFetchError(f'HTTP {response.status_code}')

        text_lower = response.text.lower()
        if any(marker.lower() in text_lower for marker in _BLOCK_MARKERS):
            raise CompetitorFetchError('네이버 접근 제한/CAPTCHA 페이지가 감지되었습니다.')

        price = extract_price_from_html(response.text)
        if price is None:
            raise CompetitorFetchError('페이지에서 가격을 찾지 못했습니다.')
        return price

    def fetch_price(self, url: str) -> int:
        self._validate_url(url)
        first_error: Exception | None = None
        for attempt in range(2):
            try:
                return self._fetch_once(url)
            except CompetitorFetchError as exc:
                if first_error is None:
                    first_error = exc
                if attempt == 0:
                    time.sleep(8)
        raise CompetitorFetchError(str(first_error or '가격 조회 실패'))
