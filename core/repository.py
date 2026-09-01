from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.defaults import OWN_MALL_NAME
from core.formatters import build_message_text
from core.models import (
    Item,
    LegacyCompetitorProductRule,
    Mall,
    ManualCompetitorPrice,
    PriceRule,
    RunHistory,
    RunPriceResult,
    SearchKeywordRule,
    TargetProductIdRule,
)

KST = ZoneInfo('Asia/Seoul')


def format_display_time(dt):
    if not dt:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('UTC'))
    return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S')


def _clean_text(value) -> str:
    if pd.isna(value):
        return ''
    text = str(value).strip()
    if text.lower() in {'nan', 'none'}:
        return ''
    return text


def _clean_bool(value, default: bool = True) -> bool:
    if pd.isna(value):
        return default
    return bool(value)


def _clean_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def normalize_item_names(raw_names: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in raw_names:
        name = _clean_text(raw)
        if not name or name in seen:
            continue
        cleaned.append(name)
        seen.add(name)
    return cleaned


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


def _get_own_mall(session: Session) -> Mall:
    mall = session.scalars(select(Mall).where(Mall.mall_name == OWN_MALL_NAME).limit(1)).first()
    if mall is None:
        raise RuntimeError(f"'{OWN_MALL_NAME}' 쇼핑몰 설정이 없습니다.")
    return mall


# ---------------------------------------------------------------------------
# 우리 상품 설정: 기존 검색 규칙 + 상품 ID 규칙을 한 화면에서 관리
# ---------------------------------------------------------------------------

def get_own_product_settings_df(session: Session) -> pd.DataFrame:
    own_mall = _get_own_mall(session)
    items = get_items(session)
    search_rules = {
        r.item_id: r.search_keyword
        for r in session.scalars(
            select(SearchKeywordRule).where(SearchKeywordRule.mall_id == own_mall.id)
        ).all()
    }
    product_id_rules = {
        r.item_id: r.target_product_id
        for r in session.scalars(
            select(TargetProductIdRule).where(TargetProductIdRule.mall_id == own_mall.id)
        ).all()
    }

    rows = []
    for item in items:
        rows.append({
            '사용여부': item.enabled,
            '상품명': item.display_name,
            '상품 ID': product_id_rules.get(item.id, ''),
            '검색어': search_rules.get(item.id, ''),
            '정렬순서': item.sort_order,
        })
    return pd.DataFrame(rows, columns=['사용여부', '상품명', '상품 ID', '검색어', '정렬순서'])


def save_own_product_settings_df(session: Session, df: pd.DataFrame) -> None:
    own_mall = _get_own_mall(session)
    existing_items = {item.display_name: item for item in get_items(session)}

    desired_rows: list[dict] = []
    seen_names: set[str] = set()
    for row_index, (_, row) in enumerate(df.iterrows(), start=1):
        item_name = _clean_text(row.get('상품명', ''))
        if not item_name or item_name in seen_names:
            continue
        seen_names.add(item_name)
        desired_rows.append({
            'item_name': item_name,
            'enabled': _clean_bool(row.get('사용여부', True), True),
            'product_id': _clean_text(row.get('상품 ID', '')),
            'search_keyword': _clean_text(row.get('검색어', '')),
            'sort_order': _clean_int(row.get('정렬순서', row_index), row_index),
        })

    desired_names = {row['item_name'] for row in desired_rows}

    # 화면에서 삭제한 상품은 관련 설정/수동 경쟁사 가격도 같이 제거합니다.
    for item_name, item in list(existing_items.items()):
        if item_name in desired_names:
            continue
        session.execute(delete(SearchKeywordRule).where(SearchKeywordRule.item_id == item.id))
        session.execute(delete(TargetProductIdRule).where(TargetProductIdRule.item_id == item.id))
        session.execute(delete(PriceRule).where(PriceRule.item_id == item.id))
        session.execute(delete(ManualCompetitorPrice).where(ManualCompetitorPrice.item_id == item.id))
        session.execute(delete(LegacyCompetitorProductRule).where(LegacyCompetitorProductRule.item_id == item.id))
        session.delete(item)
    session.flush()

    # 새 상품 추가 및 기본 정보 갱신
    for index, row in enumerate(desired_rows, start=1):
        item = existing_items.get(row['item_name'])
        if item is None or item not in session:
            item = Item(display_name=row['item_name'])
            session.add(item)
            session.flush()
            existing_items[row['item_name']] = item
        item.enabled = row['enabled']
        item.sort_order = row['sort_order'] if row['sort_order'] > 0 else index

    # 구버전 경쟁사 검색어/상품ID까지 정리하고 우리 설정만 다시 저장합니다.
    session.execute(delete(SearchKeywordRule))
    session.execute(delete(TargetProductIdRule))
    session.flush()

    for row in desired_rows:
        item = existing_items[row['item_name']]
        if row['product_id']:
            session.add(TargetProductIdRule(
                item_id=item.id,
                mall_id=own_mall.id,
                target_product_id=row['product_id'],
            ))
        if row['search_keyword']:
            session.add(SearchKeywordRule(
                item_id=item.id,
                mall_id=own_mall.id,
                search_keyword=row['search_keyword'],
            ))
    session.commit()


# ---------------------------------------------------------------------------
# 가격 규칙 / 쇼핑몰 설정
# ---------------------------------------------------------------------------

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
    session.flush()

    for _, row in df.iterrows():
        item_name = _clean_text(row.get('상품명', ''))
        mall_name = _clean_text(row.get('쇼핑몰명', ''))
        op = _clean_text(row.get('연산', ''))
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
        mall_name = _clean_text(row.get('실제쇼핑몰명', ''))
        if not mall_name:
            continue
        mall = existing.get(mall_name)
        if mall is None:
            mall = Mall(
                mall_name=mall_name,
                mall_display_name=_clean_text(row.get('표시쇼핑몰명', mall_name)) or mall_name,
                enabled=_clean_bool(row.get('사용여부', True), True),
                sort_order=_clean_int(row.get('정렬순서', len(existing) + 1), len(existing) + 1),
            )
            session.add(mall)
            existing[mall_name] = mall
        else:
            mall.mall_display_name = _clean_text(row.get('표시쇼핑몰명', mall_name)) or mall_name
            mall.enabled = _clean_bool(row.get('사용여부', True), True)
            mall.sort_order = _clean_int(row.get('정렬순서', mall.sort_order), mall.sort_order)
    session.commit()


# ---------------------------------------------------------------------------
# 경쟁사 가격 수동 입력/저장
# ---------------------------------------------------------------------------

def _normalize_label(text: str) -> str:
    return re.sub(r'\s+', '', str(text or '')).strip().lower()


def _parse_price_value(raw: str) -> int | None:
    """경쟁사 가격 입력값을 원 단위 정수로 변환합니다.

    단축 입력 규칙(쉼표가 없는 숫자에만 적용):
    - 1~2자리: 천원 단위로 해석 (예: 7 -> 7,000 / 15 -> 15,000)
    - 3자리: 백원 단위로 해석 (예: 135 -> 13,500)
    - 4자리 이상: 입력한 원 단위 그대로 사용 (예: 7500 -> 7,500)

    쉼표를 넣어 정확한 금액을 입력한 경우에는 후처리하지 않습니다.
    예: 7,500 -> 7,500 / 13,500 -> 13,500
    """
    text = str(raw or '').strip()
    if not text:
        return None

    text = text.replace('원', '').replace('₩', '').strip()
    has_comma = ',' in text

    if has_comma:
        # 쉼표 입력은 정확한 원 단위 금액으로 취급합니다.
        # 잘못된 쉼표 위치(예: 13,50)는 조용히 다른 금액으로 바꾸지 않고 오류로 처리합니다.
        if not re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.0+)?', text):
            raise ValueError(f'가격 형식이 올바르지 않습니다: {raw}')
        numeric_text = text.replace(',', '')
    else:
        numeric_text = text
        if not re.fullmatch(r'\d+(?:\.0+)?', numeric_text):
            raise ValueError(f'가격 형식이 올바르지 않습니다: {raw}')

    value = int(float(numeric_text))
    if value < 0:
        raise ValueError(f'가격은 0 이상이어야 합니다: {raw}')

    if has_comma:
        return value

    digit_count = len(str(value))
    if digit_count <= 2:
        return value * 1000
    if digit_count == 3:
        return value * 100
    return value


