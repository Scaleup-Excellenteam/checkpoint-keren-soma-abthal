import re

from errors import AppError
from models import User
from password_utils import hash_password, verify_password
from storage import StorageManager


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")


class AuthService:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.users = self.storage.load_users()

        self.next_user_id = (
            max((user.user_id for user in self.users), default=0) + 1
        )

    def signup(self, username: str, password: str) -> User:
        username = username.strip().lower()

        if not USERNAME_PATTERN.fullmatch(username):
            raise AppError(
                "INVALID_PAYLOAD",
                "Username must be 3-32 characters and contain only letters, numbers, or underscore",
            )

        if not 8 <= len(password) <= 128:
            raise AppError(
                "INVALID_PAYLOAD",
                "Password must be between 8 and 128 characters",
            )

        if any(user.username == username for user in self.users):
            raise AppError(
                "USERNAME_TAKEN",
                "Username is already taken",
            )

        user = User(
            user_id=self.next_user_id,
            username=username,
            password_hash=hash_password(password),
        )

        self.next_user_id += 1
        self.users.append(user)
        self.storage.save_users(self.users)

        return user

    def login(self, username: str, password: str) -> User:
        username = username.strip().lower()

        user = next(
            (user for user in self.users if user.username == username),
            None,
        )

        if user is None or not verify_password(password, user.password_hash):
            raise AppError(
                "AUTHENTICATION_FAILED",
                "Invalid username or password",
            )

        return user
