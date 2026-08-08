from core.competitor_scraper import extract_price_from_html


def test_extract_json_ld_price():
    html = '''
    <html><head>
      <script type="application/ld+json">
      {"@type":"Product","offers":{"@type":"Offer","price":"21900"}}
      </script>
    </head></html>
    '''
    assert extract_price_from_html(html) == 21900


def test_extract_discounted_price_from_state_json():
    html = '<script>window.__STATE__={"discountedPrice": "12,300", "salePrice": 15000}</script>'
    assert extract_price_from_html(html) == 12300


def test_extract_meta_price():
    html = '<meta property="product:price:amount" content="8,900">'
    assert extract_price_from_html(html) == 8900
