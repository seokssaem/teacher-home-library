# 🐳 우리집 책장 v5 — 1차 세션 후반부 상세 주석 (Dockerfile → docker-compose.yml → build job)

**범위:** CI(test job)는 지난 시간에 완료된 상태를 전제로, 오늘 이어서 만든 `Dockerfile`, `docker-compose.yml`, 그리고 `test.yml`의 `build` job까지 — 1차 세션(CI+Build)의 나머지 전체입니다.

---

## 	CI(test job) 확인	✅ 지난 시간에 완료 — .github/workflows/test.yml, tests/test_main.py 이미 있음

## Dockerfile 저장소 루트에 추가	⬜ 오늘 첫 작업

## 1. `Dockerfile` — 상세 주석

```dockerfile
# 우리집 책장 v4 - Dockerfile
# 이 파일은 "컨테이너 안에 우리 앱을 어떻게 조립할지"를 적어두는 설계도다.
# db  --> PostgreSQL 17 (공식 이미지를 그대로 쓰므로 이 Dockerfile과는 무관)
# api --> FastAPI (이 이미지로 만들어지는 컨테이너)
# web --> Streamlit (api와 똑같은 이 이미지를 공유하고, command만 다르게 덮어씀)

FROM python:3.12-slim
# FROM: 이 이미지가 어떤 "베이스 이미지" 위에서 시작할지 정한다.
# python:3.12-slim은 파이썬 3.12가 이미 설치된 아주 가벼운(slim) 리눅스 이미지.
# slim이 아닌 python:3.12를 쓰면 용량이 훨씬 크다 (불필요한 도구까지 다 들어있음).

WORKDIR /app
# WORKDIR: 이후 나오는 모든 명령어(COPY, RUN 등)가 실행되는 "현재 위치"를 지정.
# 컨테이너 내부에 /app 폴더가 없으면 자동으로 만들고 그 안으로 들어간다.
# ⚠️ 이건 우리 로컬 프로젝트에 app 폴더를 만들라는 뜻이 절대 아니다 —
#    "컨테이너 내부"에만 존재하는 가상의 작업 폴더다.

# ── 1단계: 패키지 설치 (코드보다 먼저!) ──────────────────────────
COPY requirements.txt .
# COPY 원본경로 대상경로 : 로컬(호스트)의 파일을 컨테이너 안으로 복사.
# requirements.txt "만" 먼저 복사하는 이유:
#   Docker는 레이어(layer) 단위로 캐시를 관리한다.
#   requirements.txt가 안 바뀌면, 코드를 아무리 자주 고쳐도
#   'pip install' 레이어는 매번 다시 실행하지 않고 캐시를 재사용해서 빌드가 빨라진다.
RUN pip install --no-cache-dir -r requirements.txt
# RUN: 이미지를 만드는 "빌드 시점"에 한 번 실행되는 명령어.
# --no-cache-dir: pip이 다운로드 캐시를 이미지 안에 남기지 않게 해서 이미지 용량을 줄인다.

# ── 2단계: 소스 코드 복사 ──────────────────────────────────────
COPY main.py .
COPY database.py .
COPY models.py .
COPY streamlit_app.py .
COPY services/ ./services/
COPY templates/ ./templates/
COPY static/ ./static/
# 폴더 전체를 복사할 땐 "원본폴더/ 대상폴더/" 형태로 슬래시를 붙인다.
# ⚠️ templates/, static/ 이 두 줄이 빠지면:
#   main.py의 Jinja2Templates(directory='templates'),
#   StaticFiles(directory='static') 가 컨테이너 안에서 그 폴더를 못 찾아서
#   docker build는 성공해도 docker run(컨테이너 실행) 시점에
#   "Directory 'static' does not exist" 에러로 서버가 즉시 죽는다.
# tests/ 폴더는 여기 없다 — 테스트 코드는 "이미지 안에 넣어서 배포할 것"이 아니라
# CI(GitHub Actions Runner)에서만 실행되면 되기 때문에 이미지에 포함시키지 않는다.

# ── 3단계: 포트 문서화 ──────────────────────────────────────────
EXPOSE 8000
EXPOSE 8501
# EXPOSE: "이 컨테이너는 몇 번 포트를 쓸 예정이다"라고 문서로 남기는 명령어.
# 실제로 포트를 열어주는 효과는 없다 (그건 docker-compose.yml의 ports: 항목이 담당).
# 8000 --> FastAPI(uvicorn) 기본 포트, 8501 --> Streamlit 기본 포트

# ── 4단계: 기본 실행 명령 ────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD: 이 이미지로 컨테이너를 띄웠을 때 "기본으로" 실행되는 명령어.
# docker-compose.yml의 web 서비스처럼 command:를 따로 지정하면 이 CMD는 덮어써진다
# (그래서 api는 이 CMD 그대로 쓰고, web은 streamlit 명령어로 대체해서 쓴다).
# --host 0.0.0.0 : 컨테이너 "내부에서만" 접속 가능한 게 아니라
#                  외부(호스트 PC, 나중엔 인터넷)에서도 접속 가능하게 열어준다는 뜻.
#                  127.0.0.1로 하면 컨테이너 내부에서만 접속 가능해서 절대 밖에서 못 들어옴.
```

