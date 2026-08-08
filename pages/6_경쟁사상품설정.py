import streamlit as st

from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_competitor_product_df, save_competitor_product_df
from core.competitor_scraper import CompetitorFetchError, CompetitorPriceFetcher

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

        st.divider()
        st.subheader('등록 URL 테스트')
        st.caption('저장된 URL을 실제로 1번 확인해서 네이버 차단인지, 가격 추출 문제인지 바로 보여줍니다. CAPTCHA나 접근 제한은 우회하지 않습니다.')
        if st.button('저장된 경쟁사 URL 테스트'):
            # 테스트는 저장된 값 기준으로 수행합니다. 표를 수정했다면 먼저 위의 저장 버튼을 눌러 주세요.
            test_df = get_competitor_product_df(session)
            fetcher = CompetitorPriceFetcher(min_delay=2.0, max_delay=5.0, timeout=20)
            test_rows = []
            for _, test_row in test_df.iterrows():
                if not bool(test_row.get('검색여부', True)):
                    continue
                item_name = str(test_row.get('상품명', '')).strip()
                for col in test_df.columns:
                    if not col.endswith(' URL'):
                        continue
                    url = str(test_row.get(col, '') or '').strip()
                    if not url or url.lower() == 'nan':
                        continue
                    mall_name = col[:-4]
                    try:
                        price = fetcher.fetch_price(url)
                        test_rows.append({'상품명': item_name, '경쟁사': mall_name, '상태': '성공', '가격': f'{price:,}', '상세': ''})
                    except CompetitorFetchError as exc:
                        test_rows.append({'상품명': item_name, '경쟁사': mall_name, '상태': '실패', '가격': '', '상세': str(exc)})
            if test_rows:
                st.dataframe(test_rows, use_container_width=True, hide_index=True)
            else:
                st.info('테스트할 저장 URL이 없습니다. 먼저 URL을 저장해 주세요.')
finally:
    session.close()
