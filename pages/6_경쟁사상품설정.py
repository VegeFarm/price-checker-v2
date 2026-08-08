import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_competitor_product_df, save_competitor_product_df

initialize_app()
ensure_login()
st.title('경쟁사 상품 설정')
st.caption(
    '상품별로 검색 여부를 선택합니다. 상품 하나를 체크하면 그 상품에 등록된 모든 경쟁사 URL의 가격을 확인합니다. '
    '기본값은 전부 검색이며, 새 상품이 추가되면 이 표에도 자동으로 추가됩니다.'
)
st.info(
    '검색여부가 체크되어 있어도 경쟁사 URL이 비어 있으면 그 경쟁사는 실제 페이지 요청을 하지 않습니다. '
    '체크를 해제하면 해당 상품의 모든 경쟁사 가격 검색을 건너뜁니다.'
)

session = get_session()
try:
    df = get_competitor_product_df(session)
    if df.empty:
        st.info('등록된 경쟁사 또는 상품이 없습니다.')
    else:
        column_config = {
            '검색여부': st.column_config.CheckboxColumn('검색여부', default=True),
        }
        for column in df.columns:
            if column.endswith(' URL'):
                column_config[column] = st.column_config.TextColumn(
                    column,
                    help='해당 경쟁사의 정확한 네이버 상품 상세 URL을 붙여넣으세요.',
                    width='large',
                )

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows='fixed',
            disabled=['상품명'],
            column_config=column_config,
        )
        if st.button('경쟁사 상품 설정 저장', type='primary'):
            save_competitor_product_df(session, edited_df)
            st.success('경쟁사 상품 설정이 저장되었습니다.')
            st.rerun()
finally:
    session.close()
