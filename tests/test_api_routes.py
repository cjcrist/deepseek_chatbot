from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chatbot.api.routes import router
from chatbot.api.schemas import (
    ArchivedChatsResponse,
    ArchiveBucket,
    ChatActionResponse,
    ChatHistoryResponse,
    ChatListResponse,
    ChatMessage,
    ChatStartResponse,
    ChatSummary,
    MessageResponse,
)
from chatbot.services.explanation_level import ExplanationLevel
from chatbot.services.chat_service import ChatNotFoundError, ChatOwnershipError
from chatbot.services.deepseek_client import DeepSeekError


def build_test_client(service) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.chat_service = service
    return TestClient(app)


class StubChatService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.start_chat_response = ChatStartResponse(user_id="user-1", chat_id="chat-1", created=True)
        self.start_chat_error: Exception | None = None
        self.send_message_response = MessageResponse(
            user_id="user-1",
            chat_id="chat-1",
            message=ChatMessage(
                role="assistant",
                content="hello",
                created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
            ),
        )
        self.send_message_error: Exception | None = None
        self.list_user_chats_response = ChatListResponse(
            user_id="user-1",
            chats=[
                ChatSummary(
                    chat_id="chat-1",
                    user_id="user-1",
                    created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
                )
            ],
        )
        self.get_chat_history_response = ChatHistoryResponse(
            user_id="user-1",
            chat_id="chat-1",
            messages=[
                ChatMessage(
                    role="user",
                    content="hi",
                    created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
                ),
                ChatMessage(
                    role="assistant",
                    content="hello",
                    created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
                ),
            ],
        )
        self.get_chat_history_error: Exception | None = None
        self.archived_response = ArchivedChatsResponse(
            user_id="user-1",
            retention_days=30,
            buckets=[
                ArchiveBucket(bucket_id="last_24h", title="Last 24 hours", chats=[]),
            ],
        )
        self.archive_error: Exception | None = None

    async def start_chat(self, *, user_id: str, chat_id: str | None = None) -> ChatStartResponse:
        self.calls.append(("start_chat", {"user_id": user_id, "chat_id": chat_id}))
        if self.start_chat_error:
            raise self.start_chat_error
        return self.start_chat_response

    async def send_message(
        self,
        *,
        user_id: str,
        chat_id: str,
        content: str,
        explanation_level: ExplanationLevel = ExplanationLevel.MODERATE,
        system_prompt: str | None = None,
    ) -> MessageResponse:
        self.calls.append(
            (
                "send_message",
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "content": content,
                    "explanation_level": explanation_level,
                    "system_prompt": system_prompt,
                },
            )
        )
        if self.send_message_error:
            raise self.send_message_error
        return self.send_message_response

    async def send_message_stream(
        self,
        *,
        user_id: str,
        chat_id: str,
        content: str,
        explanation_level: ExplanationLevel = ExplanationLevel.MODERATE,
        system_prompt: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(
            (
                "send_message_stream",
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "content": content,
                    "explanation_level": explanation_level,
                    "system_prompt": system_prompt,
                },
            )
        )
        yield {"type": "chunk", "text": "hi"}
        yield {
            "type": "done",
            "user_id": user_id,
            "chat_id": chat_id,
            "message": {
                "role": "assistant",
                "content": "hello",
                "created_at": "2026-03-19T00:00:00Z",
            },
        }

    async def list_user_chats(self, user_id: str) -> ChatListResponse:
        self.calls.append(("list_user_chats", {"user_id": user_id}))
        return self.list_user_chats_response

    async def get_chat_history(self, *, user_id: str, chat_id: str) -> ChatHistoryResponse:
        self.calls.append(("get_chat_history", {"user_id": user_id, "chat_id": chat_id}))
        if self.get_chat_history_error:
            raise self.get_chat_history_error
        return self.get_chat_history_response

    async def list_archived_chats_grouped(self, user_id: str) -> ArchivedChatsResponse:
        self.calls.append(("list_archived_chats_grouped", {"user_id": user_id}))
        return self.archived_response

    async def archive_chat(self, user_id: str, chat_id: str) -> ChatActionResponse:
        self.calls.append(("archive_chat", {"user_id": user_id, "chat_id": chat_id}))
        if self.archive_error:
            raise self.archive_error
        return ChatActionResponse(user_id=user_id, chat_id=chat_id)

    async def restore_chat(self, user_id: str, chat_id: str) -> ChatActionResponse:
        self.calls.append(("restore_chat", {"user_id": user_id, "chat_id": chat_id}))
        if self.archive_error:
            raise self.archive_error
        return ChatActionResponse(user_id=user_id, chat_id=chat_id)

    async def delete_chat_permanently(self, user_id: str, chat_id: str) -> ChatActionResponse:
        self.calls.append(("delete_chat_permanently", {"user_id": user_id, "chat_id": chat_id}))
        if self.archive_error:
            raise self.archive_error
        return ChatActionResponse(user_id=user_id, chat_id=chat_id)


