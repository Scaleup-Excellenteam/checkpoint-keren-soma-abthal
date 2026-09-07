from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    control: str
    action: str
    reason_code: str