def _build_known_label_map(labels: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for label in labels:
        cleaned = _clean_text(label)
        if cleaned:
            result[_normalize_label(cleaned)] = cleaned
    return result



def _parse_mall_line_without_dash(line: str, known_mall_map: dict[str, str]) -> tuple[str, str] | None:
    stripped = line.strip()
    normalized = _normalize_label(stripped)
    if not stripped or not normalized:
        return None
    for mall_key in sorted(known_mall_map.keys(), key=len, reverse=True):
        if not normalized.startswith(mall_key):
            continue
        mall_label = known_mall_map[mall_key]
        original_no_space = re.sub(r'\s+', '', stripped)
        remainder_no_space = original_no_space[len(mall_key):].strip()
        if not remainder_no_space:
            return None
        try:
            price = _parse_price_value(remainder_no_space)
        except ValueError:
            return None
        return mall_label, str(price)
    return None



def parse_competitor_price_text(
    text: str,
    known_item_names: list[str] | None = None,
    known_mall_labels: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    """사용자 붙여넣기 형식을 파싱합니다.

    반환 entry: {line_no, item_name, mall_label, price}
    price=None은 사용자가 `몰 -`처럼 빈 값을 명시하여 기존 가격 삭제를 요청한 뜻입니다.
    """
    entries: list[dict] = []
    errors: list[str] = []
    current_item = ''
    item_name_map = _build_known_label_map(known_item_names or [])
    mall_label_map = _build_known_label_map(known_mall_labels or [])

    for line_no, raw_line in enumerate(str(text or '').splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        raw_item_name = line[1:].strip() if line.startswith('*') else line.strip()
        normalized_item_name = _normalize_label(raw_item_name)
        if line.startswith('*'):
            current_item = raw_item_name
            if not current_item:
                errors.append(f'{line_no}행: 상품명이 비어 있습니다.')
            continue
        if normalized_item_name in item_name_map:
            current_item = item_name_map[normalized_item_name]
            continue

        mall_label = None
        raw_price = ''
        match = re.match(r'^(.+?)\s*-\s*(.*)$', line)
        if match:
            mall_label = match.group(1).strip()
            raw_price = match.group(2).strip()
        else:
            parsed = _parse_mall_line_without_dash(line, mall_label_map)
            if parsed is not None:
                mall_label, raw_price = parsed

        if mall_label is not None:
            if not current_item:
                errors.append(f'{line_no}행: 먼저 상품명을 입력해 주세요.')
                continue
            if not mall_label:
                errors.append(f'{line_no}행: 쇼핑몰명이 비어 있습니다.')
                continue
            try:
                price = _parse_price_value(raw_price)
            except ValueError as exc:
                errors.append(f'{line_no}행: {exc}')
                continue
            entries.append({
                'line_no': line_no,
                'item_name': current_item,
                'mall_label': mall_label,
                'price': price,
            })
            continue

        errors.append(f'{line_no}행: 상품명 또는 가격 형식을 읽지 못했습니다.')

    return entries, errors


def save_manual_competitor_prices_from_text(session: Session, text: str) -> dict:
    items = get_items(session)
    malls = get_malls(session)
    item_by_name = {item.display_name: item for item in items}

    known_item_names = [item.display_name for item in items]
    known_mall_labels: list[str] = []
    mall_aliases: dict[str, Mall] = {}
    for mall in malls:
        for label in {mall.mall_name, mall.mall_display_name}:
            key = _normalize_label(label)
            if key:
                mall_aliases[key] = mall
                known_mall_labels.append(label)

    entries, parse_errors = parse_competitor_price_text(
        text,
        known_item_names=known_item_names,
        known_mall_labels=known_mall_labels,
    )

    existing = {
        (row.item_id, row.mall_id): row
        for row in session.scalars(select(ManualCompetitorPrice)).all()
    }

    unknown_items: set[str] = set()
    unknown_malls: set[str] = set()
    ignored_own = 0
    saved = 0
    unchanged = 0
    deleted_count = 0

    for entry in entries:
        item = item_by_name.get(entry['item_name'])
        if item is None:
            unknown_items.add(entry['item_name'])
            continue

        mall = mall_aliases.get(_normalize_label(entry['mall_label']))
        if mall is None:
            unknown_malls.add(entry['mall_label'])
            continue
        if mall.mall_name == OWN_MALL_NAME:
            ignored_own += 1
            continue

        key = (item.id, mall.id)
        row = existing.get(key)
        price = entry['price']
        if price is None:
            if row is not None:
                session.delete(row)
                existing.pop(key, None)
                deleted_count += 1
            continue

        if row is None:
            row = ManualCompetitorPrice(
                item_id=item.id,
                mall_id=mall.id,
                price=price,
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(row)
            existing[key] = row
            saved += 1
        else:
            if int(row.price) == int(price):
                unchanged += 1
            else:
                row.price = price
                row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                saved += 1

    session.commit()
    refreshed_run_id = refresh_latest_run_with_manual_prices(session)
    return {
        'saved': saved,
        'unchanged': unchanged,
        'deleted': deleted_count,
        'ignored_own': ignored_own,
        'parse_errors': parse_errors,
        'unknown_items': sorted(unknown_items),
        'unknown_malls': sorted(unknown_malls),
        'entry_count': len(entries),
        'refreshed_run_id': refreshed_run_id,
    }


def get_manual_competitor_price_df(session: Session) -> pd.DataFrame:
    items = get_items(session)
    malls = [m for m in get_malls(session) if m.mall_name != OWN_MALL_NAME]
    prices = {
        (r.item_id, r.mall_id): r.price
        for r in session.scalars(select(ManualCompetitorPrice)).all()
    }

    rows = []
    for item in items:
        row = {'상품명': item.display_name}
        for mall in malls:
            value = prices.get((item.id, mall.id))
            row[mall.mall_display_name] = '' if value is None else f'{value:,}'
        rows.append(row)
    return pd.DataFrame(rows, columns=['상품명', *[m.mall_display_name for m in malls]])


def get_manual_competitor_price_text(session: Session) -> str:
    """현재 저장값을 경쟁사 가격 일괄 편집 형식으로 반환합니다.

    등록된 모든 상품과 경쟁사 쇼핑몰을 정렬순서대로 표시하며, 아직 가격이 없는
    조합도 ``쇼핑몰 -`` 형태로 포함합니다. 따라서 이 문자열을 편집창의 기본값으로
    사용하면 한 화면에서 최신 가격 전체를 조회하고 바로 수정할 수 있습니다.
    """
    items = get_items(session)
    malls = [m for m in get_malls(session) if m.mall_name != OWN_MALL_NAME]
    prices = {
        (row.item_id, row.mall_id): int(row.price)
        for row in session.scalars(select(ManualCompetitorPrice)).all()
    }

    blocks: list[str] = []
    for item in items:
        lines = [item.display_name]
        for mall in malls:
            price = prices.get((item.id, mall.id))
            price_text = '' if price is None else f'{price:,}'
            lines.append(f'{mall.mall_display_name} - {price_text}'.rstrip())
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


def load_manual_competitor_prices(session: Session) -> dict[tuple[str, str], int]:
    item_names = {i.id: i.display_name for i in get_items(session, enabled_only=True)}
    mall_names = {m.id: m.mall_name for m in get_malls(session, enabled_only=True)}
    result: dict[tuple[str, str], int] = {}
    for row in session.scalars(select(ManualCompetitorPrice)).all():
        item_name = item_names.get(row.item_id)
        mall_name = mall_names.get(row.mall_id)
        if not item_name or not mall_name or mall_name == OWN_MALL_NAME:
            continue
        result[(item_name, mall_name)] = int(row.price)
    return result


# ---------------------------------------------------------------------------
# 실행 시 사용하는 설정
# ---------------------------------------------------------------------------

def load_runtime_config(session: Session):
    malls = get_malls(session, enabled_only=True)
    items = get_items(session, enabled_only=True)
    own_mall = next((m for m in malls if m.mall_name == OWN_MALL_NAME), None)
    if own_mall is None:
        raise RuntimeError(f"'{OWN_MALL_NAME}' 쇼핑몰이 비활성화되어 있거나 없습니다.")

    target_malls = [m.mall_name for m in malls]
    mall_display_names = {m.mall_name: m.mall_display_name for m in malls}

    search_rules = {
        r.item_id: r.search_keyword
        for r in session.scalars(
            select(SearchKeywordRule).where(SearchKeywordRule.mall_id == own_mall.id)
        ).all()
    }
    product_id_rules = {
        r.item_id: r.target_product_id
        for r in session.scalars(
            select(TargetProductIdRule).where(TargetProductIdRule.mall_id == own_mall.id)
        ).all()
    }
    price_rules_db = {
        (r.item_id, r.mall_id): (r.op, r.value)
        for r in session.scalars(select(PriceRule)).all()
    }

    own_product_config: dict[str, dict[str, str]] = {}
    price_rules: dict[str, dict[str, tuple[str, float]]] = {}
    for item in items:
        own_product_config[item.display_name] = {
            'search_keyword': search_rules.get(item.id, '') or item.display_name,
            'target_product_id': product_id_rules.get(item.id, ''),
        }
        item_rules: dict[str, tuple[str, float]] = {}
        for mall in malls:
            rule = price_rules_db.get((item.id, mall.id))
            if rule:
                item_rules[mall.mall_name] = rule
        if item_rules:
            price_rules[item.display_name] = item_rules

    manual_prices = load_manual_competitor_prices(session)
    return target_malls, mall_display_names, own_product_config, price_rules, manual_prices


def refresh_latest_run_with_manual_prices(session: Session) -> int | None:
    """최신 성공 실행의 경쟁사 가격만 현재 수동 저장값으로 즉시 갱신합니다.

    네이버 API를 다시 호출하지 않고, 마지막 실행에서 저장된 우리 가격은 그대로 유지합니다.
    """
    run = session.scalars(
        select(RunHistory)
        .where(RunHistory.status == 'success')
        .order_by(RunHistory.id.desc())
        .limit(1)
    ).first()
    if run is None:
        return None

    malls = get_malls(session, enabled_only=True)
    items = get_items(session, enabled_only=True)
    own_price_by_item: dict[str, str] = {}
    for row in run.results:
        if _is_our_mall(row):
            own_price_by_item[row.item_name] = str(row.price_text or '')

    manual_prices = load_manual_competitor_prices(session)
    results: dict[str, list[tuple[str, str]]] = {}
    rows: list[dict] = []

    for item in items:
        display_name = item.display_name
        results[display_name] = []
        for mall in malls:
            mall_display = mall.mall_display_name
            if mall.mall_name == OWN_MALL_NAME:
                price_text = own_price_by_item.get(display_name, '')
            else:
                manual_price = manual_prices.get((display_name, mall.mall_name))
                price_text = '' if manual_price is None else f'{int(manual_price):,}'

            results[display_name].append((mall_display, price_text))
            rows.append({
                'item_name': display_name,
                'mall_name': mall.mall_name,
                'mall_display_name': mall_display,
                'price_text': price_text,
            })

    session.execute(delete(RunPriceResult).where(RunPriceResult.run_id == run.id))
    session.flush()
    for row in rows:
        session.add(RunPriceResult(
            run_id=run.id,
            item_name=row['item_name'],
            mall_name=row['mall_name'],
            mall_display_name=row['mall_display_name'],
            price_text=row['price_text'],
        ))

    run.message_text = build_message_text(results)
    run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return run.id


# ---------------------------------------------------------------------------
# 실행 이력 / 화면 요약
# ---------------------------------------------------------------------------

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
    return session.scalars(
        select(RunHistory)
        .where(RunHistory.status == 'success')
        .order_by(RunHistory.id.desc())
        .limit(1)
    ).first()


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
    return display_name == '우리' or mall_name == OWN_MALL_NAME


def _format_signed_price(value: int) -> str:
    return f'{value:+,}'


def _format_signed_percent(value: float) -> str:
    return f'{value * 100:+.1f}%'


def build_our_price_map(run: RunHistory | None) -> dict[str, int]:
    if run is None:
        return {}
    price_map: dict[str, int] = {}
    for row in run.results:
        if not _is_our_mall(row):
            continue
        value = _price_to_int(row.price_text)
        if value is not None:
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
            severity_score = max(
                abs(avg_diff),
                abs(min_diff),
                int(abs(avg_ratio) * 1000),
                int(abs(min_ratio) * 1000),
            )
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
