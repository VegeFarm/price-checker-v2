import streamlit as st
from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_mall_settings_df, save_mall_settings_df

initialize_app()
ensure_login()
st.title('쇼핑몰 설정')
st.caption('쇼핑몰 표시명, 사용 여부, 정렬 순서를 수정합니다. 경쟁사별 상품 URL/검색 여부는 ‘경쟁사 상품 설정’ 페이지에서 관리합니다.')
session = get_session()
try:
    df = get_mall_settings_df(session)
    edited_df = st.data_editor(df, use_container_width=True, num_rows='dynamic', hide_index=True)
    if st.button('쇼핑몰 설정 저장'):
        save_mall_settings_df(session, edited_df)
        st.success('쇼핑몰 설정이 저장되었습니다.')
finally:
    session.close()
