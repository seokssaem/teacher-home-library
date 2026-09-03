'''
home_library_v5 / tests/test_main.py
-----------------------------------------------
GitHub Actions 실습용 최소 테스트 (v5)

- DB, 외부 API(국립중앙도서관) 없이도 통과하는 "순수 로직"만 검증한다.
- 검증 대상: services/recognition.py 의 normalize_isbn() 함수
  (OCR로 뽑은 문자열이 진짜 유효한 ISBN인지 체크섬으로 확인하는 함수, v4 수업에서 이미 배움)
- 이 파일이 GitHub Actions(CI)에서 push할 때마다 자동으로 실행된다.
'''
from services.recognition import normalize_isbn


def test_하이픈이_있는_isbn13을_숫자로_정리한다():
    # 978-89-6626-318-9 는 체크섬이 맞는 정상 ISBN-13이다.
    # 하이픈(-)을 제거하고 순수 숫자 13자리 문자열로 반환되는지 확인한다.
    assert normalize_isbn('978-89-6626-318-9') == '9788966263189'


def test_체크섬이_틀린_isbn은_none을_반환한다():
    # 마지막 자리만 9 -> 0으로 바꿔서 체크섬이 깨지도록 만든 값이다.
    # normalize_isbn은 "숫자처럼 보이지만 가짜인 ISBN"을 여기서 걸러내야 한다.
    assert normalize_isbn('978-89-6626-318-0') is None
