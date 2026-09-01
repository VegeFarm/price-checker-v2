import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.config import (
    NAVER_COMMERCE_CLIENT_ID,
    NAVER_COMMERCE_CLIENT_SECRET,
    RELAY_BASE_URL,
    RELAY_SHARED_TOKEN,
)
from core.db import get_session
from core.repository import build_run_side_summary, get_latest_run
from core.runner import run_price_check


def render_missing_price_summary(missing_price_items: list[dict]) -> None:
    st.subheader('우리 가격 없음')
    if missing_price_items:
        for item in missing_price_items:
            st.markdown(f"- **{item['item_name']}**")
    else:
        st.caption('채소팜 가격이 비어 있는 품목이 없습니다.')


st.set_page_config(page_title='채소팜 가격비교 관리자', layout='wide')
initialize_app()
ensure_login()

st.markdown(
    """
    <style>
    div.stButton > button {
        font-size: 1.55rem;
        font-weight: 700;
        min-height: 3.8rem;
        padding: 0.5rem 2.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title('채소팜 가격비교 관리자')
st.caption(
    '우리 가격은 네이버 커머스 API에서 최신값을 가져오고, 경쟁사 가격은 직접 저장한 최신값을 사용합니다. '
    'Cron이 실행되어도 경쟁사 저장 가격은 변경되지 않습니다.'
)

relay_ready = bool(RELAY_BASE_URL and RELAY_SHARED_TOKEN)
direct_ready = bool(NAVER_COMMERCE_CLIENT_ID and NAVER_COMMERCE_CLIENT_SECRET)
naver_ready = relay_ready or direct_ready

if not naver_ready:
    st.warning('RELAY_BASE_URL/RELAY_SHARED_TOKEN 또는 네이버 커머스 API ID/Secret을 설정해 주세요.')

if st.button('지금 실행', type='primary', disabled=not naver_ready):
    with st.spinner('우리 상품 최신 가격을 조회하고 저장된 경쟁사 가격과 비교하는 중...'):
        try:
            result = run_price_check(trigger_type='manual')
            st.success(
                f"네이버 API 상품 {result['product_count']:,}개를 확인했습니다. "
                f"우리 상품 {result['own_matched_count']:,}개 매칭, "
                f"저장된 경쟁사 가격 {result['manual_competitor_price_count']:,}개를 적용했습니다."
            )
            if result['own_missing_count']:
                st.warning(
                    f"우리 가격을 찾지 못한 품목이 {result['own_missing_count']:,}개 있습니다. "
                    "'검색상품설정'에서 상품 ID와 검색어를 확인해 주세요."
                )
        except Exception as exc:
            st.error(f'실행 중 오류: {exc}')

session = get_session()
try:
    latest_run = get_latest_run(session)
    if latest_run and latest_run.message_text:
        _, missing_price_items = build_run_side_summary(latest_run)
        left, right = st.columns([2.2, 1])
        with left:
            st.text_area(
                '결과 복사',
                value=latest_run.message_text,
                height=360,
                placeholder='실행 결과가 여기에 표시됩니다.',
            )
        with right:
            render_missing_price_summary(missing_price_items)
finally:
    session.close()
