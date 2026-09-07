다다음 수업 — DB 연동 CI

전제: 오늘(test + build job)까지 초록불 확인된 상태.

목표: GitHub Actions 안에 "테스트 전용 임시 PostgreSQL"을 띄워서, models.py의 Book이 실제로 저장·조회되는지까지 자동 검증합니다.

## 1단계 — test.yml의 test job에 services: 추가

새 job을 만드는 게 아니라, 기존 test: job을 확장합니다.

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

      - name: 4. 테스트 실행하기
        env:
          DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/home_library_test
        run: python -m pytest -v

```

(build job은 그대로 아래 유지 — test: job만 이렇게 바뀝니다.)

## 2단계 — tests/test_db.py 새로 작성
```python
from database import Base, engine, SessionLocal
from models import Book


def test_책을_저장하고_다시_조회할_수_있다():
    Base.metadata.create_all(engine)  # CI DB는 매번 완전히 빈 상태

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

## 3단계 — 로컬에서 먼저 확인 (선택이지만 권장)

로컬 PostgreSQL이 이미 떠 있는 상태(docker compose up -d db)라면:

```bash
DATABASE_URL=postgresql+psycopg2://postgres:1234@localhost:5432/home_library_v1 uv run python -m pytest -v
```

## 4단계 — push 후 확인
```bash
git add .github tests
git commit -m "..."
git push
```

Actions 탭 → test job 로그에서 postgres 서비스 컨테이너가 먼저 뜨고 그다음 pytest가 도는 순서를 확인합니다.

### 자주 나는 문제
증상	처방
connection refused	ports/DATABASE_URL 포트 번호 일치 확인, --health-cmd pg_isready 옵션 확인
로컬은 되는데 CI만 "테이블 없음" 에러	Base.metadata.create_all(engine) 호출 누락 확인

---

# 그다음다음 수업 — AWS Lightsail 배포 (CD 최종 단계)

전제: DB 연동 CI까지 끝난 상태.

목표: main에 push하면 → 테스트 → 이미지 빌드/업로드 → Lightsail 서버가 자동으로 최신 버전 실행까지 완성.

## 1단계 — Lightsail 인스턴스 생성
AWS 콘솔 → Lightsail → Create instance
Linux/Unix → OS Only → Ubuntu 24.04 LTS
최저 사양 플랜 선택 후 생성
네트워킹 탭: 고정 IP(Static IP) 연결 + 커스텀 TCP 8000, 8501 포트 오픈
SSH 키 다운로드 (.pem)

⚠️ 과금 안내: 수업 끝나면 인스턴스는 정지가 아니라 삭제해야 과금이 멈춥니다.

## 2단계 — 서버에 Docker + Compose 설치 (SSH 접속해서 1회)
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
```

## 3단계 — 서버에 배포용 파일 두 개 준비 (~/home-library/)

.env:

DOCKER_USERNAME=계정명(예: seokssaem1)
POSTGRES_DB=home_library
POSTGRES_USER=postgres
POSTGRES_PASSWORD=실제_운영용_비밀번호
NLK_SEARCH_KEY=실제_국립중앙도서관_API_키

docker-compose.yml (로컬 것과 딱 하나 다름: build: . → image:):

yaml
services:
  api:
    image: ${DOCKER_USERNAME}/home-library:latest
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
    image: ${DOCKER_USERNAME}/home-library:latest
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

서버엔 소스 코드도, Dockerfile도 필요 없습니다 — 이 두 파일이 전부입니다.

## 4단계 — GitHub Secrets 3개 추가 등록
Name	Value
LIGHTSAIL_HOST	고정 IP
LIGHTSAIL_USERNAME	ubuntu
LIGHTSAIL_SSH_KEY	.pem 파일 내용 전체

(DOCKER_USERNAME, DOCKER_TOKEN은 이미 등록되어 있으니 그대로 둡니다.)

## 5단계 — test.yml에 deploy job 추가
```yaml
  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - name: SSH로 Lightsail 접속 후 컨테이너 교체
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.LIGHTSAIL_HOST }}
          username: ${{ secrets.LIGHTSAIL_USERNAME }}
          key: ${{ secrets.LIGHTSAIL_SSH_KEY }}
          script: |
            cd ~/home-library
            docker compose pull
            docker compose up -d
            docker image prune -f
```
            
## 6단계 — push 후 확인
```bash
git add .github
git commit -m "..."
git push
```
Actions 탭 → test → build → deploy 세 개 순서대로 초록불
브라우저로 http://<IP>:8000/docs, http://<IP>:8501 접속 확인
검증용 실습: 책 한 권 등록 → 아무 코드나 사소하게 고쳐서 다시 push(재배포 유도) → 아까 등록한 책이 그대로 남아있는지 확인 (db 컨테이너는 이미지가 안 바뀌면 재생성 안 되고, booklib_pgdata 볼륨에 데이터가 남아있기 때문)
자주 나는 문제
증상	처방
Permission denied (publickey)	.pem 내용 전체(BEGIN~END)를 다시 정확히 복사해서 Secret 재등록
docker: 'compose' is not a docker command	2단계에서 docker-compose-plugin 설치 누락
접속 자체가 안 됨	Lightsail 방화벽에 8000/8501 포트 오픈 확인
컨테이너는 떴는데 500 에러	서버 .env의 POSTGRES_*, DOCKER_USERNAME 값과 compose 파일 변수명 일치 확인

정리하면: 다음 수업(DB 연동 CI)은 오늘 만든 test.yml에 services: 블록만 끼워 넣는 작은 확장이고, 그다음 수업(AWS 배포)이 이번 v5 과정의 마지막 큰 단계입니다. 두 수업 다 "기존 파일은 거의 안 건드리고 새 파일/새 job만 추가"하는 예광탄 원칙이 계속 이어집니다.
