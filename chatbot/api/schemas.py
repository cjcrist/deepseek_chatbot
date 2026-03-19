"""API request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from chatbot.services.explanation_level import ExplanationLevel


class ChatStartRequest(BaseModel):
    """Create or resume a chat for a user."""

    user_id: str = Field(min_length=1)
    chat_id: str | None = None


class ChatStartResponse(BaseModel):
    """Chat creation or resume response."""

    user_id: str
    chat_id: str
    created: bool


class MessageCreateRequest(BaseModel):
    """User prompt payload."""

    user_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    explanation_level: ExplanationLevel = Field(
        default=ExplanationLevel.MODERATE,
        description="beginner | moderate | expert — controls depth and assumed audience",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional extra instructions appended to the built-in system prompt.",
    )
    stream: bool = Field(
        default=False,
        description="If true, response is text/event-stream with JSON lines (chunk + done).",
    )


class ChatMessage(BaseModel):
    """Serialized chat message."""

    role: str
    content: str
    created_at: datetime


class MessageResponse(BaseModel):
    """Assistant reply payload."""

    user_id: str
    chat_id: str
    message: ChatMessage


class ChatSummary(BaseModel):
    """Stored chat metadata."""

    chat_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class ChatListResponse(BaseModel):
    """Collection of chats for a user."""

    user_id: str
    chats: list[ChatSummary]


class ArchivedChatSummary(BaseModel):
    """Archived chat row with archive timestamp (for recall UI)."""

    chat_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime


class ArchiveBucket(BaseModel):
    """Grouped archived chats by how long ago they were archived."""

    bucket_id: str
    title: str
    chats: list[ArchivedChatSummary]


class ArchivedChatsResponse(BaseModel):
    """Archived chats for a user, grouped by age since archival."""

    user_id: str
    retention_days: int
    buckets: list[ArchiveBucket]


class ChatActionResponse(BaseModel):
    """Simple acknowledgement for archive / restore / delete operations."""

    user_id: str
    chat_id: str
    ok: bool = True


class ChatHistoryResponse(BaseModel):
    """Full stored history for a chat."""

    user_id: str
    chat_id: str
    messages: list[ChatMessage]
