from dataclasses import dataclass, field


@dataclass
class User:
    user_id: int
    username: str
    password_hash: str


@dataclass
class Room:
    room_id: int
    name: str
    admin_user_id: int
    members: set[int] = field(default_factory=set)