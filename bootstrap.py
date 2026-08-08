from sqlalchemy import func, select
from core.db import create_tables, get_session
from core.defaults import (
    DEFAULT_MALLS,
    DEFAULT_MALL_DISPLAY_NAMES,
    DEFAULT_PRICE_RULES,
    DEFAULT_SEARCH_KEYWORDS,
    DEFAULT_TARGET_PRODUCT_IDS,
)
from core.models import Item, Mall, PriceRule, SearchKeywordRule, TargetProductIdRule


def initialize_app() -> None:
    """테이블을 만들고 데이터가 전혀 없을 때만 기본 설정을 입력합니다."""
    create_tables()
    session = get_session()
    try:
        mall_count = session.scalar(select(func.count()).select_from(Mall)) or 0
        item_count = session.scalar(select(func.count()).select_from(Item)) or 0
        if mall_count or item_count:
            return

        mall_map: dict[str, Mall] = {}
        for order, mall_name in enumerate(DEFAULT_MALLS, start=1):
            mall = Mall(
                mall_name=mall_name,
                mall_display_name=DEFAULT_MALL_DISPLAY_NAMES.get(mall_name, mall_name),
                enabled=True,
                sort_order=order,
            )
            session.add(mall)
            session.flush()
            mall_map[mall_name] = mall

        item_map: dict[str, Item] = {}
        for order, item_name in enumerate(DEFAULT_SEARCH_KEYWORDS, start=1):
            item = Item(display_name=item_name, enabled=True, sort_order=order)
            session.add(item)
            session.flush()
            item_map[item_name] = item

        for item_name, rules in DEFAULT_SEARCH_KEYWORDS.items():
            for mall_name, keyword in rules.items():
                if keyword and mall_name in mall_map:
                    session.add(SearchKeywordRule(
                        item_id=item_map[item_name].id,
                        mall_id=mall_map[mall_name].id,
                        search_keyword=keyword,
                    ))

        for item_name, rules in DEFAULT_TARGET_PRODUCT_IDS.items():
            for mall_name, product_id in rules.items():
                if product_id and item_name in item_map and mall_name in mall_map:
                    session.add(TargetProductIdRule(
                        item_id=item_map[item_name].id,
                        mall_id=mall_map[mall_name].id,
                        target_product_id=str(product_id),
                    ))

        for item_name, rules in DEFAULT_PRICE_RULES.items():
            for mall_name, (op, value) in rules.items():
                if item_name in item_map and mall_name in mall_map:
                    session.add(PriceRule(
                        item_id=item_map[item_name].id,
                        mall_id=mall_map[mall_name].id,
                        op=op,
                        value=float(value),
                    ))

        session.commit()
    finally:
        session.close()
