import asyncio
import json
import logging
from urllib.error import HTTPError

import pytest

from room_service import RoomService
from security import AntiBotRateLimiter
from security.url_reputation import URLReputationChecker, extract_domains
from security.virustotal import VirusTotalClient, VirusTotalUnavailableError
from server import client_session
from server.client_session import AppStore, ClientSession
from storage import StorageManager


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeVirusTotalClient:
    def __init__(self, report=None, error=None):
        self.report = report
        self.error = error
        self.calls = []

    def get_domain_report(self, domain):
        self.calls.append(domain)
        if self.error is not None:
            raise self.error
        return self.report


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


@pytest.fixture(autouse=True)
def run_thread_work_inline(monkeypatch):
    async def fake_to_thread(function, *args):
        return function(*args)

    monkeypatch.setattr(
        "security.url_reputation.asyncio.to_thread",
        fake_to_thread,
    )


def report(malicious=0, suspicious=0, harmless=10, undetected=2):
    return {
        "malicious": malicious,
        "suspicious": suspicious,
        "harmless": harmless,
        "undetected": undetected,
    }


def check(checker, message):
    return asyncio.run(checker.check_message(message))


def test_extracts_and_normalizes_urls_and_bare_domains():
    domains = extract_domains(
        "Visit HTTPS://Example.COM/path?redirect=hidden.test, docs.example.org, "
        "or https://safe.example."
    )

    assert domains == ["example.com", "safe.example", "docs.example.org"]


def test_malformed_url_does_not_crash_extraction():
    assert extract_domains("broken http://[ address") == []


def test_message_without_domain_is_allowed_without_virustotal_call():
    client = FakeVirusTotalClient(report())
    result = check(URLReputationChecker(client), "hello general")

    assert result.decision.allowed
    assert result.decision.reason_code == "URL_REPUTATION_OK"
    assert result.domain is None
    assert client.calls == []


def test_safe_domain_is_allowed():
    client = FakeVirusTotalClient(report(malicious=0, suspicious=1))
    result = check(URLReputationChecker(client), "visit https://example.com/path")

    assert result.decision.allowed
    assert result.decision.control == "URL"
    assert result.decision.action == "ALLOW"
    assert result.decision.reason_code == "URL_REPUTATION_OK"
    assert result.domain == "example.com"


def test_domain_with_three_malicious_results_is_blocked():
    client = FakeVirusTotalClient(report(malicious=3))
    result = check(URLReputationChecker(client), "example.com")

    assert not result.decision.allowed
    assert result.decision.action == "BLOCK_MESSAGE"
    assert result.decision.reason_code == "URL_MALICIOUS"


def test_domain_with_malicious_and_suspicious_results_is_blocked():
    client = FakeVirusTotalClient(report(malicious=1, suspicious=2))
    result = check(URLReputationChecker(client), "https://example.com")

    assert not result.decision.allowed
    assert result.decision.reason_code == "URL_HIGH_RISK"


def test_unknown_domain_is_allowed():
    client = FakeVirusTotalClient(report=None)
    result = check(URLReputationChecker(client), "unknown.example")

    assert result.decision.allowed
    assert result.decision.reason_code == "URL_REPUTATION_UNKNOWN"


def test_virustotal_unavailable_is_allowed():
    client = FakeVirusTotalClient(error=TimeoutError())
    result = check(URLReputationChecker(client), "https://example.com")

    assert result.decision.allowed
    assert result.decision.reason_code == "URL_CHECK_UNAVAILABLE"


def test_cache_prevents_duplicate_domain_lookups():
    client = FakeVirusTotalClient(report())
    checker = URLReputationChecker(client, cache_ttl_seconds=600)

    check(checker, "https://Example.COM/first")
    check(checker, "example.com")

    assert client.calls == ["example.com"]


