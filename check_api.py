from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.naver_client import NaverCommerceClient


def main() -> None:
    products = NaverCommerceClient().list_products()
    print(f'API 연결 성공: 스마트스토어 채널 상품 {len(products):,}개 조회')
    for product in products[:10]:
        price = product.effective_price
        print(f'- {product.channel_product_no} | {product.name} | {price:,}원' if price is not None else f'- {product.channel_product_no} | {product.name} | 가격 없음')


if __name__ == '__main__':
    main()
