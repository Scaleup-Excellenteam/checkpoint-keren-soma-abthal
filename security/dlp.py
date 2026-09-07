import asyncio
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from .decision import SecurityDecision


CONTROL_DLP = "DLP"
ACTION_ALLOW = "ALLOW"
ACTION_BLOCK_MESSAGE = "BLOCK_MESSAGE"
REASON_DLP_OK = "DLP_OK"
REASON_DLP_PROTECTED_CONTENT = "DLP_PROTECTED_CONTENT"
REASON_DLP_SEMANTIC_MATCH = "DLP_SEMANTIC_MATCH"

# Demo policy only. Tune this threshold against labeled application data.
DEFAULT_SEMANTIC_THRESHOLD = 0.80

DEFAULT_PROTECTED_DATA_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "protected_recipe.json"
)

_SIMPLE_PUNCTUATION = re.compile(r"[,.;:!?()\[\]{}\-\u2013\u2014]")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class DLPResult:
    decision: SecurityDecision
    matched_fragment_id: str | None = None
    similarity_score: float | None = None


def normalize_dlp_text(text):
    if not isinstance(text, str):
        return ""

    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _SIMPLE_PUNCTUATION.sub(" ", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


class DLPChecker:
    def __init__(
        self,
        protected_data_path=DEFAULT_PROTECTED_DATA_PATH,
        embedding_backend=None,
        semantic_threshold=DEFAULT_SEMANTIC_THRESHOLD,
    ):
        if not 0 <= semantic_threshold <= 1:
            raise ValueError("semantic_threshold must be between 0 and 1")

        with Path(protected_data_path).open("r", encoding="utf-8") as file:
            protected_data = json.load(file)

        protected_fragments = protected_data["fragments"]
        self.fragments = tuple(
            (fragment["id"], normalize_dlp_text(fragment["text"]))
            for fragment in protected_fragments
        )
        self._fragment_texts = tuple(
            fragment["text"] for fragment in protected_fragments
        )
        self.embedding_backend = embedding_backend
        self.semantic_threshold = semantic_threshold
        self._protected_embeddings = None
        self._embedding_lock = Lock()

    def check_message(self, message):
        direct_result = self._check_direct(message)
        if direct_result is not None:
            return direct_result

        if self.embedding_backend is None:
            return _allow()

        return self._check_semantic(message)

    async def check_message_async(self, message):
        direct_result = self._check_direct(message)
        if direct_result is not None:
            return direct_result

        if self.embedding_backend is None:
            return _allow()

        return await asyncio.to_thread(self._check_semantic, message)

    def _check_direct(self, message):
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

        return None

    def _check_semantic(self, message):
        protected_embeddings = self._get_protected_embeddings()
        message_embedding = self.embedding_backend.encode([message])[0]
        similarities = [
            _cosine_similarity(message_embedding, protected_embedding)
            for protected_embedding in protected_embeddings
        ]
        best_index = max(range(len(similarities)), key=similarities.__getitem__)
        similarity = similarities[best_index]
        fragment_id = self.fragments[best_index][0]

        if similarity >= self.semantic_threshold:
            return DLPResult(
                SecurityDecision(
                    allowed=False,
                    control=CONTROL_DLP,
                    action=ACTION_BLOCK_MESSAGE,
                    reason_code=REASON_DLP_SEMANTIC_MATCH,
                ),
                matched_fragment_id=fragment_id,
                similarity_score=similarity,
            )

        return _allow(
            matched_fragment_id=fragment_id,
            similarity_score=similarity,
        )

    def _get_protected_embeddings(self):
        with self._embedding_lock:
            if self._protected_embeddings is None:
                self._protected_embeddings = tuple(
                    self.embedding_backend.encode(self._fragment_texts)
                )
        return self._protected_embeddings


def _allow(matched_fragment_id=None, similarity_score=None):
    return DLPResult(
        SecurityDecision(
            allowed=True,
            control=CONTROL_DLP,
            action=ACTION_ALLOW,
            reason_code=REASON_DLP_OK,
        ),
        matched_fragment_id=matched_fragment_id,
        similarity_score=similarity_score,
    )


def _cosine_similarity(first, second):
    if len(first) != len(second):
        raise ValueError("embedding dimensions must match")

    dot_product = sum(float(a) * float(b) for a, b in zip(first, second))
    first_magnitude = math.sqrt(sum(float(value) ** 2 for value in first))
    second_magnitude = math.sqrt(sum(float(value) ** 2 for value in second))
    if first_magnitude == 0 or second_magnitude == 0:
        return 0.0
    return dot_product / (first_magnitude * second_magnitude)
