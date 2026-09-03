import streamlit as st

from components.price_text_editor import price_text_editor
from core.auth import ensure_login
from core.bootstrap import initialize_app
from core.db import get_session
from core.repository import get_competitor_price_editor_text, save_manual_competitor_prices_from_text

initialize_app()
ensure_login()
st.title('경쟁사 가격 입력')
st.caption(
    'app의 지금 실행으로 만들어진 최신 결과를 그대로 불러와 한 번에 확인하고 수정합니다. '
    '상품명 행을 클릭하면 앞의 *를 제외한 이름만, 가격을 클릭하면 숫자만 선택됩니다. '
    '선택된 부분에 바로 입력하면 기존 내용이 교체됩니다. '
    '단축 입력: 15→15,000원 / 135→13,500원 / 7500→7,500원.'
)

session = get_session()
try:
    flash = st.session_state.pop('competitor_price_flash', None)
    if flash:
        level, message = flash
        getattr(st, level)(message)

    editor_revision = int(st.session_state.get('competitor_editor_revision', 0))
    current_text, source_revision = get_competitor_price_editor_text(session)
    revision = f'{source_revision}-{editor_revision}'

    st.subheader('경쟁사 가격 일괄 입력')
    request = price_text_editor(
        current_text,
        height=820,
        revision=revision,
        key=f'competitor_price_editor_{revision}',
    )

    if request and request.get('save_token') != st.session_state.get('competitor_last_save_token'):
        st.session_state['competitor_last_save_token'] = request.get('save_token')
        bulk_text = str(request.get('text') or '')

        if not bulk_text.strip():
            st.session_state['competitor_price_flash'] = ('warning', '저장할 내용을 입력해 주세요.')
        else:
            result = save_manual_competitor_prices_from_text(session, bulk_text)
            if result['refreshed_run_id'] is not None:
                success_message = (
                    f"가격 {result['saved']:,}건 추가/수정, {result['deleted']:,}건 삭제했습니다. "
                    'app과 실행 결과에도 즉시 반영했습니다.'
                )
            else:
                success_message = (
                    f"가격 {result['saved']:,}건 추가/수정, {result['deleted']:,}건 삭제했습니다. "
                    '저장된 실행 결과가 없어 첫 실행 후 app과 실행 결과에 표시됩니다.'
                )

            warning_messages: list[str] = []
            if result['parse_errors']:
                warning_messages.append('형식을 읽지 못한 행: ' + ' / '.join(result['parse_errors']))
            if result['unknown_items']:
                warning_messages.append(
                    '검색상품설정에 없는 상품: ' + ', '.join(result['unknown_items'])
                )
            if result['unknown_malls']:
                warning_messages.append(
                    '쇼핑몰 설정에 없는 쇼핑몰: ' + ', '.join(result['unknown_malls'])
                )

            if warning_messages:
                st.session_state['competitor_price_flash'] = (
                    'warning',
                    success_message + ' ' + ' '.join(warning_messages),
                )
            else:
                st.session_state['competitor_price_flash'] = ('success', success_message)
                st.session_state['competitor_editor_revision'] = editor_revision + 1

        st.rerun()
finally:
    session.close()
