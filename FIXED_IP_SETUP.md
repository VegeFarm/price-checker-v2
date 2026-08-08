# 기존 재고자동화 중계서버 공용 사용 설정

V2는 별도 Windows 중계서버를 설치하지 않고 기존 재고자동화 중계서버를 같이 사용합니다.

구조:

```text
price-checker-v2 (Render)
  -> https://relay.chaesostock.com
  -> 기존 맥미니 중계서버
  -> Naver Commerce API
```

Render의 Web 서비스와 Cron 서비스 모두 다음 값을 동일하게 설정합니다.

```env
RELAY_BASE_URL=https://relay.chaesostock.com
RELAY_SHARED_TOKEN=<기존 재고자동화 Render의 RELAY_SHARED_TOKEN과 동일한 값>
RELAY_TIMEOUT=90
```

`RELAY_SHARED_TOKEN`은 GitHub 코드에 넣지 마세요. Render Environment에만 저장합니다.

기존 중계서버 규격과 동일하게 V2는 `POST /naver/products/search`를 호출하고, `Authorization: Bearer <RELAY_SHARED_TOKEN>` 헤더를 사용합니다.

`RELAY_BASE_URL`과 `RELAY_SHARED_TOKEN`이 설정되어 있으면 V2 Render는 네이버 API를 직접 호출하지 않습니다.
