from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, Item, Mall, ManualCompetitorPrice, SearchKeywordRule, TargetProductIdRule
from core.repository import (
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
    ])
    session.commit()
    return session


def test_parser_supports_blank_delete():
    entries, errors = parse_competitor_price_text(
        '*바질\n그린팜 - 45,000\n야채이야기 -\n'
    )
    assert not errors
    assert entries[0]['price'] == 45000
    assert entries[1]['price'] is None


def test_bulk_save_ignores_our_price_and_keeps_unmentioned_price():
    session = make_session()
    try:
        malls = {m.mall_display_name: m for m in session.query(Mall).all()}
        item = session.query(Item).filter_by(display_name='로케트').one()
        session.add(ManualCompetitorPrice(item_id=item.id, mall_id=malls['야채이야기'].id, price=55000))
        session.commit()

        result = save_manual_competitor_prices_from_text(
            session,
            '*로케트\n우리 - 40,000\n그린팜 - 57,000\n야채왕 - 53,000\n',
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

        result = save_manual_competitor_prices_from_text(session, '*바질\n그린팜 -\n')
        assert result['deleted'] == 1
        rows = session.query(ManualCompetitorPrice).all()
        assert len(rows) == 1
        assert rows[0].mall_id == malls['야채왕'].id
        assert rows[0].price == 50000
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
