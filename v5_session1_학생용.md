# 🐳 우리집 책장 v5 — 1차 세션 후반부 (Dockerfile → docker-compose.yml → build job)

**범위:** CI(test job)는 지난 시간에 완료된 상태를 전제로, 오늘 이어서 만든 `Dockerfile`, `docker-compose.yml`, `test.yml`의 `build` job까지 — 1차 세션(CI+Build)의 나머지 전체입니다.

---

## 1. `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY database.py .
COPY models.py .
COPY streamlit_app.py .
COPY services/ ./services/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000
EXPOSE 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 2. `docker-compose.yml` (로컬 개발용, `build: .` 버전)

```yaml
services:
  api:
    build: .
    container_name: booklib-api

    ports:
      - "8000:8000"

    environment:
      DATABASE_URL: postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

    env_file:
      - .env

    volumes:
      - ./uploads:/app/uploads

    depends_on:
      db:
        condition: service_healthy

  web:
    build: .
    container_name: booklib-web

    ports:
      - "8501:8501"

    environment:
      API_URL: http://api:8000

    depends_on:
      - api

    command: >
      streamlit run streamlit_app.py
      --server.address=0.0.0.0
      --server.port=8501

  db:
    image: postgres:17
    container_name: booklib-db

    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

    volumes:
      - booklib_pgdata:/var/lib/postgresql/data

    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  booklib_pgdata:
```

---

## 3. `.github/workflows/test.yml` — 완성본 (`test` + `build`)

```yaml
name: 우리집 책장 CI/CD (테스트 + 빌드)

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: 1. 저장소 코드 가져오기
        uses: actions/checkout@v4

      - name: 2. Python 설치하기
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: 3. 패키지 설치하기
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: 4. 테스트 실행하기
        run: python -m pytest -v

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - name: 코드 가져오기
        uses: actions/checkout@v4

      - name: Docker Hub 로그인
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}

      - name: 이미지 빌드 및 Docker Hub 업로드
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ secrets.DOCKER_USERNAME }}/home-library:latest
```

---

## 4. 오늘 새로 등록한 GitHub Secrets 요약

| Name | Value | 발급처 |
| --- | --- | --- |
| `DOCKER_USERNAME` | Docker Hub 계정명 | — |
| `DOCKER_TOKEN` | Access Token (비밀번호 아님, `Read & Write` 권한) | Docker Hub → Account Settings → Security → New Access Token |

---

## 5. 로컬 테스트 vs GitHub Actions Build

| | 무엇을 하나 | 어떤 도구 | `.env` 필요? |
| --- | --- | --- | --- |
| 로컬 테스트 | api+web+db 세 컨테이너를 실제로 띄워서 눈으로 확인 | `docker compose up --build` | ✅ 필요 (컨테이너가 실행되니까) |
| GitHub Actions `build` job | 이미지를 빌드해서 Docker Hub에 올리기만 함 (실행 X) | `docker/build-push-action` | ❌ 불필요 |

---

## 6. push 명령어

```bash
git add Dockerfile docker-compose.yml .github
git commit -m "본인이름_비NCS_test"
git push origin 비NCS_영문이름
```

push 후 Actions 탭에서 `test` → `build` 순서로 초록불이 뜨는지, [Docker Hub](https://hub.docker.com)에 `home-library:latest` 이미지가 실제로 올라왔는지 확인하면 1차 세션이 끝납니다.
