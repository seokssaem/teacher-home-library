# ☁️ 우리집 책장 v5 — 3차 세션: AWS Lightsail 배포 (상세 주석 / 강사용)

**범위:** 2차 세션(DB 연동 CI)까지 끝난 상태에서, `main`에 push하면 → 테스트 통과 → Docker 이미지 빌드/업로드 → **AWS Lightsail 서버가 자동으로 최신 이미지를 받아 실행**까지, `test.yml` 하나로 전체 파이프라인을 완성합니다.

**프로덕션 DB 방식: A안 확정** — 같은 Lightsail 인스턴스 안에 PostgreSQL도 컨테이너로 같이 실행합니다 (비용 없음, 기존 `docker-compose.yml` 구조 재사용).

---

## 1. Lightsail 인스턴스 준비 (사전 작업, 코드 아님)

1. AWS 콘솔 → **Lightsail** → **Create instance**
2. 플랫폼: `Linux/Unix` → 블루프린트: **OS Only → Ubuntu 24.04 LTS**
3. 인스턴스 플랜: 가장 저렴한 플랜(월 $5 내외)
4. **네트워킹 탭**: 고정 IP(Static IP) 발급 + 연결, 방화벽에 커스텀 TCP **8000, 8501** 포트 오픈
5. SSH 키페어 다운로드(`.pem`)

> ⚠️ 수업이 끝나면 인스턴스는 **정지가 아니라 삭제**해야 과금이 완전히 멈춘다.

---

## 2. 서버에 Docker + Compose 설치 (SSH 접속해서 1회만)

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
# docker-compose-plugin을 꼭 같이 설치 — 오늘은 docker run이 아니라
# docker compose(v2 문법, 공백 있음)로 배포하기 때문이다.
sudo usermod -aG docker $USER
# 이후 터미널을 한 번 다시 열어야 sudo 없이 docker 명령어가 동작한다.
```

---

## 3. 서버용 `.env` (상세 주석)

로컬 `.env`와는 다른, **서버 전용 파일**을 최초 1회 직접 만든다.

```bash
mkdir -p ~/home-library
nano ~/home-library/.env
```

```dotenv
# Docker Hub 계정명 — 아래 docker-compose.yml의 image: 태그를 완성하는 데 쓰인다.
DOCKER_USERNAME=계정명(예: seokssaem1)

# PostgreSQL 접속 정보 — db, api 컨테이너가 함께 사용한다.
# ⚠️ 로컬 개발용 .env를 그대로 복사하지 말 것 — 특히 비밀번호는 운영용으로 새로 정한다.
POSTGRES_DB=home_library
POSTGRES_USER=postgres
POSTGRES_PASSWORD=실제_운영용_비밀번호로_변경

# 국립중앙도서관 서지정보 API 키
NLK_SEARCH_KEY=실제_국립중앙도서관_API_키
```

> 이 `.env`는 GitHub에도, workflow 로그에도 전혀 노출되지 않고 서버 안에만 존재한다.
> `docker compose`가 컨테이너를 시작할 때 이 파일을 자동으로 읽어서 변수를 채운다
> (로컬 개발 때와 완전히 같은 방식 — `docker-compose.yml`이 `.env`를 읽는 원리 자체는 동일하다).

---

## 4. 서버용 `docker-compose.yml` (상세 주석)

로컬 개발용(`build: .`)과 **딱 한 부분**만 다르다 — `api`, `web`이 `build: .`(직접 빌드) 대신 `image:`(Docker Hub에서 받아쓰기)를 쓴다.

```yaml
# home-library / docker-compose.yml (서버 배포용)
# 로컬 개발용과의 차이: build: . 대신 image: 로 Docker Hub의 완성된 이미지를 받아씀

