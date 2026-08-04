import unittest

import core.naver_client as naver_client
from core.naver_client import (
    CommerceProduct,
    flatten_products,
    format_product_price,
    generate_client_secret_sign,
    match_product,
)


class NaverClientTests(unittest.TestCase):
    @unittest.skipIf(naver_client.bcrypt is None, 'bcrypt not installed in test environment')
    def test_official_signature_example(self):
        actual = generate_client_secret_sign(
            'aaaabbbbcccc',
            '$2a$10$abcdefghijklmnopqrstuv',
            1643961623299,
        )
        self.assertEqual(
            actual,
            'JDJhJDEwJGFiY2RlZmdoaWprbG1ub3BxcnN0dXVCVldZSk42T0VPdEx1OFY0cDQxa2IuTnpVaUEzbmsy',
        )

    def test_flatten_and_discounted_price(self):
        data = {
            'contents': [{
                'originProductNo': 11,
                'channelProducts': [{
                    'channelServiceType': 'STOREFARM',
                    'channelProductNo': 22,
                    'name': '고수 1단',
                    'salePrice': 5000,
                    'discountedPrice': 4500,
                    'statusType': 'SALE',
                }],
            }]
        }
        products = flatten_products(data)
        self.assertEqual(len(products), 1)
        self.assertEqual(format_product_price(products[0]), '4,500')

    def test_id_match_has_priority(self):
        products = [
            CommerceProduct('고수 1단', '100', '10', '', 5000, None, 'SALE'),
            CommerceProduct('고수 1단 특품', '200', '20', '', 6000, None, 'SALE'),
        ]
        self.assertEqual(match_product(products, '고수 1단', '200').channel_product_no, '200')

    def test_wrong_weight_is_rejected(self):
        products = [
            CommerceProduct('딜 500g', '1', '11', '', 5000, None, 'SALE'),
            CommerceProduct('딜 1kg', '2', '22', '', 9000, None, 'SALE'),
        ]
        self.assertEqual(match_product(products, '딜 1kg').channel_product_no, '2')


if __name__ == '__main__':
    unittest.main()
