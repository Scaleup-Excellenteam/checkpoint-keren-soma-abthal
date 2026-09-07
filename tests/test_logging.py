import asyncio
import logging

from room_service import RoomService
from security import DLPChecker
from server import client_session
from server.client_session import AppStore, ClientSession
from server.logging_config import connection_fields, log_event


class FakeWebSocket:
    remote_address = ("127.0.0.1", 54321)

    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def make_session(username="soma", user_id=1):
    session = ClientSession(FakeWebSocket())
    session.username = username
    session.user_id = user_id
    return session


def test_log_event_uses_key_value_fields_without_log_injection(caplog):
    logger = logging.getLogger("test.structured_logging")
    caplog.set_level(logging.INFO, logger=logger.name)

    log_event(
        logger,
        logging.INFO,
        "ROOM_CREATED",
        username="soma\nforged-entry",
        room_name="general chat",
        room_id=3,
    )

    assert caplog.messages == [
        'event=ROOM_CREATED username="soma\\nforged-entry" '
        'room_name="general chat" room_id=3'
    ]


def test_connection_fields_include_remote_endpoint():
    assert connection_fields(FakeWebSocket()) == {
        "remote_host": "127.0.0.1",
        "remote_port": 54321,
    }


def test_message_accepted_logs_metadata_not_content(tmp_path, monkeypatch, caplog):
    rooms = RoomService(
        client_session.StorageManager(
            str(tmp_path / "users.json"),
            str(tmp_path / "rooms.json"),
        )
    )
    room = rooms.create_room(1, "general")
    session = make_session()
    online_users = AppStore()
    online_users.online_users[session.user_id] = session
    monkeypatch.setattr(client_session, "room_service", rooms)
    monkeypatch.setattr(client_session, "store", online_users)
    monkeypatch.setattr(client_session, "dlp", DLPChecker())
    caplog.set_level(logging.INFO, logger=client_session.logger.name)

    response = asyncio.run(
        client_session.handle_send_message(
            session,
            "request-1",
            {"room_id": room.room_id, "message": "demo secret text"},
        )
    )

    assert response["code"] == "MESSAGE_ACCEPTED"
    message_log = next(
        message for message in caplog.messages if "event=MESSAGE_ACCEPTED" in message
    )
    assert "username=soma" in message_log
    assert "user_id=1" in message_log
    assert "room_name=general" in message_log
    assert "room_id=1" in message_log
    assert "length=16" in message_log
    assert "demo secret text" not in message_log


def test_message_rejected_logs_reason_and_length(tmp_path, monkeypatch, caplog):
    rooms = RoomService(
        client_session.StorageManager(
            str(tmp_path / "users.json"),
            str(tmp_path / "rooms.json"),
        )
    )
    room = rooms.create_room(2, "general")
    session = make_session()
    monkeypatch.setattr(client_session, "room_service", rooms)
    caplog.set_level(logging.WARNING, logger=client_session.logger.name)

    response = asyncio.run(
        client_session.handle_send_message(
            session,
            "request-2",
            {"room_id": room.room_id, "message": "private words"},
        )
    )

    assert response["code"] == "NOT_ROOM_MEMBER"
    assert caplog.messages == [
        "event=MESSAGE_REJECTED username=soma user_id=1 length=13 "
        "reason_code=NOT_ROOM_MEMBER room_id=1 room_name=general"
    ]
    assert "private words" not in caplog.text
