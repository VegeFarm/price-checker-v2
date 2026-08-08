import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.config import (
    NAVER_COMMERCE_CLIENT_ID,
    NAVER_COMMERCE_CLIENT_SECRET,
    NAVER_RELAY_KEY,
    NAVER_RELAY_URL,
)
from core.db import get_session
from core.repository import build_run_side_summary, get_latest_run
from core.runner import run_price_check


def render_missing_price_summary(missing_price_items: list[dict]) -> None:
    st.subheader('가격 없음')
    if missing_price_items:
        for item in missing_price_items:
            missing_text = ', '.join(item['missing_malls'])
            st.markdown(f"- **{item['item_name']}**: {missing_text}")
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
st.caption('네이버 커머스 API에서 채소팜 상품 가격만 조회하며 경쟁사 가격은 공백으로 표시합니다. 고정 IP 중계 서버가 설정되면 Render는 네이버 API를 직접 호출하지 않습니다.')

relay_ready = bool(NAVER_RELAY_URL and NAVER_RELAY_KEY)
direct_ready = bool(NAVER_COMMERCE_CLIENT_ID and NAVER_COMMERCE_CLIENT_SECRET)
naver_ready = relay_ready or direct_ready

if relay_ready:
    st.info('고정 IP 중계 서버 모드로 연결됩니다.')
elif not direct_ready:
    st.warning('NAVER_RELAY_URL/NAVER_RELAY_KEY 또는 네이버 커머스 API ID/Secret을 설정해 주세요.')

if st.button('지금 실행', type='primary', disabled=not naver_ready):
    with st.spinner('채소팜 상품 가격 조회 중...'):
        try:
            result = run_price_check(trigger_type='manual')
            st.success(f"네이버 상품 {result['product_count']:,}개를 확인했습니다.")
            st.rerun()
        except Exception as exc:
            st.error(f'실행 중 오류: {exc}')

session = get_session()
try:
    latest_run = get_latest_run(session)
    if latest_run and latest_run.message_text:
        _, missing_price_items = build_run_side_summary(latest_run)
        left, right = st.columns([2.2, 1])
        with left:
            st.text_area('결과 복사', value=latest_run.message_text, height=420)
        with right:
            render_missing_price_summary(missing_price_items)
finally:
    session.close()
