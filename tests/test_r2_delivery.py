from datetime import datetime, timezone

from bot.services.r2_delivery import load_config, presign


def test_presign_matches_aws_documented_example():
    # Worked example from the AWS SigV4 query-string documentation.
    url = presign("GET", "examplebucket.s3.amazonaws.com", "/test.txt", "us-east-1",
                  "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                  expires=86400, now=datetime(2013, 5, 24, tzinfo=timezone.utc))
    assert url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")


def test_config_is_none_unless_fully_set(monkeypatch):
    for key in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(key, raising=False)
    assert load_config() is None
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    assert load_config() is None
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET", "videos")
    assert load_config().host == "acct.r2.cloudflarestorage.com"
