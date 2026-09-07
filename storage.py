import json
from pathlib import Path

from models import User, Room


class StorageManager:
    def __init__(
        self,
        users_path: str = "data/users.json",
        rooms_path: str = "data/rooms.json",
    ):
        self.users_path = Path(users_path)
        self.rooms_path = Path(rooms_path)

        self.users_path.parent.mkdir(parents=True, exist_ok=True)
        self.rooms_path.parent.mkdir(parents=True, exist_ok=True)

    def load_users(self) -> list[User]:
        if not self.users_path.exists():
            self.save_users([])
            return []

        with self.users_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return [
            User(
                user_id=item["user_id"],
                username=item["username"],
                password_hash=item["password_hash"],
            )
            for item in data.get("users", [])
        ]

    def save_users(self, users: list[User]) -> None:
        data = {
            "users": [
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "password_hash": user.password_hash,
                }
                for user in users
            ]
        }

        with self.users_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    def load_rooms(self) -> list[Room]:
        if not self.rooms_path.exists():
            self.save_rooms([])
            return []

        with self.rooms_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return [
            Room(
                room_id=item["room_id"],
                name=item["name"],
                admin_user_id=item["admin_user_id"],
                members=set(item["members"]),
            )
            for item in data.get("rooms", [])
        ]

    def save_rooms(self, rooms: list[Room]) -> None:
        data = {
            "rooms": [
                {
                    "room_id": room.room_id,
                    "name": room.name,
                    "admin_user_id": room.admin_user_id,
                    "members": list(room.members),
                }
                for room in rooms
            ]
        }

        with self.rooms_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)