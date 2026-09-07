import asyncio
import logging
import sys
from types import SimpleNamespace

import pytest

from room_service import RoomService
from security import (
    AntiBotRateLimiter,
    DLPChecker,
    SentenceTransformerEmbeddingBackend,
)
from server import client_session
from server.client_session import AppStore, ClientSession
from storage import StorageManager


PROTECTED_FRAGMENT = (
    "Knead the dough for 10 minutes, then let it rise for 90 minutes"
)
PARAPHRASE = (
    "Work the dough for ten minutes and leave it to rise for an hour and a half"
)
NEAR_EXACT = "Knead this dough for ten minutes before a ninety minute rise"
UNRELATED_COOKING = "I enjoy making vegetable soup and sharing it with friends"
GENERAL_PIZZA = "Pizza is my favorite dinner for a relaxed Friday evening"

PROTECTED_VECTORS = {
    "Mix 500 grams of bread flour with 325 milliliters of warm water": [1, 0, 0, 0, 0],
    "Add 7 grams of dry yeast and 10 grams of fine salt": [0, 1, 0, 0, 0],
    PROTECTED_FRAGMENT: [0, 0, 1, 0, 0],
    "Preheat the oven to 250 degrees Celsius": [0, 0, 0, 1, 0],
    "Bake the pizza for 10 to 12 minutes": [0, 0, 0, 0, 1],
}


class FakeEmbeddingBackend:
    def __init__(self, message_vectors=None):
        self.message_vectors = message_vectors or {}
        self.calls = []

    def encode(self, texts):
        texts = list(texts)
        self.calls.append(tuple(texts))
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text):
        if text in PROTECTED_VECTORS:
            return PROTECTED_VECTORS[text]
        return self.message_vectors[text]


class FakeClock:
    def __call__(self):
        return 0.0


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def semantic_checker(message_vectors, threshold=0.80):
    backend = FakeEmbeddingBackend(message_vectors)
    return DLPChecker(
        embedding_backend=backend,
        semantic_threshold=threshold,
    ), backend


def test_exact_fragment_still_blocks_without_embedding_work():
    checker, backend = semantic_checker({})

    result = checker.check_message(PROTECTED_FRAGMENT)

    assert not result.decision.allowed
    assert result.decision.reason_code == "DLP_PROTECTED_CONTENT"
    assert result.matched_fragment_id == "knead_and_rise"
    assert result.similarity_score is None
    assert backend.calls == []


def test_unrelated_message_remains_allowed():
    checker, _ = semantic_checker({UNRELATED_COOKING: [1, 1, 1, 1, 1]})

    result = checker.check_message(UNRELATED_COOKING)

    assert result.decision.allowed
    assert result.decision.reason_code == "DLP_OK"
    assert result.similarity_score == pytest.approx(1 / (5 ** 0.5))


def test_paraphrase_with_high_similarity_is_blocked():
    checker, _ = semantic_checker({PARAPHRASE: [0, 0, 0.98, 0.1, 0]})

    result = checker.check_message(PARAPHRASE)

    assert not result.decision.allowed
    assert result.decision.reason_code == "DLP_SEMANTIC_MATCH"
    assert result.similarity_score > 0.99


def test_general_pizza_text_does_not_automatically_block():
    checker, _ = semantic_checker({GENERAL_PIZZA: [1, 1, 1, 1, 1]})

    result = checker.check_message(GENERAL_PIZZA)

    assert result.decision.allowed
    assert result.similarity_score < checker.semantic_threshold


def test_best_matched_fragment_id_is_reported():
    checker, _ = semantic_checker({PARAPHRASE: [0, 0, 0.98, 0.1, 0]})

    result = checker.check_message(PARAPHRASE)

    assert result.matched_fragment_id == "knead_and_rise"


def test_semantic_threshold_is_configurable():
    vector = [0, 0, 0.8, 0.6, 0]
    strict_checker, _ = semantic_checker({NEAR_EXACT: vector}, threshold=0.85)
    demo_checker, _ = semantic_checker({NEAR_EXACT: vector}, threshold=0.75)

    strict_result = strict_checker.check_message(NEAR_EXACT)
    demo_result = demo_checker.check_message(NEAR_EXACT)

    assert strict_result.decision.allowed
    assert not demo_result.decision.allowed
    assert strict_result.similarity_score == pytest.approx(0.8)
    assert demo_result.similarity_score == pytest.approx(0.8)


