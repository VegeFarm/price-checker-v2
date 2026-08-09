"""기존 DB를 모두 비우고 기본 설정으로 재생성합니다. 주의해서 사용하세요."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete
from core.bootstrap import initialize_app
from core.db import create_tables, get_session
from core.models import (
    AppSetting,
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


def main() -> None:
    create_tables()
    session = get_session()
    try:
        for model in (
            RunPriceResult,
            RunHistory,
            ManualCompetitorPrice,
            LegacyCompetitorProductRule,
            SearchKeywordRule,
            TargetProductIdRule,
            PriceRule,
            AppSetting,
            Item,
            Mall,
        ):
            session.execute(delete(model))
        session.commit()
    finally:
        session.close()
    initialize_app()
    print('기본 데이터 재입력 완료')


if __name__ == '__main__':
    main()
