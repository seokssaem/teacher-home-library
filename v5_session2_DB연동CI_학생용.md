# 🗄️ 우리집 책장 v5 — 2차 세션: DB 연동 CI

**범위:** 1차 세션(CI+Build)이 이미 초록불로 확인된 상태에서, `test` job 안에 "테스트 전용 임시 PostgreSQL"을 띄워 `models.py`의 `Book`이 실제로 저장·조회되는지까지 자동 검증합니다.

---

## 1. `.github/workflows/test.yml` — `test` job 확장

기존 `test:` job을 확장합니다. `build` job은 그대로 유지되므로 이 문서에는 생략합니다.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_DB: home_library_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

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
          DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/home_library_test
        run: python -m pytest -v
```

---

## 2. `tests/test_db.py` — 새 파일

```python
from database import Base, engine, SessionLocal
from models import Book


def test_책을_저장하고_다시_조회할_수_있다():
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        book = Book(title='CI 테스트용 책', isbn='9999999999999', author='테스트 저자')
        db.add(book)
        db.commit()
        db.refresh(book)

        saved = db.get(Book, book.id)
        assert saved is not None
        assert saved.title == 'CI 테스트용 책'
        assert saved.recognition_status == 'confirmed'
    finally:
        db.query(Book).delete()
        db.commit()
        db.close()
```

---

## 3. 로컬에서 먼저 확인 (선택이지만 권장)

```bash
DATABASE_URL=postgresql+psycopg2://postgres:1234@localhost:5432/home_library_v1 uv run python -m pytest -v
```

---

## 4. push 및 확인

```bash
git add .github tests
git commit -m "본인이름_비NCS_test"
git push origin 비NCS_영문이름
```

## 5. 자주 발생하는 문제

| 증상 | 원인 | 처방 |
| --- | --- | --- |
| `connection refused` / DB 접속 실패 | `options`의 헬스체크 설정 누락, 또는 포트 번호 불일치 | `ports: - 5432:5432`와 `DATABASE_URL`의 포트가 정확히 일치하는지, `--health-cmd pg_isready` 옵션이 들어있는지 확인 |
| `psql: command not found` 계열 에러 | `psql` CLI를 직접 호출하는 코드가 섞여 있는 경우 | 우리는 SQLAlchemy(`psycopg2-binary`)로만 접속하므로 원래는 안 나야 함 |
| 로컬은 되는데 CI에서만 "테이블 없음" 에러 | `Base.metadata.create_all(engine)` 호출 누락 | CI DB는 매번 완전히 빈 상태이므로, 로컬처럼 "이미 테이블이 있겠지"라고 가정하면 안 됨 |