def test_healthcheck_returns_ok() -> None:
    client = build_test_client(StubChatService())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_chat_returns_created_chat() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.post("/chats/start", json={"user_id": "user-1", "chat_id": "chat-1"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "chat_id": "chat-1", "created": True}
    assert service.calls == [("start_chat", {"user_id": "user-1", "chat_id": "chat-1"})]


def test_start_chat_returns_forbidden_when_chat_owned_by_other_user() -> None:
    service = StubChatService()
    service.start_chat_error = ChatOwnershipError("belongs to another user")
    client = build_test_client(service)

    response = client.post("/chats/start", json={"user_id": "user-1", "chat_id": "chat-1"})

    assert response.status_code == 403
    assert response.json() == {"detail": "belongs to another user"}


def test_send_message_returns_assistant_response() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.post(
        "/chats/chat-1/messages",
        json={
            "user_id": "user-1",
            "content": "hello",
            "system_prompt": "be concise",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "chat_id": "chat-1",
        "message": {
            "role": "assistant",
            "content": "hello",
            "created_at": "2026-03-19T00:00:00Z",
        },
    }
    assert service.calls == [
        (
            "send_message",
            {
                "user_id": "user-1",
                "chat_id": "chat-1",
                "content": "hello",
                "explanation_level": ExplanationLevel.MODERATE,
                "system_prompt": "be concise",
            },
        )
    ]


def test_send_message_stream_returns_sse() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.post(
        "/chats/chat-1/messages",
        json={"user_id": "user-1", "content": "hello", "stream": True},
    )

    assert response.status_code == 200
    assert "text/event-stream" in (response.headers.get("content-type") or "")
    text = response.text
    assert '"type": "chunk"' in text or '"type":"chunk"' in text
    assert '"type": "done"' in text or '"type":"done"' in text
    assert service.calls == [
        (
            "send_message_stream",
            {
                "user_id": "user-1",
                "chat_id": "chat-1",
                "content": "hello",
                "explanation_level": ExplanationLevel.MODERATE,
                "system_prompt": None,
            },
        )
    ]


def test_send_message_passes_explanation_level() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.post(
        "/chats/chat-1/messages",
        json={
            "user_id": "user-1",
            "content": "hello",
            "explanation_level": "beginner",
        },
    )

    assert response.status_code == 200
    assert service.calls == [
        (
            "send_message",
            {
                "user_id": "user-1",
                "chat_id": "chat-1",
                "content": "hello",
                "explanation_level": ExplanationLevel.BEGINNER,
                "system_prompt": None,
            },
        )
    ]


def test_send_message_returns_not_found_for_missing_chat() -> None:
    service = StubChatService()
    service.send_message_error = ChatNotFoundError("chat missing")
    client = build_test_client(service)

    response = client.post("/chats/chat-1/messages", json={"user_id": "user-1", "content": "hello"})

    assert response.status_code == 404
    assert response.json() == {"detail": "chat missing"}


def test_send_message_returns_forbidden_for_wrong_owner() -> None:
    service = StubChatService()
    service.send_message_error = ChatOwnershipError("forbidden")
    client = build_test_client(service)

    response = client.post("/chats/chat-1/messages", json={"user_id": "user-1", "content": "hello"})

    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


def test_send_message_returns_bad_gateway_for_deepseek_failure() -> None:
    service = StubChatService()
    service.send_message_error = DeepSeekError("deepseek unavailable")
    client = build_test_client(service)

    response = client.post("/chats/chat-1/messages", json={"user_id": "user-1", "content": "hello"})

    assert response.status_code == 502
    assert response.json() == {"detail": "deepseek unavailable"}


def test_list_user_chats_returns_chat_collection() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.get("/users/user-1/chats")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "chats": [
            {
                "chat_id": "chat-1",
                "user_id": "user-1",
                "created_at": "2026-03-19T00:00:00Z",
                "updated_at": "2026-03-19T00:00:00Z",
            }
        ],
    }
    assert service.calls == [("list_user_chats", {"user_id": "user-1"})]


def test_get_chat_history_returns_messages() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.get("/chats/chat-1/messages", params={"user_id": "user-1"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "chat_id": "chat-1",
        "messages": [
            {"role": "user", "content": "hi", "created_at": "2026-03-19T00:00:00Z"},
            {"role": "assistant", "content": "hello", "created_at": "2026-03-19T00:00:00Z"},
        ],
    }
    assert service.calls == [("get_chat_history", {"user_id": "user-1", "chat_id": "chat-1"})]


def test_get_chat_history_returns_not_found() -> None:
    service = StubChatService()
    service.get_chat_history_error = ChatNotFoundError("chat missing")
    client = build_test_client(service)

    response = client.get("/chats/chat-1/messages", params={"user_id": "user-1"})

    assert response.status_code == 404
    assert response.json() == {"detail": "chat missing"}


def test_get_chat_history_returns_forbidden() -> None:
    service = StubChatService()
    service.get_chat_history_error = ChatOwnershipError("forbidden")
    client = build_test_client(service)

    response = client.get("/chats/chat-1/messages", params={"user_id": "user-1"})

    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


def test_list_archived_chats() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.get("/users/user-1/chats/archived")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user-1"
    assert body["retention_days"] == 30
    assert len(body["buckets"]) == 1
    assert body["buckets"][0]["bucket_id"] == "last_24h"
    assert service.calls == [("list_archived_chats_grouped", {"user_id": "user-1"})]


def test_archive_chat_endpoint() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.post("/users/user-1/chats/chat-1/archive")

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "chat_id": "chat-1", "ok": True}
    assert service.calls == [("archive_chat", {"user_id": "user-1", "chat_id": "chat-1"})]


def test_restore_chat_endpoint() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.post("/users/user-1/chats/chat-1/restore")

    assert response.status_code == 200
    assert service.calls == [("restore_chat", {"user_id": "user-1", "chat_id": "chat-1"})]


def test_delete_chat_endpoint() -> None:
    service = StubChatService()
    client = build_test_client(service)

    response = client.delete("/users/user-1/chats/chat-1")

    assert response.status_code == 200
    assert service.calls == [("delete_chat_permanently", {"user_id": "user-1", "chat_id": "chat-1"})]
