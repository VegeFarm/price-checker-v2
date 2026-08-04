from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


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
    __tablename__ = 'search_keyword_rule'
    __table_args__ = (UniqueConstraint('item_id', 'mall_id', name='uq_search_keyword_rule'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('item_master.id'), nullable=False)
    mall_id: Mapped[int] = mapped_column(ForeignKey('mall_master.id'), nullable=False)
    search_keyword: Mapped[str] = mapped_column(String(300), nullable=False, default='')


class TargetProductIdRule(Base):
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
