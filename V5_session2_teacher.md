다다음 수업 — DB 연동 CI

전제: 오늘(test + build job)까지 초록불 확인된 상태.

목표: GitHub Actions 안에 "테스트 전용 임시 PostgreSQL"을 띄워서, models.py의 Book이 실제로 저장·조회되는지까지 자동 검증합니다.

## 1단계 — test.yml의 test job에 services: 추가

## 1. .github/workflows/test.yml — test job 확장 (상세 주석)

기존 test: job을 새로 만들지 않고, 그대로 확장합니다. build job은 아래 그대로 유지되므로 이 문서에는 생략합니다.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      # services: 는 이 job이 실행되는 동안 "같이 떠 있는 보조 컨테이너"를 정의한다.
      # 우리 로컬 PostgreSQL과는 완전히 별개의, 이 워크플로우 실행 한 번만을 위한 임시 DB.
      # job이 끝나면 이 컨테이너도 통째로 폐기된다 (매번 완전히 빈 테이블에서 시작).
      postgres:
        image: postgres:17
        # 로컬 개발(docker-compose.yml)과 같은 버전을 써서 "버전 차이로 인한 문제"를 원천 차단.
        env:
          POSTGRES_DB: home_library_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          # 로컬/운영 계정 정보와 전혀 무관한 CI 전용 값. 이 값이 노출돼도 문제없다
          # (어차피 이 DB는 워크플로우가 끝나면 사라지고, 외부에서 접근도 불가능하다).
        ports:
          - 5432:5432
          # "Runner포트:컨테이너포트" — 아래 DATABASE_URL의 5432와 반드시 일치해야 한다.
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
          # PostgreSQL 컨테이너가 "떴다"고 표시돼도 실제로 접속 가능해지기까지는
          # 약간의 시간차가 있다. 이 헬스체크가 없으면 테스트가 DB보다 먼저 시작해서
          # "connection refused" 에러가 날 수 있다.
          # pg_isready --> PostgreSQL 공식 준비 상태 확인 명령어.
          # 10초마다 확인, 5초까지 대기, 최대 5번 재시도.

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

      - name: 4. 테스트 실행하기 (DB 없는 테스트 + DB 연동 테스트 모두 포함)
        env:
          # database.py의 os.getenv('DATABASE_URL', ...)가 이 값을 그대로 읽어간다.
          # 드라이버 이름(+psycopg2)까지 로컬 개발 때와 완전히 동일한 형식으로 맞춘 것이 핵심 —
          # 코드는 로컬이든 CI든 "환경변수만 다르고 나머지는 똑같다"고 믿을 수 있어야 한다.
          DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/home_library_test
        run: python -m pytest -v
        # pytest가 tests/ 아래의 모든 test_*.py를 자동으로 찾아서 실행한다.
        # 즉 이번에 새로 만드는 tests/test_db.py도 이 한 줄로 함께 실행된다
        # (새 job을 안 만들고 기존 job만 확장한 이유가 바로 이것).
```

(build job은 그대로 아래 유지 — test: job만 이렇게 바뀝니다.)

항목	의미
services.postgres	Job이 시작될 때 함께 뜨는 사이드카 컨테이너. postgres:17은 로컬과 동일 버전으로 맞춤
options: --health-cmd pg_isready ...	DB 컨테이너가 완전히 준비되기 전에 테스트가 먼저 시작해서 접속 실패하는 걸 막아주는 헬스체크
env.DATABASE_URL	database.py가 읽어가는 바로 그 환경변수. 로컬 .env와 값만 다르고 형식은 동일


## 2단계 — tests/test_db.py 새로 작성

## 2. tests/test_db.py — 새 파일 (상세 주석)

```python
'''
home_library_v4 / tests/test_db.py
-----------------------------------------------
GitHub Actions DB 연동 테스트 (v5 2차 세션)

- test.yml의 services.postgres가 띄워준 임시 DB에 실제로 접속해서
  Book 모델이 저장/조회되는지 확인한다.
- DATABASE_URL은 test.yml에서 CI 전용 값으로 주입되므로,
  이 파일 안에는 접속 정보가 전혀 하드코딩되지 않는다.
- /books/lookup처럼 국립중앙도서관 API를 부르는 부분은 일부러 건드리지 않는다
  (API 키가 CI에는 없다). 대신 우리가 직접 통제할 수 있는 "DB 저장" 부분만 검증한다.
'''
from database import Base, engine, SessionLocal
from models import Book


