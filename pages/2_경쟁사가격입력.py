import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_manual_competitor_price_df, save_manual_competitor_prices_from_text

initialize_app()
ensure_login()
st.title('경쟁사 가격 입력')
st.caption('경쟁사 가격을 한 번에 붙여넣어 저장합니다. 단축 입력: 15→15,000원 / 135→13,500원 / 7500→7,500원. 쉼표 입력은 그대로 사용합니다.')

bulk_text = st.text_area(
    '경쟁사 가격 일괄 입력',
    height=360,
    placeholder='로케트\n우리 - 40,000\n그린팜 55,000\n야채왕 - 55,000\n야채이야기 - 55,000\n쉐프의정원 33,000',
)

session = get_session()
try:
    if st.button('경쟁사 가격 저장', type='primary'):
        if not bulk_text.strip():
            st.warning('저장할 내용을 입력해 주세요.')
        else:
            result = save_manual_competitor_prices_from_text(session, bulk_text)
            if result['refreshed_run_id'] is not None:
                st.success(
                    f"가격 {result['saved']:,}건 저장/수정, {result['deleted']:,}건 삭제했습니다. "
                    'app과 실행 결과에도 즉시 반영했습니다.'
                )
            else:
                st.success(
                    f"가격 {result['saved']:,}건 저장/수정, {result['deleted']:,}건 삭제했습니다. "
                    '저장된 실행 결과가 없어 첫 실행 후 app과 실행 결과에 표시됩니다.'
                )
            if result['parse_errors']:
                st.warning('형식을 읽지 못한 행이 있습니다.')
                for message in result['parse_errors']:
                    st.write(f'- {message}')
            if result['unknown_items']:
                st.warning('검색상품설정에 없는 상품은 저장하지 않았습니다: ' + ', '.join(result['unknown_items']))
            if result['unknown_malls']:
                st.warning('쇼핑몰 설정에 없는 쇼핑몰은 저장하지 않았습니다: ' + ', '.join(result['unknown_malls']))

    st.divider()
    st.subheader('현재 저장된 경쟁사 가격')
    st.caption('아래 값이 수동 실행과 매일 Cron에서 사용됩니다.')
    current_df = get_manual_competitor_price_df(session)
    st.dataframe(current_df, use_container_width=True, hide_index=True)
finally:
    session.close()
