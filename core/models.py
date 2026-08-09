from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Mall(Base):
    __tablename__ = 'mall_master'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mall_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    mall_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Item(Base):
    __tablename__ = 'item_master'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SearchKeywordRule(Base):
    """우리 상품의 검색어 fallback 규칙.

    기존 DB 호환을 위해 테이블명은 유지합니다. 화면에서는 '우리 상품 설정'에서
    상품 ID와 함께 한 번에 관리합니다.
    """

    __tablename__ = 'search_keyword_rule'
    __table_args__ = (UniqueConstraint('item_id', 'mall_id', name='uq_search_keyword_rule'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('item_master.id'), nullable=False)
    mall_id: Mapped[int] = mapped_column(ForeignKey('mall_master.id'), nullable=False)
    search_keyword: Mapped[str] = mapped_column(String(300), nullable=False, default='')


class TargetProductIdRule(Base):
    """우리 상품의 네이버 상품 ID 우선 매칭 규칙."""

    __tablename__ = 'target_product_id_rule'
    __table_args__ = (UniqueConstraint('item_id', 'mall_id', name='uq_target_product_id_rule'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('item_master.id'), nullable=False)
    mall_id: Mapped[int] = mapped_column(ForeignKey('mall_master.id'), nullable=False)
    target_product_id: Mapped[str] = mapped_column(String(100), nullable=False, default='')


class PriceRule(Base):
    __tablename__ = 'price_rule'
    __table_args__ = (UniqueConstraint('item_id', 'mall_id', name='uq_price_rule'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('item_master.id'), nullable=False)
    mall_id: Mapped[int] = mapped_column(ForeignKey('mall_master.id'), nullable=False)
    op: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class ManualCompetitorPrice(Base):
    """사용자가 직접 입력한 경쟁사 최신 가격."""

    __tablename__ = 'manual_competitor_price'
    __table_args__ = (UniqueConstraint('item_id', 'mall_id', name='uq_manual_competitor_price'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('item_master.id'), nullable=False)
    mall_id: Mapped[int] = mapped_column(ForeignKey('mall_master.id'), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AppSetting(Base):
    __tablename__ = 'app_setting'

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default='')


class LegacyCompetitorProductRule(Base):
    """구버전 경쟁사 URL 설정 테이블.

    직접 조회 기능은 삭제되었고 이 모델은 기존 DB의 URL 데이터를 안전하게 정리하기
    위한 호환 용도로만 남겨 둡니다. 새 코드에서는 이 테이블을 조회에 사용하지 않습니다.
    """

    __tablename__ = 'competitor_product_rule'
    __table_args__ = (UniqueConstraint('item_id', 'mall_id', name='uq_competitor_product_rule'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('item_master.id'), nullable=False)
    mall_id: Mapped[int] = mapped_column(ForeignKey('mall_master.id'), nullable=False)
    product_url: Mapped[str] = mapped_column(String(1000), nullable=False, default='')
    search_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RunHistory(Base):
    __tablename__ = 'run_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False, default='')
    error_text: Mapped[str] = mapped_column(Text, nullable=False, default='')

    results: Mapped[list['RunPriceResult']] = relationship(back_populates='run', cascade='all, delete-orphan')


class RunPriceResult(Base):
    __tablename__ = 'run_price_result'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('run_history.id'), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mall_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mall_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    price_text: Mapped[str] = mapped_column(String(100), nullable=False, default='')

    run: Mapped['RunHistory'] = relationship(back_populates='results')