def test_책을_저장하고_다시_조회할_수_있다():
    # 매 실행마다 완전히 빈 DB이므로, 먼저 테이블부터 만들어야 한다.
    # 로컬에서는 main.py가 이미 만들어둔 테이블을 그대로 쓰지만,
    # CI는 항상 "방금 태어난 빈 DB"라서 이 한 줄이 없으면 "테이블 없음" 에러가 난다.
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        # models.py의 Book: title(필수), isbn/author/publisher(선택), 등록.
        book = Book(title='CI 테스트용 책', isbn='9999999999999', author='테스트 저자')
        db.add(book)
        db.commit()
        db.refresh(book)  # DB가 자동으로 채운 id, created_at 등을 다시 읽어온다.

        saved = db.get(Book, book.id)
        assert saved is not None
        assert saved.title == 'CI 테스트용 책'
        # models.py에서 default='confirmed'로 정의된 값이 실제로 DB에도 반영됐는지 확인.
        # 이건 "파이썬 코드상의 기본값"이 아니라 "진짜 DB에 저장된 값"을 검증하는 것이라
        # 순수 함수 테스트(1장)와는 성격이 다르다.
        assert saved.recognition_status == 'confirmed'
    finally:
        # CI 컨테이너는 job이 끝나면 어차피 통째로 폐기되지만,
        # "테스트는 자기가 만든 데이터를 스스로 치운다"는 습관을 들이는 차원에서 정리한다.
        db.query(Book).delete()
        db.commit()
        db.close()
