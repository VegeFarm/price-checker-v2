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
from core.repository import (
    build_run_side_summary,
    get_latest_run,
    get_own_product_settings_df,
    save_own_product_settings_df,
)
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

if relay_ready:
    st.info('고정 IP 중계 서버 모드로 네이버 커머스 API에 연결됩니다.')
elif not direct_ready:
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
                    "아래 '우리 상품 설정'에서 상품 ID와 검색어를 확인해 주세요."
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
            st.text_area('결과 복사', value=latest_run.message_text, height=420)
        with right:
            render_missing_price_summary(missing_price_items)

    st.divider()
    st.subheader('우리 상품 설정')
    st.caption('기존 검색 규칙과 상품 ID 규칙을 한 화면에서 관리합니다. 상품 추가/삭제도 이 표에서 할 수 있습니다.')
    st.info(
        '조회 순서: ① 상품 ID가 있으면 ID를 먼저 찾습니다. '
        '② ID가 없거나 해당 ID로 상품을 찾지 못하면 검색어로 다시 찾습니다. '
        '정확한 매칭을 위해 가능하면 상품 ID를 등록해 주세요.'
    )
    own_df = get_own_product_settings_df(session)
    edited_df = st.data_editor(
        own_df,
        use_container_width=True,
        num_rows='dynamic',
        hide_index=True,
        column_config={
            '사용여부': st.column_config.CheckboxColumn('사용여부', default=True),
            '상품명': st.column_config.TextColumn('상품명', required=True, width='medium'),
            '상품 ID': st.column_config.TextColumn(
                '상품 ID',
                help='채널 상품번호, 원상품번호 또는 판매자 관리코드를 사용할 수 있습니다.',
                width='medium',
            ),
            '검색어': st.column_config.TextColumn(
                '검색어',
                help='상품 ID가 없거나 ID 매칭에 실패했을 때 사용하는 네이버 상품 검색어입니다.',
                width='large',
            ),
            '정렬순서': st.column_config.NumberColumn('정렬순서', min_value=1, step=1, format='%d'),
        },
    )
    if st.button('우리 상품 설정 저장', type='secondary'):
        save_own_product_settings_df(session, edited_df)
        st.success('우리 상품 설정이 저장되었습니다.')
        st.rerun()
finally:
    session.close()
