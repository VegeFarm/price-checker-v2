from __future__ import annotations
from zoneinfo import ZoneInfo
from collections import defaultdict
import pandas as pd
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from core.models import Mall, Item, SearchKeywordRule, TargetProductIdRule, PriceRule, CompetitorProductRule, RunHistory, RunPriceResult

KST = ZoneInfo("Asia/Seoul")


def format_display_time(dt):
    if not dt:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('UTC'))
    return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S')


def normalize_item_names(raw_names: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for raw in raw_names:
        name = str(raw).strip()
        if not name or name.lower() in {'nan', 'none'}:
            continue
        if name in seen:
            continue
        cleaned.append(name)
        seen.add(name)
    return cleaned


def ensure_items_from_search_rules(session: Session, item_names: list[str]) -> None:
    existing_items = get_items(session)
    existing_names = {item.display_name for item in existing_items}
    next_sort_order = (max((item.sort_order for item in existing_items), default=0) or 0) + 1

    for name in item_names:
        if name not in existing_names:
            session.add(Item(display_name=name, enabled=True, sort_order=next_sort_order))
            existing_names.add(name)
            next_sort_order += 1
    session.commit()


def sync_items_to_search_rules(session: Session, item_names: list[str]) -> None:
    existing_items = get_items(session)
    item_names_set = set(item_names)

    for item in existing_items:
        if item.display_name not in item_names_set:
            session.execute(delete(SearchKeywordRule).where(SearchKeywordRule.item_id == item.id))
            session.execute(delete(TargetProductIdRule).where(TargetProductIdRule.item_id == item.id))
            session.execute(delete(PriceRule).where(PriceRule.item_id == item.id))
            session.execute(delete(CompetitorProductRule).where(CompetitorProductRule.item_id == item.id))
            session.delete(item)
    session.commit()
    session.expire_all()


def get_malls(session: Session, enabled_only: bool = False) -> list[Mall]:
    stmt = select(Mall)
    if enabled_only:
        stmt = stmt.where(Mall.enabled.is_(True))
    stmt = stmt.order_by(Mall.sort_order.asc(), Mall.id.asc())
    return list(session.scalars(stmt).all())


def get_items(session: Session, enabled_only: bool = False) -> list[Item]:
    stmt = select(Item)
    if enabled_only:
        stmt = stmt.where(Item.enabled.is_(True))
    stmt = stmt.order_by(Item.sort_order.asc(), Item.id.asc())
    return list(session.scalars(stmt).all())


def get_search_keyword_df(session: Session) -> pd.DataFrame:
    malls = get_malls(session)
    items = get_items(session)
    mall_names = [m.mall_name for m in malls]
    data = []
    rules = {(r.item_id, r.mall_id): r.search_keyword for r in session.scalars(select(SearchKeywordRule)).all()}
    for item in items:
        row = {'상품명': item.display_name}
        for mall in malls:
            row[mall.mall_name] = rules.get((item.id, mall.id), '')
        data.append(row)
    return pd.DataFrame(data, columns=['상품명', *mall_names])


def save_search_keyword_df(session: Session, df: pd.DataFrame) -> None:
    malls = get_malls(session)
    mall_by_name = {m.mall_name: m for m in malls}

    item_names = normalize_item_names(df['상품명'].tolist())
    ensure_items_from_search_rules(session, item_names)
    sync_items_to_search_rules(session, item_names)
    item_by_name = {i.display_name: i for i in get_items(session)}

    session.execute(delete(SearchKeywordRule))
    session.commit()

    for _, row in df.iterrows():
        item_name = str(row.get('상품명', '')).strip()
        if not item_name:
            continue
        item = item_by_name[item_name]
        for mall_name, mall in mall_by_name.items():
            value = str(row.get(mall_name, '')).strip()
            if value:
                session.add(SearchKeywordRule(item_id=item.id, mall_id=mall.id, search_keyword=value))
    session.commit()


def get_target_product_id_df(session: Session) -> pd.DataFrame:
    malls = get_malls(session)
    items = get_items(session)
    mall_names = [m.mall_name for m in malls]
    rules = {(r.item_id, r.mall_id): r.target_product_id for r in session.scalars(select(TargetProductIdRule)).all()}
    data = []
    for item in items:
        row = {'상품명': item.display_name}
        for mall in malls:
            row[mall.mall_name] = rules.get((item.id, mall.id), '')
        data.append(row)
    return pd.DataFrame(data, columns=['상품명', *mall_names])


def save_target_product_id_df(session: Session, df: pd.DataFrame) -> None:
    malls = get_malls(session)
    mall_by_name = {m.mall_name: m for m in malls}
    item_by_name = {i.display_name: i for i in get_items(session)}

    session.execute(delete(TargetProductIdRule))
    session.commit()

    for _, row in df.iterrows():
        item_name = str(row.get('상품명', '')).strip()
        if not item_name or item_name not in item_by_name:
            continue
        item = item_by_name[item_name]
        for mall_name, mall in mall_by_name.items():
            value = str(row.get(mall_name, '')).strip()
            if value:
                session.add(TargetProductIdRule(item_id=item.id, mall_id=mall.id, target_product_id=value))
    session.commit()


def get_price_rule_df(session: Session) -> pd.DataFrame:
    items = {i.id: i.display_name for i in get_items(session)}
    malls = {m.id: m.mall_name for m in get_malls(session)}
    rows = []
    for rule in session.scalars(select(PriceRule).order_by(PriceRule.id.asc())).all():
        rows.append({
            '상품명': items.get(rule.item_id, ''),
            '쇼핑몰명': malls.get(rule.mall_id, ''),
            '연산': rule.op,
            '값': rule.value,
        })
    return pd.DataFrame(rows, columns=['상품명', '쇼핑몰명', '연산', '값'])


def save_price_rule_df(session: Session, df: pd.DataFrame) -> None:
    item_by_name = {i.display_name: i for i in get_items(session)}
    mall_by_name = {m.mall_name: m for m in get_malls(session)}

    session.execute(delete(PriceRule))
    session.commit()

    for _, row in df.iterrows():
        item_name = str(row.get('상품명', '')).strip()
        mall_name = str(row.get('쇼핑몰명', '')).strip()
        op = str(row.get('연산', '')).strip()
        raw_value = row.get('값', '')
        if not item_name or not mall_name or not op:
            continue
        if item_name not in item_by_name or mall_name not in mall_by_name:
            continue
        try:
            value = float(raw_value)
        except Exception:
            continue
        session.add(PriceRule(
            item_id=item_by_name[item_name].id,
            mall_id=mall_by_name[mall_name].id,
            op=op,
            value=value,
        ))
    session.commit()


def get_mall_settings_df(session: Session) -> pd.DataFrame:
    rows = []
    for mall in get_malls(session):
        rows.append({
            '실제쇼핑몰명': mall.mall_name,
            '표시쇼핑몰명': mall.mall_display_name,
            '사용여부': mall.enabled,
            '정렬순서': mall.sort_order,
        })
    return pd.DataFrame(rows, columns=['실제쇼핑몰명', '표시쇼핑몰명', '사용여부', '정렬순서'])


def save_mall_settings_df(session: Session, df: pd.DataFrame) -> None:
    existing = {m.mall_name: m for m in get_malls(session)}
    for _, row in df.iterrows():
        mall_name = str(row.get('실제쇼핑몰명', '')).strip()
        if not mall_name:
            continue
        mall = existing.get(mall_name)
        if mall is None:
            mall = Mall(
                mall_name=mall_name,
                mall_display_name=str(row.get('표시쇼핑몰명', mall_name)).strip() or mall_name,
                enabled=bool(row.get('사용여부', True)),
                sort_order=int(row.get('정렬순서', len(existing) + 1) or 0),
            )
            session.add(mall)
            existing[mall_name] = mall
        else:
            mall.mall_display_name = str(row.get('표시쇼핑몰명', mall_name)).strip() or mall_name
            mall.enabled = bool(row.get('사용여부', True))
            mall.sort_order = int(row.get('정렬순서', mall.sort_order) or 0)
    session.commit()



def _competitor_url_columns(malls: list[Mall]) -> dict[str, str]:
    """mall_name -> 화면에 표시할 URL 열 이름."""
    display_counts: dict[str, int] = {}
    for mall in malls:
        display_counts[mall.mall_display_name] = display_counts.get(mall.mall_display_name, 0) + 1

    columns: dict[str, str] = {}
    for mall in malls:
        if display_counts.get(mall.mall_display_name, 0) > 1:
            columns[mall.mall_name] = f'{mall.mall_display_name} ({mall.mall_name}) URL'
        else:
            columns[mall.mall_name] = f'{mall.mall_display_name} URL'
    return columns


def get_competitor_product_df(session: Session) -> pd.DataFrame:
    """상품별 경쟁사 검색 여부와 경쟁사 URL을 한 행에 표시합니다.

    검색여부는 상품 단위 하나의 체크박스이며, 체크하면 해당 상품의 모든 경쟁사 URL을
    검색합니다. Item/Mall 마스터를 기준으로 동적으로 만들기 때문에 새 상품이 추가되면
    자동으로 새 행이 생기며 기본값은 검색=True입니다.
    """
    from core.defaults import OWN_MALL_NAME

    items = get_items(session)
    malls = [m for m in get_malls(session) if m.mall_name != OWN_MALL_NAME]
    rules = {(r.item_id, r.mall_id): r for r in session.scalars(select(CompetitorProductRule)).all()}
    url_columns = _competitor_url_columns(malls)

    rows = []
    for item in items:
        item_rules = [rules.get((item.id, mall.id)) for mall in malls]
        enabled = all(True if rule is None else bool(rule.search_enabled) for rule in item_rules)
        row = {
            '상품명': item.display_name,
            '검색여부': enabled,
        }
        for mall in malls:
            rule = rules.get((item.id, mall.id))
            row[url_columns[mall.mall_name]] = '' if rule is None else str(rule.product_url or '')
        rows.append(row)

    columns = ['상품명', '검색여부', *[url_columns[m.mall_name] for m in malls]]
    return pd.DataFrame(rows, columns=columns)


def save_competitor_product_df(session: Session, df: pd.DataFrame) -> None:
    """상품 단위 체크값을 해당 상품의 모든 경쟁사 규칙에 동일하게 저장합니다."""
    from core.defaults import OWN_MALL_NAME

    item_by_name = {i.display_name: i for i in get_items(session)}
    malls = [m for m in get_malls(session) if m.mall_name != OWN_MALL_NAME]
    url_columns = _competitor_url_columns(malls)

    session.execute(delete(CompetitorProductRule))
    session.commit()

    for _, row in df.iterrows():
        item_name = str(row.get('상품명', '')).strip()
        if item_name not in item_by_name:
            continue

        raw_enabled = row.get('검색여부', True)
        enabled = bool(raw_enabled) if not pd.isna(raw_enabled) else True
        item = item_by_name[item_name]

        for mall in malls:
            raw_url = row.get(url_columns[mall.mall_name], '')
            product_url = '' if pd.isna(raw_url) else str(raw_url).strip()
            session.add(CompetitorProductRule(
                item_id=item.id,
                mall_id=mall.id,
                product_url=product_url,
                search_enabled=enabled,
            ))
    session.commit()


def load_competitor_product_config(session: Session) -> dict[tuple[str, str], dict]:
    """(상품명, 경쟁사명) -> {enabled, url}.

    저장된 행이 없으면 기본 검색여부는 True, URL은 빈칸으로 취급합니다.
    """
    from core.defaults import OWN_MALL_NAME

    items = get_items(session, enabled_only=True)
    malls = [m for m in get_malls(session, enabled_only=True) if m.mall_name != OWN_MALL_NAME]
    rules = {(r.item_id, r.mall_id): r for r in session.scalars(select(CompetitorProductRule)).all()}
    config: dict[tuple[str, str], dict] = {}
    for item in items:
        for mall in malls:
            rule = rules.get((item.id, mall.id))
            config[(item.display_name, mall.mall_name)] = {
                'enabled': True if rule is None else bool(rule.search_enabled),
                'url': '' if rule is None else str(rule.product_url or '').strip(),
            }
    return config

def load_runtime_config(session: Session):
    malls = get_malls(session, enabled_only=True)
    items = get_items(session, enabled_only=True)
    target_malls = [m.mall_name for m in malls]
    mall_display_names = {m.mall_name: m.mall_display_name for m in malls}

    search_rules = {(r.item_id, r.mall_id): r.search_keyword for r in session.scalars(select(SearchKeywordRule)).all()}
    product_id_rules = {(r.item_id, r.mall_id): r.target_product_id for r in session.scalars(select(TargetProductIdRule)).all()}
    price_rules_db = {(r.item_id, r.mall_id): (r.op, r.value) for r in session.scalars(select(PriceRule)).all()}

    search_keywords = {}
    target_product_ids = {}
    price_rules = {}

    for item in items:
        mall_keywords = {}
        mall_target_ids = {}
        item_price_rules = {}
        for mall in malls:
            keyword = search_rules.get((item.id, mall.id), '')
            if keyword:
                mall_keywords[mall.mall_name] = keyword
            target_id = product_id_rules.get((item.id, mall.id), '')
            if target_id:
                mall_target_ids[mall.mall_name] = target_id
            price_rule = price_rules_db.get((item.id, mall.id))
            if price_rule:
                item_price_rules[mall.mall_name] = price_rule
        search_keywords[item.display_name] = mall_keywords
        if mall_target_ids:
            target_product_ids[item.display_name] = mall_target_ids
        if item_price_rules:
            price_rules[item.display_name] = item_price_rules

    return target_malls, mall_display_names, search_keywords, target_product_ids, price_rules


def prune_run_history(session: Session, keep_latest: int = 3) -> None:
    runs = list(session.scalars(select(RunHistory).order_by(RunHistory.id.desc())).all())
    for run in runs[keep_latest:]:
        session.delete(run)
    session.commit()


def save_run_result(session: Session, trigger_type: str, status: str, started_at, finished_at,
                    message_text: str, error_text: str, rows: list[dict]) -> int:
    run = RunHistory(
        trigger_type=trigger_type,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        message_text=message_text,
        error_text=error_text,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    for row in rows:
        session.add(RunPriceResult(
            run_id=run.id,
            item_name=row['item_name'],
            mall_name=row['mall_name'],
            mall_display_name=row['mall_display_name'],
            price_text=row['price_text'],
        ))
    session.commit()
    prune_run_history(session, keep_latest=3)
    return run.id


def get_recent_runs_df(session: Session, limit: int = 3) -> pd.DataFrame:
    rows = []
    stmt = select(RunHistory).order_by(RunHistory.id.desc()).limit(limit)
    for idx, run in enumerate(session.scalars(stmt).all(), start=1):
        rows.append({
            'run_id': idx,
            '구분': run.trigger_type,
            '상태': run.status,
            '시작': format_display_time(run.started_at),
            '종료': format_display_time(run.finished_at),
            '에러': run.error_text,
        })
    return pd.DataFrame(rows)


def get_recent_runs_meta(session: Session, limit: int = 3) -> list[dict]:
    rows = []
    stmt = select(RunHistory).order_by(RunHistory.id.desc()).limit(limit)
    for idx, run in enumerate(session.scalars(stmt).all(), start=1):
        rows.append({
            'run_id': idx,
            'actual_run_id': run.id,
            '구분': run.trigger_type,
            '상태': run.status,
            '시작': format_display_time(run.started_at),
        })
    return rows


def get_run_history(session: Session, run_id: int) -> RunHistory | None:
    return session.get(RunHistory, run_id)


def get_previous_run(session: Session, run_id: int) -> RunHistory | None:
    stmt = select(RunHistory).where(RunHistory.id < run_id).order_by(RunHistory.id.desc()).limit(1)
    return session.scalars(stmt).first()


def get_latest_run(session: Session) -> RunHistory | None:
    return session.scalars(select(RunHistory).order_by(RunHistory.id.desc()).limit(1)).first()


def _price_to_int(price_text: str) -> int | None:
    text = str(price_text or '').replace(',', '').replace('원', '').strip()
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _is_our_mall(row: RunPriceResult) -> bool:
    display_name = str(row.mall_display_name or '').strip()
    mall_name = str(row.mall_name or '').strip()
    return display_name == '우리' or mall_name == '채소팜'


def _format_signed_price(value: int) -> str:
    return f"{value:+,}"


def _format_signed_percent(value: float) -> str:
    return f"{value * 100:+.1f}%"


def build_our_price_map(run: RunHistory | None) -> dict[str, int]:
    if run is None:
        return {}

    price_map: dict[str, int] = {}
    for row in run.results:
        if not _is_our_mall(row):
            continue
        value = _price_to_int(row.price_text)
        if value is None:
            continue
        price_map[row.item_name] = value
    return price_map


def build_price_map_by_item_mall(run: RunHistory | None) -> dict[str, dict[str, int]]:
    if run is None:
        return {}

    price_map: dict[str, dict[str, int]] = defaultdict(dict)
    for row in run.results:
        value = _price_to_int(row.price_text)
        if value is None:
            continue

        item_prices = price_map[row.item_name]
        item_prices[str(row.mall_display_name).strip()] = value
        raw_mall_name = str(row.mall_name).strip()
        if raw_mall_name:
            item_prices[raw_mall_name] = value
    return dict(price_map)


def build_run_side_summary(run: RunHistory) -> tuple[list[dict], list[dict]]:
    grouped: dict[str, list[RunPriceResult]] = defaultdict(list)
    for row in run.results:
        grouped[row.item_name].append(row)

    large_gap_items: list[dict] = []
    missing_price_items: list[dict] = []

    for item_name, rows in grouped.items():
        our_row: RunPriceResult | None = None
        competitor_priced: list[tuple[str, int]] = []
        missing: list[str] = []

        for row in rows:
            value = _price_to_int(row.price_text)
            if value is None:
                if _is_our_mall(row):
                    missing.append(row.mall_display_name)
                continue
            if _is_our_mall(row):
                our_row = row
            else:
                competitor_priced.append((row.mall_display_name, value))

        if missing:
            missing_price_items.append({
                'item_name': item_name,
                'missing_malls': missing,
            })

        if our_row is None:
            continue

        our_price = _price_to_int(our_row.price_text)
        if our_price is None or not competitor_priced:
            continue

        competitor_values = [price for _, price in competitor_priced]
        avg_price = round(sum(competitor_values) / len(competitor_values))
        min_mall, min_price = min(competitor_priced, key=lambda x: x[1])

        avg_diff = our_price - avg_price
        avg_ratio = (avg_diff / avg_price) if avg_price else 0
        min_diff = our_price - min_price
        min_ratio = (min_diff / min_price) if min_price else 0

        is_high = avg_diff >= 2000 and avg_ratio >= 0.15
        is_low = avg_diff <= -1500 and avg_ratio <= -0.15
        has_min_gap = min_diff >= 3000 and min_ratio >= 0.15
        is_similar = abs(avg_diff) <= 1000 and abs(avg_ratio) <= 0.10

        if is_high:
            status = '시장평균보다 높음'
        elif is_low:
            status = '시장평균보다 낮음'
        elif is_similar:
            status = '평균가는 유사'
        else:
            status = '주의'

        tags = [status]
        if has_min_gap:
            tags.append('최저가와 격차 큼')

        should_show = is_high or is_low or has_min_gap
        if should_show:
            severity_score = max(abs(avg_diff), abs(min_diff), int(abs(avg_ratio) * 1000), int(abs(min_ratio) * 1000))
            large_gap_items.append({
                'item_name': item_name,
                'our_price': f'{our_price:,}',
                'avg_price': f'{avg_price:,}',
                'min_price': f'{min_price:,}',
                'min_mall': min_mall,
                'avg_diff_amount': _format_signed_price(avg_diff),
                'avg_diff_ratio': _format_signed_percent(avg_ratio),
                'min_diff_amount': _format_signed_price(min_diff),
                'min_diff_ratio': _format_signed_percent(min_ratio),
                'status_text': ' · '.join(tags),
                'severity_score': severity_score,
            })

    large_gap_items.sort(key=lambda x: x['severity_score'], reverse=True)
    missing_price_items.sort(key=lambda x: x['item_name'])
    return large_gap_items, missing_price_items