```

## 3단계 — 로컬에서 먼저 확인 (선택이지만 권장)

3. 로컬에서 먼저 확인 (선택이지만 권장)

로컬 PostgreSQL이 이미 떠 있는 상태(docker compose up -d db)라면, CI와 똑같은 방식으로 로컬에서도 미리 검증할 수 있다.

```bash
DATABASE_URL=postgresql+psycopg2://postgres:1234@localhost:5432/home_library_v1 uv run python -m pytest -v
```
DATABASE_URL=postgresql+psycopg2://postgres:1234@localhost:5432/home_library_v1 uv run python -m pytest -v

postgres:1234, home_library_v1은 로컬 .env에 이미 등록된 값을 그대로 씀. CI에서는 위 test.yml의 postgres/postgres, home_library_test로 완전히 분리된 값을 쓰므로 서로 절대 섞이지 않는다

## 4단계 — push 후 확인
```bash
git add .github tests
git commit -m "..."
git push
```

Actions 탭 → test job 로그에서 postgres 서비스 컨테이너가 먼저 뜨고 그다음 pytest가 도는 순서를 확인합니다.

### 자주 나는 문제
Actions 탭 → test job 로그를 열어보면, postgres 서비스 컨테이너가 먼저 뜨고 그다음 pytest가 실행되는 순서가 로그에 그대로 보인다.

5. 자주 발생하는 문제
증상	원인	처방
connection refused / DB 접속 실패	options의 헬스체크 설정 누락, 또는 포트 번호 불일치	ports: - 5432:5432와 DATABASE_URL의 포트가 정확히 일치하는지, --health-cmd pg_isready 옵션이 들어있는지 확인
psql: command not found 계열 에러	psql CLI를 직접 호출하는 코드가 섞여 있는 경우	우리는 SQLAlchemy(psycopg2-binary)로만 접속하므로 원래는 안 나야 함
로컬은 되는데 CI에서만 "테이블 없음" 에러	Base.metadata.create_all(engine) 호출 누락

---

# 그다음다음 수업 — AWS Lightsail 배포 (CD 최종 단계)
## ☁️ 우리집 책장 v5 — 3차 세션: AWS Lightsail 배포 (상세 주석 / 강사용)

범위: 2차 세션(DB 연동 CI)까지 끝난 상태에서, main에 push하면 → 테스트 통과 → Docker 이미지 빌드/업로드 → AWS Lightsail 서버가 자동으로 최신 이미지를 받아 실행까지, test.yml 하나로 전체 파이프라인을 완성합니다.

프로덕션 DB 방식: A안 확정 — 같은 Lightsail 인스턴스 안에 PostgreSQL도 컨테이너로 같이 실행합니다 (비용 없음, 기존 docker-compose.yml 구조 재사용).

전제: DB 연동 CI까지 끝난 상태.

목표: main에 push하면 → 테스트 → 이미지 빌드/업로드 → Lightsail 서버가 자동으로 최신 버전 실행까지 완성.

## 1단계 — Lightsail 인스턴스 생성
## 1. Lightsail 인스턴스 준비 (사전 작업, 코드 아님)
AWS 콘솔 → Lightsail → Create instance
플랫폼: Linux/Unix → 블루프린트: OS Only → Ubuntu 24.04 LTS
인스턴스 플랜: 가장 저렴한 플랜(월 $5 내외)
네트워킹 탭: 고정 IP(Static IP) 발급 + 연결, 방화벽에 커스텀 TCP 8000, 8501 포트 오픈
SSH 키페어 다운로드(.pem)

⚠️ 수업이 끝나면 인스턴스는 정지가 아니라 삭제해야 과금이 완전히 멈춘다.


⚠️ 과금 안내: 수업 끝나면 인스턴스는 정지가 아니라 삭제해야 과금이 멈춥니다.

## 2단계 — 서버에 Docker + Compose 설치 (SSH 접속해서 1회)
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
# docker-compose-plugin을 꼭 같이 설치 — 오늘은 docker run이 아니라
# docker compose(v2 문법, 공백 있음)로 배포하기 때문이다.
sudo usermod -aG docker $USER
# 이후 터미널을 한 번 다시 열어야 sudo 없이 docker 명령어가 동작한다.

```

## 3단계 — 서버에 배포용 파일 두 개 준비 (~/home-library/)

3. 서버용 .env (상세 주석)

로컬 .env와는 다른, 서버 전용 파일을 최초 1회 직접 만든다.

mkdir -p ~/home-library
nano ~/home-library/.env

.env:
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
이 .env는 GitHub에도, workflow 로그에도 전혀 노출되지 않고 서버 안에만 존재한다. docker compose가 컨테이너를 시작할 때 이 파일을 자동으로 읽어서 변수를 채운다 (로컬 개발 때와 완전히 같은 방식 — docker-compose.yml이 .env를 읽는 원리 자체는 동일하다).

---
## 4. 서버용 docker-compose.yml (상세 주석)

로컬 개발용(build: .)과 딱 한 부분만 다르다 — api, web이 build: .(직접 빌드) 대신 image:(Docker Hub에서 받아쓰기)를 쓴다.

docker-compose.yml (로컬 것과 딱 하나 다름: build: . → image:):

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
💾 서버에는 소스 코드가 필요 없다. git clone도 Dockerfile도 서버엔 없어도 된다. ~/home-library/에 docker-compose.yml과 .env 딱 두 파일만 있으면 충분하다. uploads/ 폴더는 docker compose up 실행 시 없으면 자동으로 생성된다.

---
## 4단계 — GitHub Secrets 3개 추가 등록
기존 DOCKER_USERNAME, DOCKER_TOKEN은 그대로 두고, 아래 3개를 추가한다.

Name	Value
LIGHTSAIL_HOST	Lightsail 인스턴스의 고정 IP
LIGHTSAIL_USERNAME	ubuntu (Lightsail Ubuntu 인스턴스 기본 계정명)
LIGHTSAIL_SSH_KEY	.pem 키 파일을 텍스트 에디터로 열어서 내용 전체(BEGIN~END 포함)를 복사해 붙여넣기

