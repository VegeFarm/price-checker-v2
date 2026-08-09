import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_own_product_settings_df, save_own_product_settings_df

initialize_app()
ensure_login()
st.title('우리 상품 설정')
st.caption('기존 검색 규칙과 상품 ID 규칙을 한 화면에서 관리합니다. 상품 추가/삭제도 이 표에서 할 수 있습니다.')
st.info(
    '조회 순서: ① 상품 ID가 있으면 ID를 먼저 찾습니다. '
    '② ID가 없거나 해당 ID로 상품을 찾지 못하면 검색어로 다시 찾습니다. '
    '정확한 매칭을 위해 가능하면 상품 ID를 등록해 주세요.'
)

session = get_session()
try:
    df = get_own_product_settings_df(session)
    edited_df = st.data_editor(
        df,
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
    if st.button('우리 상품 설정 저장', type='primary'):
        save_own_product_settings_df(session, edited_df)
        st.success('우리 상품 설정이 저장되었습니다.')
        st.rerun()
finally:
    session.close()
