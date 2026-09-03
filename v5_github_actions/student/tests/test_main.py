from services.recognition import normalize_isbn


def test_하이픈이_있는_isbn13을_숫자로_정리한다():
    assert normalize_isbn('978-89-6626-318-9') == '9788966263189'


def test_체크섬이_틀린_isbn은_none을_반환한다():
    assert normalize_isbn('978-89-6626-318-0') is None
