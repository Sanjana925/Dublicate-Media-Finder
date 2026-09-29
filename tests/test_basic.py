from app.services.media_service import human
def test_human():
    assert human(1024) == "1.0 KB"
