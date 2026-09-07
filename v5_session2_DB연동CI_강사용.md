# 🗄️ 우리집 책장 v5 — 2차 세션: DB 연동 CI (상세 주석 / 강사용)

**범위:** 1차 세션(CI+Build)이 이미 초록불로 확인된 상태에서, `test` job 안에 "테스트 전용 임시 PostgreSQL"을 띄워 `models.py`의 `Book`이 실제로 저장·조회되는지까지 자동 검증합니다.

---

## 1. `.github/workflows/test.yml` — `test` job 확장 (상세 주석)

**기존 `test:` job을 새로 만들지 않고, 그대로 확장합니다.** `build` job은 아래 그대로 유지되므로 이 문서에는 생략합니다.

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

| 항목 | 의미 |
| --- | --- |
| `services.postgres` | Job이 시작될 때 함께 뜨는 사이드카 컨테이너. `postgres:17`은 로컬과 동일 버전으로 맞춤 |
| `options: --health-cmd pg_isready ...` | DB 컨테이너가 완전히 준비되기 전에 테스트가 먼저 시작해서 접속 실패하는 걸 막아주는 헬스체크 |
| `env.DATABASE_URL` | `database.py`가 읽어가는 바로 그 환경변수. 로컬 `.env`와 값만 다르고 형식은 동일 |

---

## 2. `tests/test_db.py` — 새 파일 (상세 주석)

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

---

## 3. 로컬에서 먼저 확인 (선택이지만 권장)

로컬 PostgreSQL이 이미 떠 있는 상태(`docker compose up -d db`)라면, CI와 똑같은 방식으로 로컬에서도 미리 검증할 수 있다.

```bash
DATABASE_URL=postgresql+psycopg2://postgres:1234@localhost:5432/home_library_v1 uv run python -m pytest -v
```

> `postgres:1234`, `home_library_v1`은 로컬 `.env`에 이미 등록된 값을 그대로 씀. CI에서는 위 test.yml의 `postgres/postgres`, `home_library_test`로 완전히 분리된 값을 쓰므로 서로 절대 섞이지 않는다.

---

## 4. push 및 확인

```bash
git add .github tests
git commit -m "본인이름_비NCS_test"
git push origin 비NCS_영문이름
```

Actions 탭 → `test` job 로그를 열어보면, `postgres` 서비스 컨테이너가 먼저 뜨고 그다음 pytest가 실행되는 순서가 로그에 그대로 보인다.

## 5. 자주 발생하는 문제

| 증상 | 원인 | 처방 |
| --- | --- | --- |
| `connection refused` / DB 접속 실패 | `options`의 헬스체크 설정 누락, 또는 포트 번호 불일치 | `ports: - 5432:5432`와 `DATABASE_URL`의 포트가 정확히 일치하는지, `--health-cmd pg_isready` 옵션이 들어있는지 확인 |
| `psql: command not found` 계열 에러 | `psql` CLI를 직접 호출하는 코드가 섞여 있는 경우 | 우리는 SQLAlchemy(`psycopg2-binary`)로만 접속하므로 원래는 안 나야 함 |
| 로컬은 되는데 CI에서만 "테이블 없음" 에러 | `Base.metadata.create_all(engine)` 호출 누락 | CI DB는 매번 완전히 빈 상태이므로, 로컬처럼 "이미 테이블이 있겠지"라고 가정하면 안 됨 |
