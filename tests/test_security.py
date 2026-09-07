import asyncio
import logging

from room_service import RoomService
from security import AntiBotRateLimiter, DLPChecker, SecurityDecision
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


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def test_first_message_is_allowed():
    limiter = AntiBotRateLimiter(clock=FakeClock())

    decision = limiter.check(user_id=1)

    assert decision == SecurityDecision(
        allowed=True,
        control="ANTI_BOT",
        action="ALLOW",
        reason_code="ANTIBOT_OK",
    )


def test_messages_up_to_threshold_are_allowed():
    limiter = AntiBotRateLimiter(max_messages=3, clock=FakeClock())

    decisions = [limiter.check(user_id=1) for _ in range(3)]

    assert all(decision.allowed for decision in decisions)


def test_message_exceeding_threshold_is_blocked():
    limiter = AntiBotRateLimiter(max_messages=2, clock=FakeClock())

    limiter.check(user_id=1)
    limiter.check(user_id=1)
    decision = limiter.check(user_id=1)

    assert decision == SecurityDecision(
        allowed=False,
        control="ANTI_BOT",
        action="BLOCK_MESSAGE",
        reason_code="ANTIBOT_RATE_LIMIT",
    )


def test_old_timestamps_expire_from_sliding_window():
    clock = FakeClock()
    limiter = AntiBotRateLimiter(
        max_messages=2,
        window_seconds=5,
        clock=clock,
    )
    limiter.check(user_id=1)
    clock.advance(3)
    limiter.check(user_id=1)
    clock.advance(1)
    assert not limiter.check(user_id=1).allowed

    clock.advance(1)

    assert limiter.check(user_id=1).allowed


def test_rate_limits_are_independent_between_users():
    limiter = AntiBotRateLimiter(max_messages=1, clock=FakeClock())

    assert limiter.check(user_id=1).allowed
    assert not limiter.check(user_id=1).allowed
    assert limiter.check(user_id=2).allowed


def test_blocked_message_is_not_broadcast(tmp_path, monkeypatch, caplog):
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
        AntiBotRateLimiter(max_messages=1, clock=FakeClock()),
    )
    monkeypatch.setattr(client_session, "dlp", DLPChecker())
    caplog.set_level(logging.INFO, logger=client_session.logger.name)

    allowed_response = asyncio.run(
        client_session.handle_send_message(
            sender,
            "request-1",
            {"room_id": room.room_id, "message": "first message"},
        )
    )
    sent_counts = (len(sender.websocket.sent), len(recipient.websocket.sent))
    caplog.clear()

    blocked_response = asyncio.run(
        client_session.handle_send_message(
            sender,
            "request-2",
            {"room_id": room.room_id, "message": "blocked message"},
        )
    )

    assert allowed_response["code"] == "MESSAGE_ACCEPTED"
    assert blocked_response["status"] == "error"
    assert blocked_response["code"] == "ANTIBOT_RATE_LIMIT"
    assert (len(sender.websocket.sent), len(recipient.websocket.sent)) == sent_counts
    assert caplog.messages == [
        "event=SECURITY_DECISION username=soma user_id=1 room_name=general "
        "room_id=1 control=ANTI_BOT decision=BLOCK action=BLOCK_MESSAGE "
        "reason_code=ANTIBOT_RATE_LIMIT length=15"
    ]
    assert "blocked message" not in caplog.text
