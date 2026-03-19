"""Chat orchestration service."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chatbot.api.schemas import (
    ArchivedChatSummary,
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
from chatbot.db import Chat, Message, User, utcnow
from chatbot.services.assistant_blocks import normalize_assistant_output
from chatbot.services.deepseek_client import DeepSeekClient
from chatbot.services.explanation_level import ExplanationLevel
from chatbot.services.system_prompts import build_system_prompt


class ChatNotFoundError(LookupError):
    """Raised when the requested chat does not exist."""


class ChatOwnershipError(PermissionError):
    """Raised when a user references a chat they do not own."""


class ChatState(TypedDict):
    """LangGraph state stored in memory for active chats."""

    messages: Annotated[list[BaseMessage], add_messages]


def persist_state(_: ChatState) -> dict[str, list[BaseMessage]]:
    """Passthrough node so LangGraph checkpoints the message state."""
    return {}


_ARCHIVE_BUCKET_ORDER: list[tuple[str, str]] = [
    ("last_24h", "Last 24 hours"),
    ("1_7d", "1–7 days ago"),
    ("7_21d", "1–3 weeks ago"),
    ("21_30d", "3–4 weeks ago"),
]


class ChatService:
    """Coordinates chat memory, storage, and DeepSeek responses."""

    def __init__(
        self,
        session_factory,
        deepseek_client: DeepSeekClient,
        *,
        archive_retention_days: int = 30,
    ) -> None:
        self._session_factory = session_factory
        self._deepseek_client = deepseek_client
        self._archive_retention_days = archive_retention_days
        self._checkpointer = InMemorySaver()

        builder = StateGraph(ChatState)
        builder.add_node("persist", persist_state)
        builder.add_edge(START, "persist")
        builder.add_edge("persist", END)
        self._graph = builder.compile(checkpointer=self._checkpointer)

    async def start_chat(self, user_id: str, chat_id: str | None = None) -> ChatStartResponse:
        """Create or resume a chat for a user."""
        resolved_chat_id = chat_id or str(uuid4())
        created = False

        async with self._session_factory() as session:
            await self._purge_expired_archives(session)

            user = await session.get(User, user_id)
            if user is None:
                user = User(user_id=user_id)
                session.add(user)

            chat = await session.get(Chat, resolved_chat_id)
            if chat is None:
                chat = Chat(chat_id=resolved_chat_id, user_id=user_id)
                session.add(chat)
                created = True
            elif chat.user_id != user_id:
                raise ChatOwnershipError("The requested chat belongs to a different user.")
            elif chat.archived_at is not None:
                chat.archived_at = None

            user.latest_chat_id = resolved_chat_id
            user.updated_at = utcnow()
            chat.updated_at = utcnow()
            await session.commit()

        return ChatStartResponse(user_id=user_id, chat_id=resolved_chat_id, created=created)

    async def list_user_chats(self, user_id: str) -> ChatListResponse:
        """Return active (non-archived) chats owned by the user."""
        async with self._session_factory() as session:
            await self._purge_expired_archives(session)

            user = await session.get(User, user_id)
            if user is None:
                return ChatListResponse(user_id=user_id, chats=[])

            result = await session.execute(
                select(Chat)
                .where(Chat.user_id == user_id, Chat.archived_at.is_(None))
                .order_by(Chat.updated_at.desc())
            )
            chats = list(result.scalars().all())

            return ChatListResponse(
                user_id=user_id,
                chats=[
                    ChatSummary(
                        chat_id=chat.chat_id,
                        user_id=chat.user_id,
                        created_at=chat.created_at,
                        updated_at=chat.updated_at,
                    )
                    for chat in chats
                ],
            )

    async def list_archived_chats_grouped(self, user_id: str) -> ArchivedChatsResponse:
        """Return archived chats within retention, grouped by age since archival."""
        retention = self._archive_retention_days
        cutoff = utcnow() - timedelta(days=retention)
        now = utcnow()

        async with self._session_factory() as session:
            await self._purge_expired_archives(session)

            result = await session.execute(
                select(Chat).where(Chat.user_id == user_id, Chat.archived_at.isnot(None))
            )
            rows = list(result.scalars().all())

        chats = [row for row in rows if self._normalize_utc(row.archived_at) >= cutoff]
        chats.sort(key=lambda c: self._normalize_utc(c.archived_at), reverse=True)

        by_bucket: dict[str, list[ArchivedChatSummary]] = {bid: [] for bid, _ in _ARCHIVE_BUCKET_ORDER}
        for row in chats:
            assert row.archived_at is not None
            bid = self._bucket_id_for_archived_at(row.archived_at, now)
            by_bucket[bid].append(
                ArchivedChatSummary(
                    chat_id=row.chat_id,
                    user_id=row.user_id,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    archived_at=row.archived_at,
                )
            )

        buckets = [
            ArchiveBucket(bucket_id=bid, title=title, chats=by_bucket[bid])
            for bid, title in _ARCHIVE_BUCKET_ORDER
        ]
        return ArchivedChatsResponse(
            user_id=user_id,
            retention_days=retention,
            buckets=buckets,
        )

    async def archive_chat(self, user_id: str, chat_id: str) -> ChatActionResponse:
        """Move a chat out of the active sidebar list."""
        async with self._session_factory() as session:
            await self._purge_expired_archives(session)
            chat = await session.get(Chat, chat_id)
            if chat is None:
                raise ChatNotFoundError("Chat was not found.")
            if chat.user_id != user_id:
                raise ChatOwnershipError("The requested chat belongs to a different user.")

            chat.archived_at = utcnow()
            chat.updated_at = utcnow()

            user = await session.get(User, user_id)
            if user is not None and user.latest_chat_id == chat_id:
                user.latest_chat_id = await self._fallback_latest_active_id(session, user_id, exclude=chat_id)
                user.updated_at = utcnow()

            await session.commit()

        return ChatActionResponse(user_id=user_id, chat_id=chat_id)

    async def restore_chat(self, user_id: str, chat_id: str) -> ChatActionResponse:
        """Return an archived chat to the active list."""
        async with self._session_factory() as session:
            await self._purge_expired_archives(session)
            chat = await session.get(Chat, chat_id)
            if chat is None:
                raise ChatNotFoundError("Chat was not found.")
            if chat.user_id != user_id:
                raise ChatOwnershipError("The requested chat belongs to a different user.")
            if chat.archived_at is None:
                return ChatActionResponse(user_id=user_id, chat_id=chat_id)

            chat.archived_at = None
            chat.updated_at = utcnow()
            await session.commit()

        return ChatActionResponse(user_id=user_id, chat_id=chat_id)

    async def delete_chat_permanently(self, user_id: str, chat_id: str) -> ChatActionResponse:
        """Hard-delete a chat and its messages (active or archived)."""
        async with self._session_factory() as session:
            await self._purge_expired_archives(session)
            chat = await session.get(Chat, chat_id)
            if chat is None:
                raise ChatNotFoundError("Chat was not found.")
            if chat.user_id != user_id:
                raise ChatOwnershipError("The requested chat belongs to a different user.")

            user = await session.get(User, user_id)
            if user is not None and user.latest_chat_id == chat_id:
                user.latest_chat_id = await self._fallback_latest_active_id(session, user_id, exclude=chat_id)
                user.updated_at = utcnow()

            await session.delete(chat)
            await session.commit()

        return ChatActionResponse(user_id=user_id, chat_id=chat_id)

    async def get_chat_history(self, user_id: str, chat_id: str) -> ChatHistoryResponse:
        """Fetch the stored message history for a chat."""
        async with self._session_factory() as session:
            await self._purge_expired_archives(session)

            chat = await session.get(Chat, chat_id)
            if chat is None:
                raise ChatNotFoundError("Chat was not found.")
            if chat.user_id != user_id:
                raise ChatOwnershipError("The requested chat belongs to a different user.")

            result = await session.execute(
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            messages = list(result.scalars().all())

            return ChatHistoryResponse(
                user_id=user_id,
                chat_id=chat_id,
                messages=[
                    ChatMessage(role=message.role, content=message.content, created_at=message.created_at)
                    for message in messages
                ],
            )

    async def send_message(
        self,
        *,
        user_id: str,
        chat_id: str,
        content: str,
        explanation_level: ExplanationLevel = ExplanationLevel.MODERATE,
        system_prompt: str | None = None,
    ) -> MessageResponse:
        """Generate and persist an assistant reply for a chat."""
        combined_system = build_system_prompt(explanation_level, system_prompt)

        async with self._session_factory() as session:
            await self._purge_expired_archives(session)

            chat = await session.get(Chat, chat_id)
            if chat is None:
                raise ChatNotFoundError("Chat was not found.")
            if chat.user_id != user_id:
                raise ChatOwnershipError("The requested chat belongs to a different user.")

            if chat.archived_at is not None:
                chat.archived_at = None

            user = await session.get(User, user_id)
            if user is None:
                raise ChatNotFoundError("User was not found.")

            result = await session.execute(
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            stored_messages = list(result.scalars().all())

        await self._ensure_memory_seeded_async(chat_id=chat_id, stored_messages=stored_messages)
        prior_messages = self._get_thread_messages(chat_id)
        prompt_messages = self._serialize_for_deepseek(
            messages=prior_messages + [HumanMessage(content=content)],
            system_prompt=combined_system,
        )
        assistant_text = await self._deepseek_client.generate_response(prompt_messages)
        stored_assistant_content = normalize_assistant_output(assistant_text)

        async with self._session_factory() as session:
            user_message = Message(chat_id=chat_id, role="user", content=content)
            assistant_message = Message(
                chat_id=chat_id,
                role="assistant",
                content=stored_assistant_content,
            )
            session.add_all([user_message, assistant_message])

            u = await session.get(User, user_id)
            c = await session.get(Chat, chat_id)
            assert u is not None and c is not None
            u.latest_chat_id = chat_id
            u.updated_at = utcnow()
            c.updated_at = utcnow()
            await session.commit()
            await session.refresh(assistant_message)

        await asyncio.to_thread(
            self._graph.invoke,
            {
                "messages": [
                    HumanMessage(content=content),
                    AIMessage(content=stored_assistant_content),
                ]
            },
            self._thread_config(chat_id),
        )

        return MessageResponse(
            user_id=user_id,
            chat_id=chat_id,
            message=ChatMessage(
                role=assistant_message.role,
                content=assistant_message.content,
                created_at=assistant_message.created_at,
            ),
        )

    async def send_message_stream(
        self,
        *,
        user_id: str,
        chat_id: str,
        content: str,
        explanation_level: ExplanationLevel = ExplanationLevel.MODERATE,
        system_prompt: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream assistant tokens as JSON lines, then a final ``done`` event."""
        combined_system = build_system_prompt(explanation_level, system_prompt)

        async with self._session_factory() as session:
            await self._purge_expired_archives(session)

            chat = await session.get(Chat, chat_id)
            if chat is None:
                yield {"type": "error", "detail": "Chat was not found."}
                return
            if chat.user_id != user_id:
                yield {"type": "error", "detail": "The requested chat belongs to a different user."}
                return

            if chat.archived_at is not None:
                chat.archived_at = None

            user = await session.get(User, user_id)
            if user is None:
                yield {"type": "error", "detail": "User was not found."}
                return

            result = await session.execute(
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            stored_messages = list(result.scalars().all())

        await self._ensure_memory_seeded_async(chat_id=chat_id, stored_messages=stored_messages)
        prior_messages = self._get_thread_messages(chat_id)
        prompt_messages = self._serialize_for_deepseek(
            messages=prior_messages + [HumanMessage(content=content)],
            system_prompt=combined_system,
        )

        async with self._session_factory() as session:
            user_message = Message(chat_id=chat_id, role="user", content=content)
            session.add(user_message)
            u = await session.get(User, user_id)
            c = await session.get(Chat, chat_id)
            assert u is not None and c is not None
            u.latest_chat_id = chat_id
            u.updated_at = utcnow()
            c.updated_at = utcnow()
            await session.commit()
            await session.refresh(user_message)

        accumulated: list[str] = []
        try:
            async for delta in self._deepseek_client.stream_chat_completion(prompt_messages):
                accumulated.append(delta)
                yield {"type": "chunk", "text": delta}
        except Exception as exc:
            yield {"type": "error", "detail": str(exc)}
            return

        full_raw = "".join(accumulated)
        stored_assistant_content = normalize_assistant_output(full_raw)

        async with self._session_factory() as session:
            assistant_message = Message(
                chat_id=chat_id,
                role="assistant",
                content=stored_assistant_content,
            )
            session.add(assistant_message)
            c = await session.get(Chat, chat_id)
            u = await session.get(User, user_id)
            assert c is not None and u is not None
            c.updated_at = utcnow()
            u.updated_at = utcnow()
            await session.commit()
            await session.refresh(assistant_message)

        await asyncio.to_thread(
            self._graph.invoke,
            {
                "messages": [
                    HumanMessage(content=content),
                    AIMessage(content=stored_assistant_content),
                ]
            },
            self._thread_config(chat_id),
        )

        yield {
            "type": "done",
            "user_id": user_id,
            "chat_id": chat_id,
            "message": {
                "role": assistant_message.role,
                "content": assistant_message.content,
                "created_at": assistant_message.created_at.isoformat(),
            },
        }

    async def _purge_expired_archives(self, session: AsyncSession) -> None:
        """Delete archived chats older than the configured retention window."""
        days = self._archive_retention_days
        cutoff = utcnow() - timedelta(days=days)
        result = await session.execute(select(Chat).where(Chat.archived_at.isnot(None)))
        archived_rows = list(result.scalars().all())
        stale = [row for row in archived_rows if self._normalize_utc(row.archived_at) < cutoff]
        for row in stale:
            await session.delete(row)
        if stale:
            await session.commit()

    @staticmethod
    async def _fallback_latest_active_id(
        session: AsyncSession,
        user_id: str,
        exclude: str | None,
    ) -> str | None:
        stmt = select(Chat).where(Chat.user_id == user_id, Chat.archived_at.is_(None))
        if exclude:
            stmt = stmt.where(Chat.chat_id != exclude)
        stmt = stmt.order_by(Chat.updated_at.desc()).limit(1)
        r = await session.execute(stmt)
        row = r.scalar_one_or_none()
        return row.chat_id if row else None

    @staticmethod
    def _normalize_utc(dt: datetime | None) -> datetime:
        """Make datetimes UTC-aware (SQLite often returns naive UTC values)."""
        if dt is None:
            raise ValueError("expected non-null datetime")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _bucket_id_for_archived_at(cls, archived_at: datetime, now: datetime) -> str:
        """Map archive time to a UI bucket (by age since archival, in days)."""
        arch = cls._normalize_utc(archived_at)
        n = cls._normalize_utc(now)
        age_days = (n - arch).total_seconds() / 86400.0
        if age_days < 1.0:
            return "last_24h"
        if age_days < 7.0:
            return "1_7d"
        if age_days < 21.0:
            return "7_21d"
        return "21_30d"

    async def _ensure_memory_seeded_async(self, *, chat_id: str, stored_messages: list[Message]) -> None:
        """Seed in-memory state from Postgres the first time a chat is touched."""
        if self._get_thread_messages(chat_id):
            return

        if not stored_messages:
            return

        lc_messages = [self._to_langchain_message(message) for message in stored_messages]
        await asyncio.to_thread(
            self._graph.invoke,
            {"messages": lc_messages},
            self._thread_config(chat_id),
        )

    def _get_thread_messages(self, chat_id: str) -> list[BaseMessage]:
        """Return the current in-memory message list for a chat."""
        try:
            snapshot = self._graph.get_state(self._thread_config(chat_id))
        except Exception:
            return []

        values = getattr(snapshot, "values", {}) or {}
        return list(values.get("messages", []))

    @staticmethod
    def _serialize_for_deepseek(
        *,
        messages: list[BaseMessage],
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        """Convert LangChain messages into OpenAI-style messages."""
        payload: list[dict[str, str]] = []

        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})

        for message in messages:
            if isinstance(message, HumanMessage):
                payload.append({"role": "user", "content": str(message.content)})
            elif isinstance(message, AIMessage):
                payload.append({"role": "assistant", "content": str(message.content)})

        return payload

    @staticmethod
    def _to_langchain_message(message: Message) -> BaseMessage:
        """Convert a stored ORM message into a LangChain message."""
        if message.role == "assistant":
            return AIMessage(content=message.content)
        return HumanMessage(content=message.content)

    @staticmethod
    def _thread_config(chat_id: str) -> dict[str, dict[str, str]]:
        """Return LangGraph thread configuration for a chat."""
        return {"configurable": {"thread_id": chat_id}}
