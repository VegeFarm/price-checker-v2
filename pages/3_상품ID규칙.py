import streamlit as st
from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_target_product_id_df, save_target_product_id_df

initialize_app()
ensure_login()
st.title('상품 ID 규칙')
st.caption('채소팜의 채널 상품번호를 입력하면 상품명보다 우선해서 정확히 매칭합니다. 원상품번호도 사용할 수 있습니다.')
session = get_session()
try:
    df = get_target_product_id_df(session)
    edited_df = st.data_editor(df, use_container_width=True, num_rows='fixed', hide_index=True)
    if st.button('상품 ID 규칙 저장'):
        save_target_product_id_df(session, edited_df)
        st.success('상품 ID 규칙이 저장되었습니다.')
finally:
    session.close()
