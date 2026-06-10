from dailybrief.runtime.safety import contains_secret, redact, redact_url


def test_redact_common_secret_shapes():
    raw = "\n".join(
        [
            "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/secret",
            "Authorization: Bearer abc.def-123",
            "postgresql://user:pass@example.com/db?sslmode=require",
            "https://api.telegram.org/bot123456:ABCdefGHIjklMNOpqrSTUvwx/sendMessage",
            "api_key=supersecret",
            "OPENAI_API_KEY=sk-testsecret",
        ]
    )
    redacted = redact(raw)

    assert "hooks.slack.com/services/T000" not in redacted
    assert "abc.def-123" not in redacted
    assert "user:pass@" not in redacted
    assert "123456:ABC" not in redacted
    assert "supersecret" not in redacted
    assert "sk-testsecret" not in redacted
    assert contains_secret(raw)


def test_redact_url_hides_password():
    assert redact_url("postgresql://user:pass@example.com/db") == "postgresql://user:[REDACTED]@example.com/db"

