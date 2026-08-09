from __future__ import annotations

from datetime import datetime, timezone

from core.bootstrap import initialize_app
from core.defaults import OWN_MALL_NAME
from core.db import get_session
from core.formatters import build_message_text
from core.naver_client import NaverCommerceClient, format_product_price, match_product
from core.repository import load_runtime_config, save_run_result
from core.telegram_sender import send_telegram_message


def apply_price_rule(display_name, mall_name, price_text, price_rules):
    if not price_text:
        return ''

    rules_by_item = price_rules.get(display_name, {})
    rule = rules_by_item.get(mall_name)
    if not rule:
        return price_text

    try:
        op, value = rule
        price = int(str(price_text).replace(',', '').strip())
        if op == 'mul':
            result = price * value
        elif op == 'add':
            result = price + value
        elif op == 'sub':
            result = price - value
        elif op == 'set':
            result = value
        elif op == 'rate':
            result = round(price * value)
        else:
            return price_text
        return f'{int(result):,}'
    except Exception:
        return price_text


def run_price_check(trigger_type: str = 'manual') -> dict:
    initialize_app()
    started_at = datetime.now(timezone.utc)
    session = get_session()
    rows: list[dict] = []
    message_text = ''
    try:
        (
            target_malls,
            mall_display_names,
            own_product_config,
            price_rules,
            manual_competitor_prices,
        ) = load_runtime_config(session)

        products = NaverCommerceClient().list_products()
        results: dict[str, list[tuple[str, str]]] = {}
        own_matched_count = 0
        own_missing_count = 0
        manual_price_count = 0

        for display_name, own_config in own_product_config.items():
            results[display_name] = []
            for mall in target_malls:
                mall_display = mall_display_names.get(mall, mall)
                price = ''

                if mall == OWN_MALL_NAME:
                    # match_product는 상품 ID를 먼저 찾고, 없거나 실패하면 검색어로 fallback 합니다.
                    product = match_product(
                        products,
                        own_config.get('search_keyword', display_name),
                        own_config.get('target_product_id', ''),
                    )
                    price = format_product_price(product)
                    price = apply_price_rule(display_name, mall, price, price_rules)
                    if price:
                        own_matched_count += 1
                    else:
                        own_missing_count += 1
                else:
                    manual_price = manual_competitor_prices.get((display_name, mall))
                    if manual_price is not None:
                        # 경쟁사 수동 가격은 사용자가 입력한 최종 비교 가격을 그대로 사용합니다.
                        price = f'{int(manual_price):,}'
                        manual_price_count += 1

                results[display_name].append((mall_display, price))
                rows.append({
                    'item_name': display_name,
                    'mall_name': mall,
                    'mall_display_name': mall_display,
                    'price_text': price,
                })

        message_text = build_message_text(results)
        finished_at = datetime.now(timezone.utc)
        run_id = save_run_result(
            session=session,
            trigger_type=trigger_type,
            status='success',
            started_at=started_at,
            finished_at=finished_at,
            message_text=message_text,
            error_text='',
            rows=rows,
        )
        if trigger_type == 'cron':
            send_telegram_message(message_text)
        return {
            'status': 'success',
            'run_id': run_id,
            'message_text': message_text,
            'rows': rows,
            'product_count': len(products),
            'own_matched_count': own_matched_count,
            'own_missing_count': own_missing_count,
            'manual_competitor_price_count': manual_price_count,
        }
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        save_run_result(
            session=session,
            trigger_type=trigger_type,
            status='fail',
            started_at=started_at,
            finished_at=finished_at,
            message_text=message_text,
            error_text=str(exc),
            rows=rows,
        )
        raise
    finally:
        session.close()
