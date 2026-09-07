import time
from collections import defaultdict, deque
from collections.abc import Callable

from .decision import SecurityDecision


CONTROL_ANTI_BOT = "ANTI_BOT"
ACTION_ALLOW = "ALLOW"
ACTION_BLOCK_MESSAGE = "BLOCK_MESSAGE"
REASON_ANTIBOT_OK = "ANTIBOT_OK"
REASON_ANTIBOT_RATE_LIMIT = "ANTIBOT_RATE_LIMIT"


class AntiBotRateLimiter:
    def __init__(
        self,
        max_messages: int = 5,
        window_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")

        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.clock = clock
        self._timestamps: dict[int, deque[float]] = defaultdict(deque)

    def check(self, user_id: int) -> SecurityDecision:
        now = self.clock()
        timestamps = self._timestamps[user_id]
        cutoff = now - self.window_seconds

        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= self.max_messages:
            return SecurityDecision(
                allowed=False,
                control=CONTROL_ANTI_BOT,
                action=ACTION_BLOCK_MESSAGE,
                reason_code=REASON_ANTIBOT_RATE_LIMIT,
            )

        timestamps.append(now)
        return SecurityDecision(
            allowed=True,
            control=CONTROL_ANTI_BOT,
            action=ACTION_ALLOW,
            reason_code=REASON_ANTIBOT_OK,
        )