def test_expired_cache_entry_is_refreshed():
    clock = FakeClock()
    client = FakeVirusTotalClient(report())
    checker = URLReputationChecker(client, cache_ttl_seconds=10, clock=clock)
    check(checker, "example.com")

    clock.advance(10)
    check(checker, "example.com")

    assert client.calls == ["example.com", "example.com"]


def test_lookup_runs_through_asyncio_to_thread(monkeypatch):
    client = FakeVirusTotalClient(report())
    calls = []

    async def fake_to_thread(function, *args):
        calls.append((function, args))
        return function(*args)

    monkeypatch.setattr(
        "security.url_reputation.asyncio.to_thread",
        fake_to_thread,
    )

    check(URLReputationChecker(client), "example.com")

    assert calls == [(client.get_domain_report, ("example.com",))]


def test_virustotal_client_reads_existing_domain_report(monkeypatch):
    payload = {
        "data": {
            "attributes": {
                "last_analysis_stats": report(
                    malicious=1,
                    suspicious=2,
                    harmless=70,
                    undetected=5,
                )
            }
        }
    }
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["api_key"] = request.get_header("X-apikey")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("security.virustotal.urlopen", fake_urlopen)
    monkeypatch.setenv("VIRUSTOTAL_API_KEY", "test-key")

    stats = VirusTotalClient(timeout=3).get_domain_report("example.com")

    assert captured == {
        "url": "https://www.virustotal.com/api/v3/domains/example.com",
        "api_key": "test-key",
        "timeout": 3,
    }
    assert stats == report(1, 2, 70, 5)


def test_virustotal_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("VIRUSTOTAL_API_KEY", raising=False)

    with pytest.raises(VirusTotalUnavailableError):
        VirusTotalClient().get_domain_report("example.com")


def test_virustotal_client_treats_not_found_as_unknown(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr("security.virustotal.urlopen", fake_urlopen)

    assert (
        VirusTotalClient(api_key="test-key").get_domain_report("missing.example")
        is None
    )


def test_blocked_url_message_is_not_broadcast(tmp_path, monkeypatch, caplog):
    rooms = RoomService(
        StorageManager(
            str(tmp_path / "users.json"),
            str(tmp_path / "rooms.json"),
        )
    )
    room = rooms.create_room(1, "general")
    rooms.join_room(2, room.room_id)

    sender = ClientSession(FakeWebSocket())
    sender.user_id = 1
    sender.username = "soma"
    recipient = ClientSession(FakeWebSocket())
    recipient.user_id = 2
    recipient.username = "keren"
    online_users = AppStore()
    online_users.online_users = {1: sender, 2: recipient}
    fake_client = FakeVirusTotalClient(report(malicious=3))

    monkeypatch.setattr(client_session, "room_service", rooms)
    monkeypatch.setattr(client_session, "store", online_users)
    monkeypatch.setattr(
        client_session,
        "anti_bot",
        AntiBotRateLimiter(max_messages=5, clock=FakeClock()),
    )
    monkeypatch.setattr(
        client_session,
        "url_reputation",
        URLReputationChecker(fake_client),
    )
    caplog.set_level(logging.INFO, logger=client_session.logger.name)

    response = asyncio.run(
        client_session.handle_send_message(
            sender,
            "request-1",
            {
                "room_id": room.room_id,
                "message": "visit https://evil.example/private?token=secret",
            },
        )
    )

    assert response["status"] == "error"
    assert response["code"] == "URL_MALICIOUS"
    assert sender.websocket.sent == []
    assert recipient.websocket.sent == []
    assert fake_client.calls == ["evil.example"]
    url_log = next(
        message
        for message in caplog.messages
        if "control=URL" in message
    )
    assert "decision=BLOCK" in url_log
    assert "action=BLOCK_MESSAGE" in url_log
    assert "reason_code=URL_MALICIOUS" in url_log
    assert "domain=evil.example" in url_log
    assert "private" not in url_log
    assert "token" not in url_log
