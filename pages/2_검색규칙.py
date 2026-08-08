import streamlit as st
from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_search_keyword_df, save_search_keyword_df

initialize_app()
ensure_login()
st.title('검색 규칙')
st.caption('채소팜 열의 상품 검색어를 사용합니다. 경쟁사 열은 향후 연동용으로 비워 둡니다.')
session = get_session()
try:
    df = get_search_keyword_df(session)
    edited_df = st.data_editor(df, use_container_width=True, num_rows='dynamic', hide_index=True)
    if st.button('검색 규칙 저장'):
        save_search_keyword_df(session, edited_df)
        st.success('검색 규칙이 저장되었습니다.')
        st.rerun()
finally:
    session.close()
