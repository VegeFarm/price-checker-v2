from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, Item, Mall, ManualCompetitorPrice, SearchKeywordRule, TargetProductIdRule
from core.repository import (
    get_manual_competitor_price_text,
    get_own_product_settings_df,
    parse_competitor_price_text,
    save_manual_competitor_prices_from_text,
    save_own_product_settings_df,
)


def make_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add_all([
        Mall(mall_name='채소팜', mall_display_name='우리', enabled=True, sort_order=1),
        Mall(mall_name='싱싱채소 그린팜', mall_display_name='그린팜', enabled=True, sort_order=2),
        Mall(mall_name='야채왕', mall_display_name='야채왕', enabled=True, sort_order=3),
        Mall(mall_name='야채이야기', mall_display_name='야채이야기', enabled=True, sort_order=4),
        Mall(mall_name='쉐프의 정원', mall_display_name='쉐프의정원', enabled=True, sort_order=5),
    ])
    session.flush()
    session.add_all([
        Item(display_name='로케트', enabled=True, sort_order=1),
        Item(display_name='바질', enabled=True, sort_order=2),
        Item(display_name='와일드', enabled=True, sort_order=3),
    ])
    session.commit()
    return session


def test_parser_supports_blank_delete():
    entries, errors = parse_competitor_price_text(
        '*바질\n그린팜 - 45,000\n야채이야기 -\n',
        known_item_names=['바질'],
        known_mall_labels=['우리', '그린팜', '야채왕', '야채이야기', '쉐프의정원'],
    )
    assert not errors
    assert entries[0]['price'] == 45000
    assert entries[1]['price'] is None


def test_parser_supports_no_star_and_no_dash():
    entries, errors = parse_competitor_price_text(
        '로케트\n그린팜 55,000\n야채왕 55000\n와일드\n그린팜 - 20,000\n',
        known_item_names=['로케트', '바질', '와일드'],
        known_mall_labels=['우리', '그린팜', '야채왕', '야채이야기', '쉐프의정원'],
    )
    assert not errors
    assert entries[0]['item_name'] == '로케트'
    assert entries[0]['mall_label'] == '그린팜'
    assert entries[0]['price'] == 55000
    assert entries[1]['mall_label'] == '야채왕'
    assert entries[1]['price'] == 55000
    assert entries[2]['item_name'] == '와일드'
    assert entries[2]['price'] == 20000


def test_parser_supports_abbreviated_competitor_prices():
    entries, errors = parse_competitor_price_text(
        '*바질\n그린팜 - 7\n야채왕 - 15\n야채이야기 - 135\n쉐프의정원 - 7500\n',
        known_item_names=['바질'],
        known_mall_labels=['우리', '그린팜', '야채왕', '야채이야기', '쉐프의정원'],
    )
    assert not errors
    assert [entry['price'] for entry in entries] == [7000, 15000, 13500, 7500]


def test_parser_keeps_exact_prices_with_commas_or_full_digits():
    entries, errors = parse_competitor_price_text(
        '*바질\n그린팜 - 7,500\n야채왕 - 13,500\n야채이야기 - 13,550\n쉐프의정원 - 13500\n',
        known_item_names=['바질'],
        known_mall_labels=['우리', '그린팜', '야채왕', '야채이야기', '쉐프의정원'],
    )
    assert not errors
    assert [entry['price'] for entry in entries] == [7500, 13500, 13550, 13500]


def test_parser_rejects_malformed_comma_price_instead_of_guessing():
    entries, errors = parse_competitor_price_text(
        '*바질\n그린팜 - 13,50\n',
        known_item_names=['바질'],
        known_mall_labels=['우리', '그린팜'],
    )
    assert entries == []
    assert errors


def test_bulk_save_ignores_our_price_and_keeps_unmentioned_price():
    session = make_session()
    try:
        malls = {m.mall_display_name: m for m in session.query(Mall).all()}
        item = session.query(Item).filter_by(display_name='로케트').one()
        session.add(ManualCompetitorPrice(item_id=item.id, mall_id=malls['야채이야기'].id, price=55000))
        session.commit()

        result = save_manual_competitor_prices_from_text(
            session,
            '로케트\n우리 - 40,000\n그린팜 57,000\n야채왕 - 53,000\n',
        )
        assert result['ignored_own'] == 1
        saved = {
            (row.item_id, row.mall_id): row.price
            for row in session.query(ManualCompetitorPrice).all()
        }
        assert saved[(item.id, malls['그린팜'].id)] == 57000
        assert saved[(item.id, malls['야채왕'].id)] == 53000
        assert saved[(item.id, malls['야채이야기'].id)] == 55000
    finally:
        session.close()


