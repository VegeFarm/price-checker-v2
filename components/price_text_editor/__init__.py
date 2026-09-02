from pathlib import Path

import streamlit.components.v1 as components


_FRONTEND_DIR = Path(__file__).parent / 'frontend'
_price_text_editor = components.declare_component(
    'competitor_price_text_editor',
    path=str(_FRONTEND_DIR),
)


def price_text_editor(
    value: str,
    *,
    height: int = 820,
    revision: str = '0',
    key: str | None = None,
) -> dict | None:
    """최신 경쟁사 가격을 편집하고 저장 요청을 반환하는 메모장형 편집기."""
    return _price_text_editor(
        value=value,
        height=height,
        revision=revision,
        key=key,
        default=None,
    )
