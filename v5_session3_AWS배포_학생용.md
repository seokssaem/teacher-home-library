# ☁️ 우리집 책장 v5 — 3차 세션: AWS Lightsail 배포

**범위:** 2차 세션(DB 연동 CI)까지 끝난 상태에서, `main`에 push하면 → 테스트 통과 → Docker 이미지 빌드/업로드 → **AWS Lightsail 서버가 자동으로 최신 이미지를 받아 실행**까지, `test.yml` 하나로 전체 파이프라인을 완성합니다.

**프로덕션 DB 방식: A안** — 같은 Lightsail 인스턴스 안에 PostgreSQL도 컨테이너로 같이 실행합니다.

---

## 1. Lightsail 인스턴스 준비

1. AWS 콘솔 → **Lightsail** → **Create instance**
2. 플랫폼: `Linux/Unix` → 블루프린트: **OS Only → Ubuntu 24.04 LTS**
3. 인스턴스 플랜: 가장 저렴한 플랜(월 $5 내외)
4. **네트워킹 탭**: 고정 IP(Static IP) 발급 + 연결, 방화벽에 커스텀 TCP **8000, 8501** 포트 오픈
5. SSH 키페어 다운로드(`.pem`)

---

## 2. 서버에 Docker + Compose 설치 (SSH 접속해서 1회만)

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
```

---

## 3. 서버용 `.env`

```bash
mkdir -p ~/home-library
nano ~/home-library/.env
```

```dotenv
DOCKER_USERNAME=계정명(예: seokssaem1)

POSTGRES_DB=home_library
POSTGRES_USER=postgres
POSTGRES_PASSWORD=실제_운영용_비밀번호로_변경

NLK_SEARCH_KEY=실제_국립중앙도서관_API_키
```

---

## 4. 서버용 `docker-compose.yml`

```yaml
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
```

---

## 5. GitHub Secrets 추가 등록

| Name | Value |
| --- | --- |
| `LIGHTSAIL_HOST` | Lightsail 인스턴스의 고정 IP |
| `LIGHTSAIL_USERNAME` | `ubuntu` |
| `LIGHTSAIL_SSH_KEY` | `.pem` 키 파일 내용 전체 |

---

## 6. `test.yml`에 `deploy` job 추가

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

---

## 7. push 및 확인

```bash
git add .github
git commit -m "본인이름_비NCS_test"
git push origin 비NCS_영문이름
```

1. Actions 탭 → `test` → `build` → `deploy` 순서대로 초록불 확인
2. 브라우저로 `http://<LIGHTSAIL_HOST>:8000/docs`, `http://<LIGHTSAIL_HOST>:8501` 접속 확인
3. 책 한 권 등록 → 재배포 → 데이터가 그대로 남아있는지 확인

---

## 8. 자주 발생하는 문제

| 증상 | 원인 | 처방 |
| --- | --- | --- |
| `Permission denied (publickey)` | `.pem` 내용을 잘못 붙여넣음 | 키 파일 전체(BEGIN~END 포함)를 다시 정확히 복사해서 Secret 재등록 |
| `docker: 'compose' is not a docker command` | `docker-compose-plugin` 미설치 | 2단계 명령어를 서버에서 다시 실행 |
| 접속이 안 됨 | Lightsail 방화벽 포트 미오픈 | 네트워킹 탭에서 커스텀 TCP 8000, 8501 규칙 추가 |
| 컨테이너는 떴는데 500 에러 | `.env`/`docker-compose.yml` 변수 이름 불일치 | 변수 이름 재확인 |
| `docker: command not found` | Docker 최초 설치 누락 | 2단계 재실행 |
| `db` 컨테이너가 계속 재시작 | 비밀번호에 특수문자 포함 | 영문/숫자 위주 비밀번호로 변경 |
| 이전 버전이 계속 보임 | 브라우저 캐시 또는 pull 실패 | 시크릿 창 재확인, `docker images`로 확인 |
| `cd` 실패 | 서버용 파일 준비 안 됨 | `mkdir -p ~/home-library` 후 파일 배치 |

---

## 9. 오늘의 배포 성공 체크리스트

- [ ]  Lightsail 인스턴스 생성 + 고정 IP 연결 + 8000·8501번 포트 오픈
- [ ]  서버에 Docker + `docker-compose-plugin` 최초 설치 완료
- [ ]  `LIGHTSAIL_HOST`, `LIGHTSAIL_USERNAME`, `LIGHTSAIL_SSH_KEY` Secrets 등록
- [ ]  서버 `~/home-library/`에 `.env` 준비
- [ ]  서버 `~/home-library/`에 배포용 `docker-compose.yml` 준비
- [ ]  `test.yml`에 `deploy` job 추가 후 push
- [ ]  Actions 탭에서 `test → build → deploy` 전부 초록불
- [ ]  브라우저로 `http://<IP>:8000/shelf`, `http://<IP>:8501` 둘 다 접속 확인
- [ ]  책 등록 후 재배포해서 데이터가 그대로 남아있는지 확인