def test_explicit_blank_deletes_only_that_price():
    session = make_session()
    try:
        malls = {m.mall_display_name: m for m in session.query(Mall).all()}
        item = session.query(Item).filter_by(display_name='바질').one()
        session.add_all([
            ManualCompetitorPrice(item_id=item.id, mall_id=malls['그린팜'].id, price=45000),
            ManualCompetitorPrice(item_id=item.id, mall_id=malls['야채왕'].id, price=50000),
        ])
        session.commit()

        result = save_manual_competitor_prices_from_text(session, '바질\n그린팜 -\n')
        assert result['deleted'] == 1
        rows = session.query(ManualCompetitorPrice).all()
        assert len(rows) == 1
        assert rows[0].mall_id == malls['야채왕'].id
        assert rows[0].price == 50000
    finally:
        session.close()


def test_current_competitor_price_text_contains_every_item_and_mall():
    session = make_session()
    try:
        malls = {m.mall_display_name: m for m in session.query(Mall).all()}
        rocket = session.query(Item).filter_by(display_name='로케트').one()
        session.add_all([
            ManualCompetitorPrice(item_id=rocket.id, mall_id=malls['그린팜'].id, price=55000),
            ManualCompetitorPrice(item_id=rocket.id, mall_id=malls['야채왕'].id, price=13500),
        ])
        session.commit()

        text = get_manual_competitor_price_text(session)

        assert text.startswith('로케트\n그린팜 - 55,000\n야채왕 - 13,500')
        assert '야채이야기 -\n쉐프의정원 -' in text
        assert '\n\n바질\n그린팜 -\n야채왕 -' in text
        assert '\n\n와일드\n그린팜 -\n야채왕 -' in text
        assert '\n우리 -' not in text
    finally:
        session.close()


def test_saving_full_current_text_does_not_rewrite_unchanged_prices():
    session = make_session()
    try:
        malls = {m.mall_display_name: m for m in session.query(Mall).all()}
        rocket = session.query(Item).filter_by(display_name='로케트').one()
        session.add(ManualCompetitorPrice(
            item_id=rocket.id,
            mall_id=malls['그린팜'].id,
            price=55000,
        ))
        session.commit()

        text = get_manual_competitor_price_text(session)
        result = save_manual_competitor_prices_from_text(session, text)

        assert result['saved'] == 0
        assert result['unchanged'] == 1
        assert result['deleted'] == 0
    finally:
        session.close()


def test_own_product_settings_combines_id_and_search_keyword():
    session = make_session()
    try:
        own = session.query(Mall).filter_by(mall_name='채소팜').one()
        rocket = session.query(Item).filter_by(display_name='로케트').one()
        session.add(SearchKeywordRule(item_id=rocket.id, mall_id=own.id, search_keyword='로케트 1kg'))
        session.add(TargetProductIdRule(item_id=rocket.id, mall_id=own.id, target_product_id='12345'))
        session.commit()

        df = get_own_product_settings_df(session)
        row = df[df['상품명'] == '로케트'].iloc[0]
        assert row['상품 ID'] == '12345'
        assert row['검색어'] == '로케트 1kg'

        edited = df.copy()
        edited.loc[edited['상품명'] == '로케트', '상품 ID'] = '99999'
        edited.loc[edited['상품명'] == '로케트', '검색어'] = '와일드루꼴라 1kg'
        save_own_product_settings_df(session, edited)

        df2 = get_own_product_settings_df(session)
        row2 = df2[df2['상품명'] == '로케트'].iloc[0]
        assert row2['상품 ID'] == '99999'
        assert row2['검색어'] == '와일드루꼴라 1kg'
    finally:
        session.close()


def test_competitor_save_refreshes_latest_run_immediately():
    from datetime import datetime
    from core.models import RunHistory, RunPriceResult
    from core.repository import get_latest_run

    session = make_session()
    try:
        malls = {m.mall_display_name: m for m in session.query(Mall).all()}
        run = RunHistory(
            trigger_type='manual',
            status='success',
            started_at=datetime.now(),
            finished_at=datetime.now(),
            message_text='*바질\n우리 - 43,000\n그린팜 -',
            error_text='',
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        session.add_all([
            RunPriceResult(
                run_id=run.id,
                item_name='바질',
                mall_name='채소팜',
                mall_display_name='우리',
                price_text='43,000',
            ),
            RunPriceResult(
                run_id=run.id,
                item_name='바질',
                mall_name=malls['그린팜'].mall_name,
                mall_display_name='그린팜',
                price_text='',
            ),
        ])
        session.commit()

        result = save_manual_competitor_prices_from_text(session, '바질\n그린팜 45,000\n')
        assert result['refreshed_run_id'] == run.id
        latest = get_latest_run(session)
        assert latest is not None
        assert '그린팜 - 45,000' in latest.message_text
        our_rows = [r for r in latest.results if r.mall_display_name == '우리' and r.item_name == '바질']
        assert our_rows[0].price_text == '43,000'
    finally:
        session.close()
