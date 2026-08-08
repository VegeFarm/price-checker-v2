import pandas as pd
import streamlit as st
from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_items, get_malls, get_price_rule_df, save_price_rule_df

initialize_app()
ensure_login()
st.title('가격 규칙')
st.caption('단위 환산이 필요한 채소팜 가격에 mul/add/sub/set/rate 규칙을 적용합니다.')
session = get_session()
try:
    df = get_price_rule_df(session)
    items = [x.display_name for x in get_items(session)]
    malls = [x.mall_name for x in get_malls(session)]
    if df.empty:
        df = pd.DataFrame([{'상품명': '', '쇼핑몰명': '', '연산': '', '값': ''}])
    df['값'] = df['값'].astype(str)
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows='dynamic',
        hide_index=True,
        column_config={
            '상품명': st.column_config.SelectboxColumn(options=items),
            '쇼핑몰명': st.column_config.SelectboxColumn(options=malls),
            '연산': st.column_config.SelectboxColumn(options=['mul', 'add', 'sub', 'set', 'rate']),
            '값': st.column_config.TextColumn(width='small'),
        },
    )
    if st.button('가격 규칙 저장'):
        save_price_rule_df(session, edited_df)
        st.success('가격 규칙이 저장되었습니다.')
finally:
    session.close()
