# 채소팜 네이버 커머스 API 가격조회

기존 가격비교 관리자 화면 구조를 유지하면서, **네이버 커머스 API에서 채소팜 상품 가격만 조회**하도록 만든 Streamlit 프로그램입니다.
그린팜·야채왕·야채이야기·쉐프의정원 열은 향후 연동을 위해 유지하며 가격은 공백으로 출력합니다.

## 작동 방식

1. OAuth2 Client Credentials 방식으로 네이버 커머스 API 토큰을 발급합니다.
2. `/v1/products/search`에서 내 스마트스토어 채널 상품 전체를 최대 500개씩 조회합니다.
3. `상품 ID 규칙`의 채널 상품번호/원상품번호를 먼저 찾습니다.
4. 번호가 없으면 `검색 규칙`의 상품명과 네이버 상품명을 비교합니다.
5. `discountedPrice`가 있으면 할인가를, 없으면 `salePrice`를 표시합니다.
6. 경쟁사 가격은 의도적으로 공백으로 저장·표시합니다.

## 1. 네이버 커머스 API 준비

네이버 커머스 API센터에서 **내 스토어용 애플리케이션**을 만들고 상품 조회 권한을 설정합니다.
기존 네이버 개발자센터의 쇼핑 검색 API Client ID/Secret과는 다른 값입니다.

발급받을 값:

- 애플리케이션 ID → `NAVER_COMMERCE_CLIENT_ID`
- 애플리케이션 시크릿 → `NAVER_COMMERCE_CLIENT_SECRET`
- 자가 애플리케이션은 일반적으로 `NAVER_TOKEN_TYPE=SELF`

API센터에서 호출 서버 IP 등록이 요구되는 계정이라면 Render 배포 환경의 고정 IP 사용 여부도 확인해야 합니다.

## 2. 로컬 실행

### Windows에서 가장 쉬운 방법

1. `01_최초설치.bat` 실행
2. 자동으로 열린 `.env` 메모장에 API ID와 Secret 입력 후 저장
3. `02_API연결확인.bat` 실행
4. 성공하면 `03_프로그램실행.bat` 실행

### 명령어로 실행

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 커머스 API 값을 입력합니다.

```env
NAVER_COMMERCE_CLIENT_ID=발급받은_애플리케이션_ID
NAVER_COMMERCE_CLIENT_SECRET=발급받은_애플리케이션_시크릿
NAVER_TOKEN_TYPE=SELF
DATABASE_URL=sqlite:///local.db
```

API 연결 확인:

```bash
python scripts/check_api.py
```

웹 실행:

```bash
streamlit run app.py
```

브라우저에서 보통 `http://localhost:8501`로 열립니다.

## 3. GitHub 업로드

이 폴더 안의 파일을 저장소 최상위에 그대로 올리면 됩니다.

```bash
git init
git add .
git commit -m "네이버 커머스 API 가격조회 프로그램"
git branch -M main
git remote add origin 본인_GitHub_저장소_URL
git push -u origin main
```

`.env`, 로컬 DB, 캐시 파일은 `.gitignore`에 포함되어 GitHub에 올라가지 않습니다.

## 4. Render 배포

저장소에 `render.yaml`이 포함되어 있습니다. Render에서 **New Blueprint**로 GitHub 저장소를 연결합니다.

필수 환경변수:

- `NAVER_COMMERCE_CLIENT_ID`
- `NAVER_COMMERCE_CLIENT_SECRET`
- `NAVER_TOKEN_TYPE=SELF`
- `DATABASE_URL`

선택 환경변수:

- `NAVER_USE_DISCOUNTED_PRICE=true`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Render에서 SQLite를 사용하면 재배포 시 데이터가 초기화될 수 있으므로 운영용은 PostgreSQL을 권장합니다. `DATABASE_URL`에는 PostgreSQL의 **External Database URL**을 입력합니다.

수동 설정 시:

- Build Command: `pip install -r requirements.txt`
- Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

## 5. 자동 실행

Render Cron Job을 별도로 만들 때:

- Build Command: `pip install -r requirements.txt`
- Start Command: `python cron_entry.py`
- 한국시간 오전 8시 30분: UTC 기준 Cron `30 23 * * *`

웹 서비스와 Cron Job은 반드시 같은 `DATABASE_URL`을 사용해야 합니다.

## 6. 상품 매칭 수정

가격이 비어 있거나 다른 상품이 잡히면 다음 순서로 수정합니다.

1. 스마트스토어 상품 URL 또는 판매자센터에서 **채널 상품번호**를 확인합니다.
2. 프로그램의 `상품 ID 규칙` 페이지에서 해당 품목의 `채소팜` 열에 번호를 입력합니다.
3. 저장 후 `지금 실행`을 다시 누릅니다.

상품번호가 없을 때만 상품명 자동 매칭을 사용합니다. 용량·수량이 포함된 검색어를 넣는 것이 안전합니다.

## 7. 기본 가격 규칙

기존 설정 중 채소팜 단위 환산 규칙만 유지했습니다.

- 쌈배추(1kg): 채소팜 500g 가격 × 2
- 청경채(4kg): 채소팜 2kg 가격 × 2
- 양상추: 채소팜 6통 가격 × 2

`가격 규칙` 페이지에서 자유롭게 수정할 수 있습니다.

## 8. 테스트

```bash
python -m unittest discover -s tests -v
```
