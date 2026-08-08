# 기존 네이버 허용 IP 재사용 설정

목표: 네이버 API 호출 출발 IP를 기존 허용 IP(예: 121.167.202.38)로 유지합니다.

## 구성

- Render의 `price-checker-v2-web` / `price-checker-v2-cron`: 가격 비교 UI와 스케줄 실행
- 기존 허용 IP 서버: `relay/` 중계 서버 실행
- 네이버 API: 기존 허용 IP에서 들어온 호출로 인식

## 1) 기존 허용 IP 서버에서 relay 실행

`relay/` 폴더만 복사합니다.

1. `relay/.env.example` → `relay/.env` 복사
2. 기존 재고자동화에 쓰는 네이버 애플리케이션 ID/Secret 입력
3. `python generate_key.py` 실행 후 나온 값을 `RELAY_SHARED_KEY`에 입력
4. Windows: `start_windows.bat`, macOS/Linux: `./start_mac_linux.sh`
5. `http://127.0.0.1:8787/health`가 `{"ok":true}`를 반환하는지 확인

중계 서버는 기존 재고자동화 프로세스와 별도 프로세스로 실행되므로 기존 프로그램 코드를 변경하지 않습니다.

## 2) 중계 서버를 HTTPS로 공개

Render가 접속할 수 있는 HTTPS URL이 필요합니다. 기존 도메인/리버스 프록시/HTTPS 터널 중 하나를 이용해 `127.0.0.1:8787`을 공개합니다.

예: `https://naver-relay.example.com`

## 3) Render 환경변수

Web과 Cron 양쪽에 동일하게 입력합니다.

- `NAVER_RELAY_URL=https://naver-relay.example.com`
- `NAVER_RELAY_KEY=<relay의 RELAY_SHARED_KEY와 동일>`
- `NAVER_RELAY_TIMEOUT=90`

기존 `NAVER_COMMERCE_CLIENT_ID` / `NAVER_COMMERCE_CLIENT_SECRET`은 남아 있어도 되지만, `NAVER_RELAY_URL`이 설정되면 Render에서는 직접 네이버 API를 호출하지 않습니다.

## 4) 네이버 API 호출 IP

기존 허용 IP는 그대로 둡니다. 별도 Render IP를 추가할 필요가 없습니다.

## 5) 테스트

1. Render 재배포
2. 가격조회 화면에서 `고정 IP 중계 서버 모드로 연결됩니다.` 문구 확인
3. `지금 실행` 클릭
4. 네이버 IP 오류가 사라지고 상품 개수가 표시되는지 확인
