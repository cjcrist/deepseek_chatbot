from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from chatbot.db import Base, Chat, Message, User, utcnow
from chatbot.services.assistant_blocks import normalize_assistant_output
from chatbot.services.chat_service import ChatNotFoundError, ChatOwnershipError, ChatService
from chatbot.services.explanation_level import ExplanationLevel
from chatbot.services.system_prompts import build_system_prompt


class StubDeepSeekClient:
    def __init__(
        self,
        responses: list[str] | None = None,
        stream_parts: list[str] | None = None,
    ) -> None:
        self.responses = responses or []
        self.stream_parts = stream_parts
        self.calls: list[Any] = []  # message lists or ("stream", messages)

    async def generate_response(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return "stubbed-response"

    async def stream_chat_completion(self, messages: list[dict[str, str]]):
        self.calls.append(("stream", messages))
        for part in self.stream_parts or ["stub"]:
            yield part

    async def aclose(self) -> None:
        pass


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_start_chat_creates_user_and_chat(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())

    response = await service.start_chat(user_id="user-1", chat_id="chat-1")

    assert response.user_id == "user-1"
    assert response.chat_id == "chat-1"
    assert response.created is True

    async with session_factory() as session:
        user = await session.get(User, "user-1")
        chat = await session.get(Chat, "chat-1")

        assert user is not None
        assert user.latest_chat_id == "chat-1"
        assert chat is not None
        assert chat.user_id == "user-1"


@pytest.mark.asyncio
async def test_start_chat_reuses_existing_chat_for_same_user(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    response = await service.start_chat(user_id="user-1", chat_id="chat-1")

    assert response.created is False

    async with session_factory() as session:
        rc = await session.execute(select(Chat))
        assert len(list(rc.scalars().all())) == 1
        ru = await session.execute(select(User))
        assert len(list(ru.scalars().all())) == 1


@pytest.mark.asyncio
async def test_start_chat_rejects_chat_owned_by_another_user(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    with pytest.raises(ChatOwnershipError):
        await service.start_chat(user_id="user-2", chat_id="chat-1")


@pytest.mark.asyncio
async def test_list_user_chats_returns_empty_for_unknown_user(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())

    response = await service.list_user_chats("missing-user")

    assert response.user_id == "missing-user"
    assert response.chats == []


@pytest.mark.asyncio
async def test_list_user_chats_returns_latest_first(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())
    await service.start_chat(user_id="user-1", chat_id="chat-1")
    await service.start_chat(user_id="user-1", chat_id="chat-2")

    response = await service.list_user_chats("user-1")

    assert [chat.chat_id for chat in response.chats] == ["chat-2", "chat-1"]


@pytest.mark.asyncio
async def test_get_chat_history_returns_messages(session_factory) -> None:
    deepseek = StubDeepSeekClient(responses=["hello there"])
    service = ChatService(session_factory=session_factory, deepseek_client=deepseek)
    await service.start_chat(user_id="user-1", chat_id="chat-1")
    await service.send_message(user_id="user-1", chat_id="chat-1", content="hi")

    response = await service.get_chat_history(user_id="user-1", chat_id="chat-1")

    assert response.user_id == "user-1"
    assert response.chat_id == "chat-1"
    assert [(message.role, message.content) for message in response.messages] == [
        ("user", "hi"),
        ("assistant", normalize_assistant_output("hello there")),
    ]


@pytest.mark.asyncio
async def test_get_chat_history_raises_for_missing_chat(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())

    with pytest.raises(ChatNotFoundError):
        await service.get_chat_history(user_id="user-1", chat_id="missing-chat")


@pytest.mark.asyncio
async def test_get_chat_history_raises_for_wrong_owner(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    with pytest.raises(ChatOwnershipError):
        await service.get_chat_history(user_id="user-2", chat_id="chat-1")


@pytest.mark.asyncio
async def test_send_message_persists_messages_and_passes_system_prompt(session_factory) -> None:
    deepseek = StubDeepSeekClient(responses=["assistant reply"])
    service = ChatService(session_factory=session_factory, deepseek_client=deepseek)
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    response = await service.send_message(
        user_id="user-1",
        chat_id="chat-1",
        content="hello",
        system_prompt="be brief",
    )

    assert response.chat_id == "chat-1"
    assert response.message.role == "assistant"
    assert response.message.content == normalize_assistant_output("assistant reply")
    expected_system = build_system_prompt(ExplanationLevel.MODERATE, "be brief")
    assert deepseek.calls == [
        [
            {"role": "system", "content": expected_system},
            {"role": "user", "content": "hello"},
        ]
    ]

    async with session_factory() as session:
        user = await session.get(User, "user-1")
        rm = await session.execute(select(Message).order_by(Message.id.asc()))
        messages = list(rm.scalars().all())

        assert user is not None
        assert user.latest_chat_id == "chat-1"
        assert [(message.role, message.content) for message in messages] == [
            ("user", "hello"),
            ("assistant", normalize_assistant_output("assistant reply")),
        ]


@pytest.mark.asyncio
async def test_send_message_stream(session_factory) -> None:
    deepseek = StubDeepSeekClient(stream_parts=["hel", "lo"])
    service = ChatService(session_factory=session_factory, deepseek_client=deepseek)
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    chunks: list[str] = []
    done = None
    async for ev in service.send_message_stream(
        user_id="user-1",
        chat_id="chat-1",
        content="hi",
    ):
        if ev.get("type") == "chunk":
            chunks.append(ev["text"])
        elif ev.get("type") == "done":
            done = ev

    assert chunks == ["hel", "lo"]
    assert done is not None
    assert done["message"]["role"] == "assistant"
    assert normalize_assistant_output("hello") == done["message"]["content"]


@pytest.mark.asyncio
async def test_send_message_uses_existing_memory_for_follow_up_turns(session_factory) -> None:
    deepseek = StubDeepSeekClient(responses=["first reply", "second reply"])
    service = ChatService(session_factory=session_factory, deepseek_client=deepseek)
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    await service.send_message(user_id="user-1", chat_id="chat-1", content="first")
    await service.send_message(user_id="user-1", chat_id="chat-1", content="second")

    sys_mod = build_system_prompt(ExplanationLevel.MODERATE)
    assert deepseek.calls[0] == [
        {"role": "system", "content": sys_mod},
        {"role": "user", "content": "first"},
    ]
    assert deepseek.calls[1] == [
        {"role": "system", "content": sys_mod},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": normalize_assistant_output("first reply")},
        {"role": "user", "content": "second"},
    ]


@pytest.mark.asyncio
async def test_send_message_rehydrates_memory_from_database_for_new_service(session_factory) -> None:
    first_client = StubDeepSeekClient(responses=["first reply"])
    first_service = ChatService(session_factory=session_factory, deepseek_client=first_client)
    await first_service.start_chat(user_id="user-1", chat_id="chat-1")
    sys_mod = build_system_prompt(ExplanationLevel.MODERATE)
    await first_service.send_message(user_id="user-1", chat_id="chat-1", content="first")

    assert first_client.calls[0] == [
        {"role": "system", "content": sys_mod},
        {"role": "user", "content": "first"},
    ]

    second_client = StubDeepSeekClient(responses=["second reply"])
    second_service = ChatService(session_factory=session_factory, deepseek_client=second_client)

    await second_service.send_message(user_id="user-1", chat_id="chat-1", content="second")

    assert second_client.calls == [
        [
            {"role": "system", "content": sys_mod},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": normalize_assistant_output("first reply")},
            {"role": "user", "content": "second"},
        ]
    ]


@pytest.mark.asyncio
async def test_send_message_raises_for_missing_chat(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())

    with pytest.raises(ChatNotFoundError):
        await service.send_message(user_id="user-1", chat_id="missing-chat", content="hello")


@pytest.mark.asyncio
async def test_send_message_expert_level_updates_system_prompt(session_factory) -> None:
    deepseek = StubDeepSeekClient(responses=["ok"])
    service = ChatService(session_factory=session_factory, deepseek_client=deepseek)
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    await service.send_message(
        user_id="user-1",
        chat_id="chat-1",
        content="question",
        explanation_level=ExplanationLevel.EXPERT,
    )

    system_text = deepseek.calls[0][0]["content"]
    assert "senior engineer" in system_text.lower()


@pytest.mark.asyncio
async def test_send_message_raises_for_wrong_owner(session_factory) -> None:
    service = ChatService(session_factory=session_factory, deepseek_client=StubDeepSeekClient())
    await service.start_chat(user_id="user-1", chat_id="chat-1")

    with pytest.raises(ChatOwnershipError):
        await service.send_message(user_id="user-2", chat_id="chat-1", content="hello")


@pytest.mark.asyncio
async def test_list_user_chats_excludes_archived(session_factory) -> None:
    service = ChatService(
        session_factory=session_factory,
        deepseek_client=StubDeepSeekClient(),
        archive_retention_days=30,
    )
    await service.start_chat(user_id="user-1", chat_id="chat-1")
    await service.archive_chat(user_id="user-1", chat_id="chat-1")

    active = await service.list_user_chats(user_id="user-1")
    assert active.chats == []

    archived = await service.list_archived_chats_grouped(user_id="user-1")
    assert sum(len(b.chats) for b in archived.buckets) == 1


@pytest.mark.asyncio
async def test_restore_chat_returns_to_active_list(session_factory) -> None:
    service = ChatService(
        session_factory=session_factory,
        deepseek_client=StubDeepSeekClient(),
        archive_retention_days=30,
    )
    await service.start_chat(user_id="user-1", chat_id="chat-1")
    await service.archive_chat(user_id="user-1", chat_id="chat-1")
    await service.restore_chat(user_id="user-1", chat_id="chat-1")

    active = await service.list_user_chats(user_id="user-1")
    assert len(active.chats) == 1
    assert active.chats[0].chat_id == "chat-1"


@pytest.mark.asyncio
async def test_purge_deletes_archived_older_than_retention(session_factory) -> None:
    service = ChatService(
        session_factory=session_factory,
        deepseek_client=StubDeepSeekClient(),
        archive_retention_days=30,
    )
    await service.start_chat(user_id="user-1", chat_id="old-chat")
    await service.archive_chat(user_id="user-1", chat_id="old-chat")

    async with session_factory() as session:
        chat = await session.get(Chat, "old-chat")
        assert chat is not None
        chat.archived_at = utcnow() - timedelta(days=31)
        await session.commit()

    await service.list_user_chats(user_id="user-1")

    async with session_factory() as session:
        assert await session.get(Chat, "old-chat") is None


@pytest.mark.asyncio
async def test_delete_chat_permanently_removes_row(session_factory) -> None:
    service = ChatService(
        session_factory=session_factory,
        deepseek_client=StubDeepSeekClient(),
        archive_retention_days=30,
    )
    await service.start_chat(user_id="user-1", chat_id="gone")
    await service.delete_chat_permanently(user_id="user-1", chat_id="gone")

    async with session_factory() as session:
        assert await session.get(Chat, "gone") is None
