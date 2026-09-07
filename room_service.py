import logging

from errors import AppError
from models import Room
from storage import StorageManager


logger = logging.getLogger(__name__)


class RoomService:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.rooms = self.storage.load_rooms()

        self.next_room_id = (
            max((room.room_id for room in self.rooms), default=0) + 1
        )

    def create_room(self, user_id: int, name: str) -> Room:
        name = name.strip()

        if not 1 <= len(name) <= 40:
            raise AppError(
                "INVALID_PAYLOAD",
                "Room name must be between 1 and 40 characters",
            )

        if any(room.name.lower() == name.lower() for room in self.rooms):
            raise AppError(
                "ROOM_NAME_TAKEN",
                "Room name is already taken",
            )

        room = Room(
            room_id=self.next_room_id,
            name=name,
            admin_user_id=user_id,
            members={user_id},
        )

        self.next_room_id += 1
        self.rooms.append(room)
        self.storage.save_rooms(self.rooms)

        logger.info(
            "ROOM_CREATED room_id=%s name=%s admin_user_id=%s",
            room.room_id,
            room.name,
            room.admin_user_id,
        )

        return room

    def list_rooms(self, user_id: int) -> list[dict]:
        return [
            {
                "room_id": room.room_id,
                "name": room.name,
                "member": user_id in room.members,
            }
            for room in self.rooms
        ]

    def get_room(self, room_id: int) -> Room:
        room = next(
            (room for room in self.rooms if room.room_id == room_id),
            None,
        )

        if room is None:
            raise AppError(
                "ROOM_NOT_FOUND",
                "Room does not exist",
            )

        return room

    def join_room(self, user_id: int, room_id: int) -> Room:
        room = self.get_room(room_id)

        if user_id in room.members:
            raise AppError(
                "ALREADY_ROOM_MEMBER",
                "User is already a member of this room",
            )

        room.members.add(user_id)
        self.storage.save_rooms(self.rooms)

        logger.info(
            "ROOM_JOINED room_id=%s user_id=%s",
            room.room_id,
            user_id,
        )

        return room

    def leave_room(self, user_id: int, room_id: int) -> Room:
        room = self.get_room(room_id)

        if user_id not in room.members:
            raise AppError(
                "NOT_ROOM_MEMBER",
                "User is not a member of this room",
            )

        if user_id == room.admin_user_id:
            raise AppError(
                "ADMIN_CANNOT_LEAVE_ROOM",
                "Room admin cannot leave the room",
            )

        room.members.remove(user_id)
        self.storage.save_rooms(self.rooms)

        logger.info(
            "ROOM_LEFT room_id=%s user_id=%s",
            room.room_id,
            user_id,
        )

        return room

    def authorize_message(self, user_id: int, room_id: int) -> Room:
        room = self.get_room(room_id)

        if user_id not in room.members:
            logger.info(
                "ACCESS_DENIED user_id=%s room_id=%s reason=NOT_ROOM_MEMBER",
                user_id,
                room_id,
            )

            raise AppError(
                "NOT_ROOM_MEMBER",
                "User is not a member of this room",
            )

        return room