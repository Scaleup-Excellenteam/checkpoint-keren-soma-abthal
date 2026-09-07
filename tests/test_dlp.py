import asyncio
import logging

from room_service import RoomService
from security import (
    AntiBotRateLimiter,
    DLPChecker,
    SecurityDecision,
    normalize_dlp_text,
)
from server import client_session
from server.client_session import AppStore, ClientSession
from storage import StorageManager


PROTECTED_FRAGMENT = (
    "Knead the dough for 10 minutes, then let it rise for 90 minutes"
)


class FakeClock:
    def __call__(self):
        return 0.0


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def test_normalization_handles_case_whitespace_and_simple_punctuation():
    assert (
        normalize_dlp_text("  Knead THE dough,\nthen-rest!  ")
        == "knead the dough then rest"
    )


def test_unrelated_message_is_allowed():
    result = DLPChecker().check_message("Would anyone like to order pizza?")

    assert result.decision == SecurityDecision(
        allowed=True,
        control="DLP",
        action="ALLOW",
        reason_code="DLP_OK",
    )
    assert result.matched_fragment_id is None


def test_exact_protected_fragment_is_blocked():
    result = DLPChecker().check_message(PROTECTED_FRAGMENT)

    assert result.decision == SecurityDecision(
        allowed=False,
        control="DLP",
        action="BLOCK_MESSAGE",
        reason_code="DLP_PROTECTED_CONTENT",
    )
    assert result.matched_fragment_id == "knead_and_rise"


def test_case_variation_is_blocked():
    result = DLPChecker().check_message(PROTECTED_FRAGMENT.upper())

    assert not result.decision.allowed
    assert result.decision.reason_code == "DLP_PROTECTED_CONTENT"


def test_extra_whitespace_is_blocked():
    message = "Knead   the dough\nfor 10 minutes,\tthen let it rise for 90 minutes"

    result = DLPChecker().check_message(message)

    assert not result.decision.allowed


def test_simple_punctuation_variation_is_blocked():
    message = "Knead the dough for 10 minutes then let it rise for 90 minutes!"

    result = DLPChecker().check_message(message)

    assert not result.decision.allowed


def test_blocked_dlp_message_is_not_broadcast(tmp_path, monkeypatch, caplog):
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

    monkeypatch.setattr(client_session, "room_service", rooms)
    monkeypatch.setattr(client_session, "store", online_users)
    monkeypatch.setattr(
        client_session,
        "anti_bot",
        AntiBotRateLimiter(max_messages=5, clock=FakeClock()),
    )
    monkeypatch.setattr(client_session, "dlp", DLPChecker())
    caplog.set_level(logging.INFO, logger=client_session.logger.name)

    response = asyncio.run(
        client_session.handle_send_message(
            sender,
            "request-1",
            {"room_id": room.room_id, "message": PROTECTED_FRAGMENT},
        )
    )

    assert response["status"] == "error"
    assert response["code"] == "DLP_PROTECTED_CONTENT"
    assert sender.websocket.sent == []
    assert recipient.websocket.sent == []
    dlp_log = next(
        message
        for message in caplog.messages
        if "event=SECURITY_DECISION" in message and "control=DLP" in message
    )
    assert "decision=BLOCK" in dlp_log
    assert "action=BLOCK_MESSAGE" in dlp_log
    assert "reason_code=DLP_PROTECTED_CONTENT" in dlp_log
    assert "matched_fragment_id=knead_and_rise" in dlp_log
    assert PROTECTED_FRAGMENT not in caplog.text
