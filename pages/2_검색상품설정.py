import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_own_product_settings_df, save_own_product_settings_df

initialize_app()
ensure_login()
st.title('검색상품설정')
st.caption('네이버에서 조회할 우리 상품의 상품명, 상품 ID, 검색어, 사용 여부를 관리합니다.')

session = get_session()
try:
    df = get_own_product_settings_df(session)
    if not df.empty:
        df['정렬순서'] = df['정렬순서'].astype(str)
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
            '정렬순서': st.column_config.TextColumn('정렬순서', width='small'),
        },
    )
    if st.button('검색상품설정 저장', type='primary'):
        save_own_product_settings_df(session, edited_df)
        st.success('검색상품설정이 저장되었습니다.')
        st.rerun()
finally:
    session.close()