---
## docker-compose.yml 추가 — 로컬에서 api+web+db 동시 실행용	⬜ CI/CD 자동화 자체엔 필수 아님, 있으면 로컬 개발 편함

## 2. `docker-compose.yml` — 상세 주석 (로컬 개발용, `build: .` 버전)

```yaml
# 우리집 책장 v4 : FastAPI(api) + Streamlit(web) + PostgreSQL(db) 세 컨테이너를
# 함께 실행하기 위한 설정 파일

services:
  # services: 아래에 "어떤 컨테이너들을 띄울지" 하나씩 정의한다.
  # 각 서비스 이름(api, web, db)은 우리가 직접 지은 식별자이자,
  # Docker Compose가 만들어주는 내부 네트워크 안에서 서로를 부르는 "주소"가 된다.

  api:
    build: .
    # build: . --> 지금 이 폴더(현재 위치)의 Dockerfile을 기준으로 이미지를 직접 빌드한다.
    # (나중에 서버 배포할 땐 이 줄이 image: 계정명/home-library:latest 로 바뀐다 —
    #  로컬은 "직접 조립", 서버는 "완성품 받아쓰기".)
    container_name: booklib-api
    # container_name: 컨테이너에 사람이 알아보기 쉬운 고정 이름을 붙인다.
    # 안 붙이면 Docker가 임의의 이름을 자동 생성한다.

    ports:
      - "8000:8000"   # "호스트포트:컨테이너포트"
      # 내 컴퓨터(호스트)의 8000번 포트로 들어온 요청을
      # 컨테이너 내부의 8000번 포트로 그대로 연결(포트포워딩)한다.
      # 즉 브라우저에서 localhost:8000으로 접속하면 이 컨테이너에 닿는다.

    environment:
      DATABASE_URL: postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      # ${...} 는 .env 파일에 있는 값을 그대로 가져다 문자열에 끼워 넣는 문법.
      # 호스트 이름이 localhost가 아니라 "db"인 이유:
      #   Docker Compose가 만든 내부 네트워크 안에서는, 서비스 이름(db) 자체가
      #   그 컨테이너를 가리키는 주소 역할을 한다 (같은 컴퓨터 안이라도 localhost로는 안 통함).

    env_file:
      - .env
      # environment: 는 딱 하나의 값(DATABASE_URL)만 직접 조립해서 넘겨줬고,
      # env_file: 은 .env 파일에 있는 나머지 모든 변수(NLK_SEARCH_KEY 등)를
      # 통째로 컨테이너 환경변수로 주입해준다. main.py가 os.getenv()로 읽는 값들이 이렇게 들어온다.

    volumes:
      - ./uploads:/app/uploads
      # "내 컴퓨터 경로:컨테이너 경로"
      # 컨테이너가 삭제되어도 업로드된 책 표지 이미지 파일이
      # 내 컴퓨터의 uploads 폴더에 그대로 남는다 (컨테이너는 원래 사라지면 내부 파일도 다 사라짐).

    depends_on:
      db:
        # db 컨테이너가 단순히 "실행"만 된 상태가 아니라,
        # healthcheck(상태 체크)를 통과해 "정상적으로 접속 가능"해진 뒤에 api를 실행한다.
        # "생성 순서"만 맞추는 게 아니라 "준비 완료"까지 기다리는 게 핵심.
        condition: service_healthy

  web:
    build: .
    # api와 완전히 동일한 이미지를 재사용한다 (Dockerfile을 두 개 만들 필요 없음).
    container_name: booklib-web

    ports:
      - "8501:8501"  # Streamlit의 기본 포트 번호

    environment:
      # 컨테이너 안에서 api 컨테이너에 접속할 때는 localhost가 아니라
      # docker-compose.yml에 적은 서비스 이름 "api"를 주소로 사용해야 한다.
      API_URL: http://api:8000

    depends_on:
      # api가 먼저 뜬 뒤 web을 실행 (여기는 healthcheck까지는 요구 안 함, 순서만 보장)
      - api

    command: >
      streamlit run streamlit_app.py
      --server.address=0.0.0.0
      --server.port=8501
      # command: --> Dockerfile의 CMD를 이 서비스에서만 덮어쓴다.
      # (같은 이미지를 쓰지만, web 서비스는 uvicorn 대신 streamlit을 실행하도록 바꾸는 것)
      # --server.address=0.0.0.0 --> uvicorn의 --host 0.0.0.0과 같은 이유로
      #                               컨테이너 밖에서도 접근 가능하게 열어준다.

  db:
    image: postgres:17  # Dockerfile 없이 공식 PostgreSQL 이미지를 그대로 사용
    container_name: booklib-db

    environment:
      # postgres 공식 이미지가 컨테이너 최초 실행 시 자동으로 DB/계정을 생성할 때
      # 사용하는 변수들. 값 자체는 .env에서 그대로 가져온다.
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

    volumes:
      # PostgreSQL이 실제 데이터를 저장하는 내부 경로(/var/lib/postgresql/data)를
      # booklib_pgdata라는 이름의 볼륨에 연결 --> 컨테이너를 지워도 책 데이터가 보존된다.
      - booklib_pgdata:/var/lib/postgresql/data

    healthcheck:
      # pg_isready --> PostgreSQL이 접속을 받을 준비가 되었는지 확인하는 공식 명령어
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s   # 5초마다 확인
      timeout: 5s    # 응답을 5초까지 기다린다
      retries: 10    # 최대 10번까지 재시도

# named volume 선언부
# --> 위에서 db 서비스가 사용한 booklib_pgdata라는 이름의 볼륨을
#     Docker가 별도로 관리하게 된다 (컨테이너 생명주기와 분리되어 데이터가 보존됨).
volumes:
  booklib_pgdata:
```

