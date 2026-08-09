import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_manual_competitor_price_df, save_manual_competitor_prices_from_text

initialize_app()
ensure_login()
st.title('경쟁사 가격 입력')
st.caption('경쟁사 가격을 한 번에 붙여넣어 저장합니다. 저장한 가격은 다음 Cron 실행에서도 그대로 유지됩니다.')
st.info(
    '`우리 - 가격` 줄은 입력해도 무시합니다. 경쟁사 가격만 저장됩니다. '
    '일부 상품/일부 경쟁사만 입력하면 적어 둔 값만 수정되고 나머지는 기존 값이 유지됩니다. '
    '`야채이야기 -`처럼 가격을 비워서 저장하면 해당 경쟁사 가격만 삭제됩니다.'
)
st.markdown(
    '''
#### 입력 방법
- 상품명 앞의 `*`는 **있어도 되고 없어도 됩니다.**
- 가격 줄의 `-`도 **숫자를 입력할 때는 없어도 됩니다.**
  - 예: `그린팜 - 55,000`, `그린팜 55,000` 둘 다 가능
- 상품 구분은 `우리 상품 설정`에 등록된 **상품명**으로 자동 인식합니다.
- 쇼핑몰 구분은 `쇼핑몰 설정`에 등록된 **쇼핑몰명/표시쇼핑몰명**으로 자동 인식합니다.
- 가격을 삭제하려면 `야채이야기 -`처럼 **쇼핑몰명 뒤에 `-`만 입력**해 주세요.
'''
)

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
            st.success(
                f"가격 {result['saved']:,}건 저장/수정, {result['deleted']:,}건 삭제했습니다. "
                f"우리 가격 줄 {result['ignored_own']:,}건은 무시했습니다."
            )
            if result['parse_errors']:
                st.warning('형식을 읽지 못한 행이 있습니다.')
                for message in result['parse_errors']:
                    st.write(f'- {message}')
            if result['unknown_items']:
                st.warning('우리 상품 설정에 없는 상품은 저장하지 않았습니다: ' + ', '.join(result['unknown_items']))
            if result['unknown_malls']:
                st.warning('쇼핑몰 설정에 없는 쇼핑몰은 저장하지 않았습니다: ' + ', '.join(result['unknown_malls']))
            st.rerun()

    st.divider()
    st.subheader('현재 저장된 경쟁사 가격')
    st.caption('아래 값이 수동 실행과 매일 Cron에서 사용됩니다.')
    current_df = get_manual_competitor_price_df(session)
    st.dataframe(current_df, use_container_width=True, hide_index=True)
finally:
    session.close()