services:
  api:
    image: ${DOCKER_USERNAME}/home-library:latest
    # ← 로컬은 build: . 였던 부분. 서버는 소스 코드를 직접 조립하지 않고,
    #   GitHub Actions가 이미 완성해서 Docker Hub에 올려둔 이미지를 그대로 받아쓴다.
    container_name: booklib-api

    ports:
      - "8000:8000"

    environment:
      DATABASE_URL: postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      # 로컬과 완전히 동일한 형식 — "db"라는 서비스 이름을 호스트로 쓰는 원리도 그대로.

    env_file:
      - .env

    volumes:
      - ./uploads:/app/uploads

    depends_on:
      db:
        condition: service_healthy

  web:
    image: ${DOCKER_USERNAME}/home-library:latest
    # api와 완전히 동일한 이미지 — command만 다르게 덮어써서 Streamlit으로 실행한다.
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
      # 이 named volume이 배포 시마다 데이터가 사라지지 않는 이유의 핵심.
      # docker compose up -d는 이미지가 바뀐 서비스(api, web)만 컨테이너를 재생성하고,
      # db는 이미지(postgres:17)가 그대로면 건드리지 않는다.
      # 설령 db 컨테이너가 재생성되더라도, 실제 데이터는 이 볼륨에 남아있어서 보존된다.

    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  booklib_pgdata:
```

> 💾 **서버에는 소스 코드가 필요 없다.** `git clone`도 `Dockerfile`도 서버엔 없어도 된다.
> `~/home-library/`에 `docker-compose.yml`과 `.env` **딱 두 파일**만 있으면 충분하다.
> `uploads/` 폴더는 `docker compose up` 실행 시 없으면 자동으로 생성된다.

---

## 5. GitHub Secrets 추가 등록

기존 `DOCKER_USERNAME`, `DOCKER_TOKEN`은 그대로 두고, 아래 3개를 추가한다.

| Name | Value |
| --- | --- |
| `LIGHTSAIL_HOST` | Lightsail 인스턴스의 고정 IP |
| `LIGHTSAIL_USERNAME` | `ubuntu` (Lightsail Ubuntu 인스턴스 기본 계정명) |
| `LIGHTSAIL_SSH_KEY` | `.pem` 키 파일을 텍스트 에디터로 열어서 **내용 전체**(BEGIN~END 포함)를 복사해 붙여넣기 |

---

## 6. `test.yml`에 `deploy` job 추가 (상세 주석)

```yaml
  # ─────────────────────────────────────────────
  # 3단계: Deploy — Lightsail 서버가 최신 이미지를 받아 재기동
  # (needs: build 덕분에 이미지 빌드/업로드가 끝난 뒤에만 실행)
  # ─────────────────────────────────────────────
  deploy:
    needs: build
    # build job(Docker Hub 업로드)이 성공한 뒤에만 이 job이 시작된다.
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    # main에 실제로 merge/push됐을 때만 배포 — feature 브랜치에서는 배포 안 됨.

    steps:
      - name: SSH로 Lightsail 접속 후 컨테이너 교체
        uses: appleboy/ssh-action@v1.0.3
        # appleboy/ssh-action: GitHub Actions Runner에서 원격 서버로 SSH 접속해서
        # 임의의 셸 스크립트를 실행해주는 커뮤니티 액션.
        # 패치 버전(v1.0.3)까지 고정 — @master처럼 계속 바뀌는 참조를 쓰지 않는다.
        with:
          host: ${{ secrets.LIGHTSAIL_HOST }}
          username: ${{ secrets.LIGHTSAIL_USERNAME }}
          key: ${{ secrets.LIGHTSAIL_SSH_KEY }}
          # 위 세 값이 SSH 접속에 필요한 "호스트, 계정, 개인키" 삼총사.
          script: |
            cd ~/home-library
            # 4번에서 미리 만들어둔 docker-compose.yml, .env가 있는 폴더로 이동.
            docker compose pull
            # docker-compose.yml의 image: 에 적힌 최신 태그를 Docker Hub에서 새로 받아온다.
            docker compose up -d
            # 바뀐 이미지가 있는 컨테이너(api, web)만 자동으로 재생성.
            # db는 이미지가 안 바뀌었으면 그대로 유지되어 데이터가 보존된다.
            docker image prune -f
            # 갱신 후 남은 예전 이미지를 정리해 서버 디스크 용량을 절약한다.