---

## 로컬에서 직접 docker build 테스트	⬜ 가장 중요 — 여기서 문제 다 잡고 넘어가기


---

## 3. `.github/workflows/test.yml` — 완성본 (`test` + `build`) 상세 주석

```yaml
# 이 파일은 프로젝트 루트의 .github/workflows/test.yml 로 복사해서 사용합니다.
# 경로 주의: .github (점 하나) / workflows (복수형 s) / test.yml
name: 우리집 책장 CI/CD (테스트 + 빌드)
# name: 은 GitHub Actions 탭에서 이 워크플로우를 부르는 이름.

on:
  push:
    # push: 값을 안 적으면 "모든 브랜치에 push할 때마다" 실행된다.
  pull_request:
    # PR을 새로 만들거나, PR에 커밋을 추가로 올릴 때도 실행된다.

jobs:
  # ─────────────────────────────────────────────
  # 1단계: CI (테스트) — 지난 시간에 완성한 부분
  # ─────────────────────────────────────────────
  test:
    runs-on: ubuntu-latest
    # GitHub이 무료로 빌려주는 깨끗한 Ubuntu 가상 컴퓨터(Runner).
    # job이 끝나면 통째로 폐기된다.

    steps:
      - name: 1. 저장소 코드 가져오기
        uses: actions/checkout@v4
        # actions/checkout: 이 Runner(빈 컴퓨터) 안으로 우리 저장소의 코드를 git clone 해온다.
        # 이 스텝이 없으면 Runner는 우리 코드가 뭔지조차 모르는 완전히 빈 컴퓨터다.

      - name: 2. Python 설치하기
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          # 반드시 따옴표로 감싼 문자열로 써야 한다.
          # 안 그러면 YAML이 숫자로 해석해서 버전이 잘리는 경우가 생길 수 있다.
          cache: pip
          # requirements.txt 내용이 안 바뀌는 한 다음 실행부터는
          # 패키지를 매번 새로 다운로드하지 않고 캐시를 재사용해서 속도가 빨라진다.

      - name: 3. 패키지 설치하기
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: 4. 테스트 실행하기
        # pytest 대신 python -m pytest를 쓰는 이유:
        # tests/ 폴더에 __init__.py가 없으면 프로젝트 루트가 sys.path에 안 잡혀서
        # 'services' 모듈을 못 찾는 ModuleNotFoundError가 날 수 있다.
        run: python -m pytest -v

  # ─────────────────────────────────────────────
  # 2단계: Build — 오늘 새로 추가한 부분
  # (needs: test 덕분에 test가 실패하면 이 job은 아예 시작되지 않는다)
  # ─────────────────────────────────────────────
  build:
    # 'build'는 이 job의 이름. test job과 완전히 별개의 job이라,
    # 원래는 서로 다른 Runner에서 각자 독립적으로/병렬로 실행되는 게 기본값이다.
    # 하지만 바로 아래 needs: 로 이 병렬 실행을 순서 있게 바꾼다.

    needs: test
    # needs: 는 "이 job을 실행하기 전에, 먼저 끝나야 하는 다른 job"을 지정한다.
    # test가 성공(초록불)해야만 build가 시작되고,
    # test가 하나라도 실패(빨간 X)하면 build는 아예 실행되지 않고 건너뛴다.
    # → "테스트 안 된 코드는 이미지로도 못 만든다"는 안전장치의 핵심.

    runs-on: ubuntu-latest
    # test job과 마찬가지로 새로 생성되는 깨끗한 Ubuntu Runner.
    # test job에서 쓰던 Runner를 재사용하는 게 아니라 완전히 별개의 새 컴퓨터라는 점 주의
    # (그래서 아래에서 checkout을 또 한 번 해야 코드가 이 Runner 안에도 존재하게 된다).

    if: github.ref == 'refs/heads/main'
    # github.ref 는 "지금 이 workflow를 트리거한 브랜치가 뭔지" 담긴 값.
    # 'refs/heads/main' 은 브랜치 이름이 정확히 main일 때를 뜻하는 GitHub 내부 표기법.
    # → PR을 올리거나 다른 브랜치에 push할 때는 test만 돌고 build는 건너뛰고,
    #   실제로 main에 merge(또는 main에 직접 push)됐을 때만 이미지를 만든다.

    steps:
      - name: 코드 가져오기
        uses: actions/checkout@v4
        # build job은 test job과 완전히 다른 새 Runner에서 시작하기 때문에,
        # 여기서도 다시 한번 우리 코드를 복사해와야 한다.
        # (test job에서 이미 checkout 했다고 build job에서 자동으로 이어지지 않는다!)

      - name: Docker Hub 로그인
        uses: docker/login-action@v3
        # docker/login-action: 이 Runner가 Docker Hub에 로그인해서
        # 이미지를 push할 권한을 얻게 해준다.
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          # ${{ }} 는 GitHub Actions에서 "값을 여기 끼워넣어라"는 표현식 문법.
          # secrets.DOCKER_USERNAME 은 저장소 Settings에 등록해둔 비밀값을 그대로 가져온다.
          # 코드에 계정명을 직접 안 쓰는 이유: 저장소가 Public이라 노출되면 안 되기 때문.
          password: ${{ secrets.DOCKER_TOKEN }}
          # ⚠️ 이 값은 Docker Hub 계정 '비밀번호'가 아니라 Access Token이어야 한다.
          # (Docker Hub → Account Settings → Security → New Access Token,
          #  Access permissions는 반드시 Read & Write로 발급)
          # GitHub이 로그에 자동으로 *** 마스킹 처리해주지만,
          # 애초에 비밀번호 자체를 여기 넣지 않는 게 원칙 (토큰은 나중에 무효화 가능).

      - name: 이미지 빌드 및 Docker Hub 업로드
        uses: docker/build-push-action@v6
        # docker/build-push-action: 'docker build' + 'docker push' 두 명령어를
        # 한 번에 대신 실행해주는 Docker 공식 액션.
        with:
          context: .
          # context: . 는 "저장소 루트에 있는 Dockerfile을 기준으로 빌드해라"는 뜻.
          # 우리가 로컬에서 손으로 docker build . 이라고 치던 것과 완전히 동일한 의미.
          push: true
          # true로 설정하면 빌드만 하고 끝나는 게 아니라,
          # 바로 위에서 로그인한 계정으로 Docker Hub에 자동으로 업로드까지 진행한다.
          tags: ${{ secrets.DOCKER_USERNAME }}/home-library:latest
          # 이미지에 붙일 이름표(태그). '계정명/이미지이름:버전' 형식.
          # secrets를 재사용해서 계정명을 하드코딩하지 않은 것 — 다른 학생이
          # 자기 계정으로 그대로 복사해도 코드 수정 없이 바로 동작한다.
```

