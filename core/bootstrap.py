from sqlalchemy import delete, func, select

from core.db import create_tables, get_session
from core.defaults import (
    DEFAULT_MALLS,
    DEFAULT_MALL_DISPLAY_NAMES,
    DEFAULT_MANUAL_COMPETITOR_PRICES,
    DEFAULT_PRICE_RULES,
    DEFAULT_SEARCH_KEYWORDS,
    DEFAULT_TARGET_PRODUCT_IDS,
)
from core.models import (
    AppSetting,
    Item,
    LegacyCompetitorProductRule,
    Mall,
    ManualCompetitorPrice,
    PriceRule,
    SearchKeywordRule,
    TargetProductIdRule,
)


def _seed_base_data(session) -> None:
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


def _seed_manual_competitor_prices_once(session) -> None:
    setting_key = 'manual_competitor_prices_seeded_20260809_v1'
    if session.get(AppSetting, setting_key) is not None:
        return

    items = {item.display_name: item for item in session.scalars(select(Item)).all()}
    malls = {mall.mall_name: mall for mall in session.scalars(select(Mall)).all()}
    existing_count = session.scalar(select(func.count()).select_from(ManualCompetitorPrice)) or 0

    # 이미 사용자가 수동 가격을 넣어 둔 DB라면 기본값을 섞지 않습니다.
    if existing_count == 0:
        for item_name, mall_prices in DEFAULT_MANUAL_COMPETITOR_PRICES.items():
            item = items.get(item_name)
            if item is None:
                continue
            for mall_name, price in mall_prices.items():
                mall = malls.get(mall_name)
                if mall is None:
                    continue
                session.add(ManualCompetitorPrice(
                    item_id=item.id,
                    mall_id=mall.id,
                    price=int(price),
                ))

    session.add(AppSetting(key=setting_key, value='1'))
    session.commit()


def _remove_legacy_competitor_urls_once(session) -> None:
    setting_key = 'legacy_competitor_url_scraper_removed_v1'
    if session.get(AppSetting, setting_key) is not None:
        return
    session.execute(delete(LegacyCompetitorProductRule))
    session.add(AppSetting(key=setting_key, value='1'))
    session.commit()


def initialize_app() -> None:
    """테이블 생성, 기본값 입력, 구버전 경쟁사 URL 기능 정리를 수행합니다."""
    create_tables()
    session = get_session()
    try:
        mall_count = session.scalar(select(func.count()).select_from(Mall)) or 0
        item_count = session.scalar(select(func.count()).select_from(Item)) or 0
        if not mall_count and not item_count:
            _seed_base_data(session)

        _seed_manual_competitor_prices_once(session)
        _remove_legacy_competitor_urls_once(session)
    finally:
        session.close()
