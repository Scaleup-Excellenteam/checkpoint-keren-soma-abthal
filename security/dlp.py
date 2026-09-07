import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .decision import SecurityDecision


CONTROL_DLP = "DLP"
ACTION_ALLOW = "ALLOW"
ACTION_BLOCK_MESSAGE = "BLOCK_MESSAGE"
REASON_DLP_OK = "DLP_OK"
REASON_DLP_PROTECTED_CONTENT = "DLP_PROTECTED_CONTENT"

DEFAULT_PROTECTED_DATA_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "protected_recipe.json"
)

_SIMPLE_PUNCTUATION = re.compile(r"[,.;:!?()\[\]{}\-\u2013\u2014]")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class DLPResult:
    decision: SecurityDecision
    matched_fragment_id: str | None = None


def normalize_dlp_text(text):
    if not isinstance(text, str):
        return ""

    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _SIMPLE_PUNCTUATION.sub(" ", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


class DLPChecker:
    def __init__(self, protected_data_path=DEFAULT_PROTECTED_DATA_PATH):
        with Path(protected_data_path).open("r", encoding="utf-8") as file:
            protected_data = json.load(file)

        self.fragments = tuple(
            (
                fragment["id"],
                normalize_dlp_text(fragment["text"]),
            )
            for fragment in protected_data["fragments"]
        )

    def check_message(self, message):
        normalized_message = normalize_dlp_text(message)
        for fragment_id, normalized_fragment in self.fragments:
            if normalized_fragment and normalized_fragment in normalized_message:
                return DLPResult(
                    SecurityDecision(
                        allowed=False,
                        control=CONTROL_DLP,
                        action=ACTION_BLOCK_MESSAGE,
                        reason_code=REASON_DLP_PROTECTED_CONTENT,
                    ),
                    matched_fragment_id=fragment_id,
                )

        return DLPResult(
            SecurityDecision(
                allowed=True,
                control=CONTROL_DLP,
                action=ACTION_ALLOW,
                reason_code=REASON_DLP_OK,
            )
        )
