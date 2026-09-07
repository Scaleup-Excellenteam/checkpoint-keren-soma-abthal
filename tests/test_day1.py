import pytest

from auth_service import AuthService
from room_service import RoomService
from storage import StorageManager
from errors import AppError


def make_storage(tmp_path):
    return StorageManager(
        str(tmp_path / "users.json"),
        str(tmp_path / "rooms.json"),
    )


def test_signup_creates_user(tmp_path):
    storage = make_storage(tmp_path)
    auth = AuthService(storage)

    user = auth.signup("soma", "password123")

    assert user.user_id == 1
    assert user.username == "soma"
    assert user.password_hash != "password123"


def test_duplicate_username_rejected(tmp_path):
    storage = make_storage(tmp_path)
    auth = AuthService(storage)

    auth.signup("soma", "password123")

    with pytest.raises(AppError) as error:
        auth.signup("soma", "anotherpassword")

    assert error.value.code == "USERNAME_TAKEN"


def test_correct_login_succeeds(tmp_path):
    storage = make_storage(tmp_path)
    auth = AuthService(storage)

    created_user = auth.signup("soma", "password123")
    logged_in_user = auth.login("soma", "password123")

    assert logged_in_user.user_id == created_user.user_id


def test_incorrect_login_rejected(tmp_path):
    storage = make_storage(tmp_path)
    auth = AuthService(storage)

    auth.signup("soma", "password123")

    with pytest.raises(AppError) as error:
        auth.login("soma", "wrongpassword")

    assert error.value.code == "AUTHENTICATION_FAILED"


def test_create_room_adds_creator(tmp_path):
    storage = make_storage(tmp_path)
    rooms = RoomService(storage)

    room = rooms.create_room(1, "general")

    assert room.admin_user_id == 1
    assert 1 in room.members


def test_join_room_adds_member(tmp_path):
    storage = make_storage(tmp_path)
    rooms = RoomService(storage)

    room = rooms.create_room(1, "general")
    rooms.join_room(2, room.room_id)

    assert 2 in room.members


def test_non_member_cannot_send(tmp_path):
    storage = make_storage(tmp_path)
    rooms = RoomService(storage)

    room = rooms.create_room(1, "general")

    with pytest.raises(AppError) as error:
        rooms.authorize_message(2, room.room_id)

    assert error.value.code == "NOT_ROOM_MEMBER"


def test_member_can_authorize_message(tmp_path):
    storage = make_storage(tmp_path)
    rooms = RoomService(storage)

    room = rooms.create_room(1, "general")
    rooms.join_room(2, room.room_id)

    authorized_room = rooms.authorize_message(2, room.room_id)

    assert authorized_room.room_id == room.room_id


def test_invalid_room_rejected(tmp_path):
    storage = make_storage(tmp_path)
    rooms = RoomService(storage)

    with pytest.raises(AppError) as error:
        rooms.get_room(999)

    assert error.value.code == "ROOM_NOT_FOUND"


def test_leave_room_removes_member(tmp_path):
    storage = make_storage(tmp_path)
    rooms = RoomService(storage)

    room = rooms.create_room(1, "general")
    rooms.join_room(2, room.room_id)

    rooms.leave_room(2, room.room_id)

    assert 2 not in room.members