def test_protected_fragment_embeddings_are_computed_once():
    checker, backend = semantic_checker(
        {
            UNRELATED_COOKING: [1, 1, 1, 1, 1],
            GENERAL_PIZZA: [1, 1, 1, 1, 1],
        }
    )

    checker.check_message(UNRELATED_COOKING)
    checker.check_message(GENERAL_PIZZA)

    protected_calls = [call for call in backend.calls if len(call) == 5]
    assert len(protected_calls) == 1


def test_async_check_offloads_only_semantic_work(monkeypatch):
    checker, _ = semantic_checker({PARAPHRASE: [0, 0, 0.98, 0.1, 0]})
    calls = []

    async def fake_to_thread(function, *args):
        calls.append((function, args))
        return function(*args)

    monkeypatch.setattr("security.dlp.asyncio.to_thread", fake_to_thread)

    direct_result = asyncio.run(checker.check_message_async(PROTECTED_FRAGMENT))
    semantic_result = asyncio.run(checker.check_message_async(PARAPHRASE))

    assert direct_result.decision.reason_code == "DLP_PROTECTED_CONTENT"
    assert semantic_result.decision.reason_code == "DLP_SEMANTIC_MATCH"
    assert calls == [(checker._check_semantic, (PARAPHRASE,))]


def test_sentence_transformer_model_loads_once(monkeypatch):
    created_models = []

    class FakeModel:
        def __init__(self, model_name):
            created_models.append(model_name)

        def encode(self, texts, **options):
            assert options == {
                "normalize_embeddings": True,
                "show_progress_bar": False,
            }
            return [[1.0, 0.0] for _ in texts]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeModel),
    )
    backend = SentenceTransformerEmbeddingBackend()

    backend.encode(["first"])
    backend.encode(["second"])

    assert created_models == ["all-MiniLM-L6-v2"]


def test_semantic_blocked_message_is_not_broadcast(tmp_path, monkeypatch, caplog):
    rooms = RoomService(
        StorageManager(
            str(tmp_path / "users.json"),
            str(tmp_path / "rooms.json"),
        )
    )
    room = rooms.create_room(1, "general")
    rooms.join_room(2, room.room_id)

    sender = ClientSession(FakeWebSocket())
    sender.user_id = 1
    sender.username = "soma"
    recipient = ClientSession(FakeWebSocket())
    recipient.user_id = 2
    recipient.username = "keren"
    online_users = AppStore()
    online_users.online_users = {1: sender, 2: recipient}
    checker, _ = semantic_checker({PARAPHRASE: [0, 0, 0.98, 0.1, 0]})

    async def fake_to_thread(function, *args):
        return function(*args)

    monkeypatch.setattr("security.dlp.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(client_session, "room_service", rooms)
    monkeypatch.setattr(client_session, "store", online_users)
    monkeypatch.setattr(
        client_session,
        "anti_bot",
        AntiBotRateLimiter(max_messages=5, clock=FakeClock()),
    )
    monkeypatch.setattr(client_session, "dlp", checker)
    caplog.set_level(logging.INFO, logger=client_session.logger.name)

    response = asyncio.run(
        client_session.handle_send_message(
            sender,
            "request-1",
            {"room_id": room.room_id, "message": PARAPHRASE},
        )
    )

    assert response["status"] == "error"
    assert response["code"] == "DLP_SEMANTIC_MATCH"
    assert sender.websocket.sent == []
    assert recipient.websocket.sent == []
    dlp_log = next(
        message
        for message in caplog.messages
        if "event=SECURITY_DECISION" in message and "control=DLP" in message
    )
    assert "decision=BLOCK" in dlp_log
    assert "reason_code=DLP_SEMANTIC_MATCH" in dlp_log
    assert "matched_fragment_id=knead_and_rise" in dlp_log
    assert "similarity=0.995" in dlp_log
    assert PARAPHRASE not in caplog.text
