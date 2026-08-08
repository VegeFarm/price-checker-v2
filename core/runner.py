from __future__ import annotations

from datetime import datetime, timezone

from core.bootstrap import initialize_app
from core.defaults import OWN_MALL_NAME
from core.db import get_session
from core.formatters import build_message_text
from core.naver_client import NaverCommerceClient, format_product_price, match_product
from core.repository import load_runtime_config, load_competitor_product_config, save_run_result
from core.telegram_sender import send_telegram_message
from core.competitor_scraper import CompetitorFetchError, CompetitorPriceFetcher


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
        target_malls, mall_display_names, search_keywords, target_product_ids, price_rules = load_runtime_config(session)
        competitor_config = load_competitor_product_config(session)
        products = NaverCommerceClient().list_products()
        competitor_fetcher = CompetitorPriceFetcher(min_delay=2.0, max_delay=5.0, timeout=20)
        competitor_errors: list[dict] = []
        competitor_request_count = 0
        results: dict[str, list[tuple[str, str]]] = {}

        for display_name, mall_keywords in search_keywords.items():
            mall_ids = target_product_ids.get(display_name, {})
            results[display_name] = []

            for mall in target_malls:
                mall_display = mall_display_names.get(mall, mall)
                price = ''
                if mall == OWN_MALL_NAME:
                    keyword = mall_keywords.get(mall, display_name)
                    target_id = mall_ids.get(mall, '')
                    product = match_product(products, keyword, target_id)
                    price = format_product_price(product)
                    price = apply_price_rule(display_name, mall, price, price_rules)
                else:
                    rule = competitor_config.get((display_name, mall), {'enabled': True, 'url': ''})
                    if rule.get('enabled', True) and rule.get('url'):
                        competitor_request_count += 1
                        try:
                            raw_price = competitor_fetcher.fetch_price(rule['url'])
                            price = f'{raw_price:,}'
                            price = apply_price_rule(display_name, mall, price, price_rules)
                        except CompetitorFetchError as exc:
                            competitor_errors.append({
                                'item_name': display_name,
                                'mall_name': mall_display,
                                'error': str(exc),
                            })

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
            'competitor_request_count': competitor_request_count,
            'competitor_errors': competitor_errors,
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
