# 고정 IP 중계 서버

이 폴더는 **네이버 커머스 API에 이미 허용된 공인 IP를 사용하는 기존 서버**에서 실행합니다.
Render는 네이버 API를 직접 호출하지 않고 이 중계 서버의 `/v1/products`만 호출합니다.
중계 서버가 네이버 API를 호출하므로 네이버에서 보는 출발 IP는 기존 허용 IP가 됩니다.

## 환경변수

`.env.example`을 `.env`로 복사한 뒤 아래 값을 입력합니다.

- `NAVER_COMMERCE_CLIENT_ID`: 기존 재고자동화 애플리케이션 ID
- `NAVER_COMMERCE_CLIENT_SECRET`: 기존 Secret
- `NAVER_TOKEN_TYPE=SELF`
- `RELAY_SHARED_KEY`: `python generate_key.py`로 생성한 긴 랜덤 키

## 실행

Windows: `start_windows.bat`

macOS/Linux: `./start_mac_linux.sh`

기본 포트는 8787입니다.

## 외부 공개

Render가 이 서버에 접속할 수 있는 HTTPS URL이 필요합니다. 권장 방식은 기존 도메인/리버스 프록시 또는 HTTPS 터널을 사용해 이 로컬 주소를 공개하는 것입니다.

`http://127.0.0.1:8787`

공개 URL 예시:

`https://naver-relay.example.com`

그 공개 URL을 Render의 `NAVER_RELAY_URL`에 넣습니다. `/v1/products`는 붙이지 않습니다.

## 점검

서버 내부에서:

`http://127.0.0.1:8787/health`

응답: `{"ok":true}`
