import streamlit as st
from core.auth import ensure_login
from core.bootstrap import initialize_app

initialize_app()
ensure_login()
st.title('프로그램 설명서')
st.markdown(
    """
### 현재 수집 범위
- 네이버 커머스 API로 **채소팜 상품 가격만** 가져옵니다.
- 그린팜, 야채왕, 야채이야기 등 경쟁사 가격은 같은 형식으로 표시하되 공백입니다.
- API의 `discountedPrice`가 있으면 할인가를, 없으면 `salePrice`를 사용합니다.

### 검색 규칙
- 채소팜 검색어와 네이버 상품명을 비교해 상품을 찾습니다.
- 용량·수량 숫자가 다른 상품은 자동 매칭에서 제외합니다.

### 상품 ID 규칙
- 채널 상품번호 또는 원상품번호가 있으면 검색어보다 우선합니다.
- 상품이 잘못 매칭되면 해당 번호를 입력하는 방식이 가장 정확합니다.

### 가격 규칙
- `mul`: 곱하기, `add`: 더하기, `sub`: 빼기, `set`: 고정값, `rate`: 비율 적용입니다.
- 예: 2kg 상품 두 개 가격으로 비교하려면 `mul / 2`를 사용합니다.

### 자동 실행
- 웹에서 수동 실행하면 화면에만 결과가 저장됩니다.
- `cron_entry.py`로 실행한 결과는 텔레그램 설정이 있을 때만 발송됩니다.
"""
)
