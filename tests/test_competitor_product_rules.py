from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.models import Base, CompetitorProductRule, Item, Mall
from core.repository import (
    get_competitor_product_df,
    load_competitor_product_config,
    save_competitor_product_df,
)


def _make_session():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all([
        Mall(mall_name='채소팜', mall_display_name='우리', enabled=True, sort_order=1),
        Mall(mall_name='경쟁사A', mall_display_name='A', enabled=True, sort_order=2),
        Mall(mall_name='경쟁사B', mall_display_name='B', enabled=True, sort_order=3),
        Item(display_name='바질', enabled=True, sort_order=1),
        Item(display_name='딜', enabled=True, sort_order=2),
    ])
    session.commit()
    return session


def test_competitor_settings_are_one_row_per_item_and_default_checked():
    session = _make_session()
    try:
        df = get_competitor_product_df(session)
        assert list(df.columns) == ['상품명', '검색여부', 'A URL', 'B URL']
        assert df['상품명'].tolist() == ['바질', '딜']
        assert df['검색여부'].tolist() == [True, True]
    finally:
        session.close()


def test_one_checkbox_controls_all_competitors_for_item():
    session = _make_session()
    try:
        df = get_competitor_product_df(session)
        df.loc[df['상품명'] == '바질', '검색여부'] = False
        df.loc[df['상품명'] == '바질', 'A URL'] = 'https://example.com/a'
        df.loc[df['상품명'] == '바질', 'B URL'] = 'https://example.com/b'
        save_competitor_product_df(session, df)

        config = load_competitor_product_config(session)
        assert config[('바질', '경쟁사A')] == {'enabled': False, 'url': 'https://example.com/a'}
        assert config[('바질', '경쟁사B')] == {'enabled': False, 'url': 'https://example.com/b'}
        assert config[('딜', '경쟁사A')]['enabled'] is True
        assert config[('딜', '경쟁사B')]['enabled'] is True
    finally:
        session.close()


def test_new_item_appears_automatically_with_default_checked():
    session = _make_session()
    try:
        session.add(Item(display_name='루꼴라', enabled=True, sort_order=3))
        session.commit()
        df = get_competitor_product_df(session)
        row = df[df['상품명'] == '루꼴라'].iloc[0]
        assert bool(row['검색여부']) is True
        assert row['A URL'] == ''
        assert row['B URL'] == ''
    finally:
        session.close()