```

> 💡 로컬 개발 때 쓰던 `docker compose up --build`(직접 빌드)와 달리,
> 서버에서는 `--build` 없이 `pull`만 쓴다 — 서버는 소스 코드를 빌드하는 게 아니라
> GitHub Actions가 이미 만들어서 Docker Hub에 올려둔 이미지를 **받아쓰기만** 하기 때문이다.

---

## 7. push 및 확인

```bash
git add .github
git commit -m "본인이름_비NCS_test"
git push origin 비NCS_영문이름
```

1. Actions 탭 → `test` → `build` → `deploy` 세 개가 순서대로 초록불이 되는지 확인
2. 브라우저로 `http://<LIGHTSAIL_HOST>:8000/docs`, `http://<LIGHTSAIL_HOST>:8501` 접속 확인
3. **데이터 보존 검증(권장 실습)**: 책 한 권 등록 → 아무 코드나 사소하게 고쳐서 다시 push(재배포 유도) → 아까 등록한 책이 그대로 남아있는지 확인 (`booklib_pgdata` named volume이 실제로 동작하는지 눈으로 확인하는 과정)

---

## 8. 자주 발생하는 문제

| 증상 | 원인 | 처방 |
| --- | --- | --- |
| `Permission denied (publickey)` | `LIGHTSAIL_SSH_KEY`에 `.pem` 내용을 잘못 붙여넣음 (일부 누락, 앞뒤 공백) | 키 파일 전체(BEGIN~END 포함)를 다시 정확히 복사해서 Secret 값 재등록 |
| `docker: 'compose' is not a docker command` | `docker-compose-plugin` 미설치 | 2단계 명령어를 서버에서 다시 실행 |
| `deploy` job은 실행됐는데 접속이 안 됨 | Lightsail 방화벽에 8000/8501번 포트를 안 열어둠 | 네트워킹 탭에서 커스텀 TCP 8000, 8501 규칙 추가 |
| 컨테이너는 떴는데 500 에러 | `.env`에 `POSTGRES_*` 값이 없거나 `docker-compose.yml`과 변수 이름이 안 맞음 | 3, 4번의 변수 이름(`DOCKER_USERNAME`, `POSTGRES_DB` 등)이 정확히 일치하는지 확인 |
| `docker: command not found` (SSH script 안에서) | Lightsail에 Docker 최초 설치를 안 함 | 2단계를 서버에서 먼저 실행 |
| `db` 컨테이너가 unhealthy로 계속 재시작 | `POSTGRES_PASSWORD`에 특수문자가 있어 `DATABASE_URL` 문자열이 깨짐 | 영문/숫자 위주의 단순한 비밀번호로 우선 테스트 |
| 배포는 됐는데 이전 버전이 계속 보임 | 브라우저 캐시, 또는 `docker compose pull`이 최신 태그를 못 받아옴 | 시크릿 창으로 재확인, `docker images`로 실제 받아진 이미지 생성 시각 확인 |
| `~/home-library` 폴더 자체가 없어서 `cd` 실패 | 서버용 `docker-compose.yml`/`.env` 준비를 안 함 | SSH 접속해서 `mkdir -p ~/home-library` 후 두 파일 배치 |

---

## 9. 오늘의 배포 성공 체크리스트

- [ ]  Lightsail 인스턴스 생성 + 고정 IP 연결 + 8000·8501번 포트 오픈
- [ ]  서버에 Docker + `docker-compose-plugin` 최초 설치 완료
- [ ]  `LIGHTSAIL_HOST`, `LIGHTSAIL_USERNAME`, `LIGHTSAIL_SSH_KEY` Secrets 등록
- [ ]  서버 `~/home-library/`에 `.env` 준비 (`DOCKER_USERNAME`, `POSTGRES_*`, `NLK_SEARCH_KEY`)
- [ ]  서버 `~/home-library/`에 배포용 `docker-compose.yml` 준비 (`build:` 대신 `image:`)
- [ ]  `test.yml`에 `deploy` job 추가 후 push
- [ ]  Actions 탭에서 `test → build → deploy` 전부 초록불
- [ ]  브라우저로 `http://<IP>:8000/shelf`, `http://<IP>:8501` 둘 다 접속 확인
- [ ]  책 등록 후 재배포해서 데이터가 그대로 남아있는지 확인 (named volume 보존 검증)