---

## 	Docker Hub Access Token 발급 (Read & Write 권한)	⬜

## 4. 오늘 새로 등록한 GitHub Secrets 요약

| Name | Value | 발급처 |
| --- | --- | --- |
| `DOCKER_USERNAME` | Docker Hub 계정명 | — |
| `DOCKER_TOKEN` | Access Token (비밀번호 아님, `Read & Write` 권한) | Docker Hub → Account Settings → Security → New Access Token |

---

## GitHub Secrets 등록: DOCKER_USERNAME, DOCKER_TOKEN	⬜

## 5. 로컬 테스트 vs GitHub Actions Build — 다시 한번 구분

| | 무엇을 하나 | 어떤 도구 | `.env` 필요? |
| --- | --- | --- | --- |
| 로컬 테스트 | api+web+db 세 컨테이너를 실제로 띄워서 눈으로 확인 | `docker compose up --build` | ✅ 필요 (컨테이너가 실행되니까) |
| GitHub Actions `build` job | 이미지를 빌드해서 Docker Hub에 올리기만 함 (실행 X) | `docker/build-push-action` | ❌ 불필요 |

---

## 	test.yml에 build job 추가	⬜

## 6. push 명령어

```bash
git add Dockerfile docker-compose.yml .github
git commit -m "본인이름_비NCS_test"
git push origin 비NCS_영문이름
```

## 	git add/commit/push	⬜

## 	Actions 탭에서 test → build 순서로 초록불 확인	⬜

## Docker Hub 웹사이트에서 이미지 업로드 확인

push 후 Actions 탭에서 `test` → `build` 순서로 초록불이 뜨는지, [Docker Hub](https://hub.docker.com)에 `home-library:latest` 이미지가 실제로 올라왔는지 확인하면 1차 세션이 끝납니다.

