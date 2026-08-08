from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.bootstrap import initialize_app

if __name__ == '__main__':
    initialize_app()
    print('DB 초기화 완료')