(DOCKER_USERNAME, DOCKER_TOKEN은 이미 등록되어 있으니 그대로 둡니다.)

## 5단계 — test.yml에 deploy job 추가

## test.yml에 deploy job 추가 (상세 주석)


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
💡 로컬 개발 때 쓰던 docker compose up --build(직접 빌드)와 달리, 서버에서는 --build 없이 pull만 쓴다 — 서버는 소스 코드를 빌드하는 게 아니라 GitHub Actions가 이미 만들어서 Docker Hub에 올려둔 이미지를 받아쓰기만 하기 때문이다.


            
## 6단계 — push 후 확인
```bash
git add .github
git commit -m "..."
git push
```
Actions 탭 → test → build → deploy 세 개가 순서대로 초록불이 되는지 확인
브라우저로 http://<LIGHTSAIL_HOST>:8000/docs, http://<LIGHTSAIL_HOST>:8501 접속 확인
데이터 보존 검증(권장 실습): 책 한 권 등록 → 아무 코드나 사소하게 고쳐서 다시 push(재배포 유도) → 아까 등록한 책이 그대로 남아있는지 확인 (booklib_pgdata named volume이 실제로 동작하는지 눈으로 확인하는 과정)

자주 발생하는 문제
증상	원인	처방
Permission denied (publickey)	LIGHTSAIL_SSH_KEY에 .pem 내용을 잘못 붙여넣음 (일부 누락, 앞뒤 공백)	키 파일 전체(BEGIN~END 포함)를 다시 정확히 복사해서 Secret 값 재등록
docker: 'compose' is not a docker command	docker-compose-plugin 미설치	2단계 명령어를 서버에서 다시 실행
deploy job은 실행됐는데 접속이 안 됨	Lightsail 방화벽에 8000/8501번 포트를 안 열어둠	네트워킹 탭에서 커스텀 TCP 8000, 8501 규칙 추가
컨테이너는 떴는데 500 에러	.env에 POSTGRES_* 값이 없거나 docker-compose.yml과 변수 이름이 안 맞음	3, 4번의 변수 이름(DOCKER_USERNAME, POSTGRES_DB 등)이 정확히 일치하는지 확인
docker: command not found (SSH script 안에서)	Lightsail에 Docker 최초 설치를 안 함	2단계를 서버에서 먼저 실행
db 컨테이너가 unhealthy로 계속 재시작	POSTGRES_PASSWORD에 특수문자가 있어 DATABASE_URL 문자열이 깨짐	영문/숫자 위주의 단순한 비밀번호로 우선 테스트
배포는 됐는데 이전 버전이 계속 보임	브라우저 캐시, 또는 docker compose pull이 최신 태그를 못 받아옴	시크릿 창으로 재확인, docker images로 실제 받아진 이미지 생성 시각 확인
~/home-library 폴더 자체가 없어서 cd 실패	서버용 docker-compose.yml/.env 준비를 안 함	SSH 접속해서 mkdir -p ~/home-library 후 두 파일 배치

### 오늘의 배포 성공 체크리스트
 Lightsail 인스턴스 생성 + 고정 IP 연결 + 8000·8501번 포트 오픈
 서버에 Docker + docker-compose-plugin 최초 설치 완료
 LIGHTSAIL_HOST, LIGHTSAIL_USERNAME, LIGHTSAIL_SSH_KEY Secrets 등록
 서버 ~/home-library/에 .env 준비 (DOCKER_USERNAME, POSTGRES_*, NLK_SEARCH_KEY)
 서버 ~/home-library/에 배포용 docker-compose.yml 준비 (build: 대신 image:)
 test.yml에 deploy job 추가 후 push
 Actions 탭에서 test → build → deploy 전부 초록불
 브라우저로 http://<IP>:8000/shelf, http://<IP>:8501 둘 다 접속 확인
 책 등록 후 재배포해서 데이터가 그대로 남아있는지 확인 (named volume 보존 검증)
