"""FastAPI routes for the chatbot service."""

import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from chatbot.api.schemas import (
    ArchivedChatsResponse,
    ChatActionResponse,
    ChatHistoryResponse,
    ChatListResponse,
    ChatStartRequest,
    ChatStartResponse,
    MessageCreateRequest,
    MessageResponse,
)
from chatbot.services.chat_service import ChatNotFoundError, ChatOwnershipError, ChatService
from chatbot.services.deepseek_client import DeepSeekError

router = APIRouter()


def get_chat_service(request: Request) -> ChatService:
    """Return the shared chat service from application state."""
    return request.app.state.chat_service


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    """Container-friendly health endpoint."""
    return {"status": "ok"}


@router.post("/chats/start", response_model=ChatStartResponse)
async def start_chat(payload: ChatStartRequest, request: Request) -> ChatStartResponse:
    """Create or resume a chat."""
    service = get_chat_service(request)

    try:
        return await service.start_chat(user_id=payload.user_id, chat_id=payload.chat_id)
    except ChatOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/chats/{chat_id}/messages")
async def send_message(chat_id: str, payload: MessageCreateRequest, request: Request):
    """Send a prompt to the assistant and persist the reply (JSON or SSE stream)."""
    service = get_chat_service(request)

    if payload.stream:

        async def event_stream():
            async for event in service.send_message_stream(
                user_id=payload.user_id,
                chat_id=chat_id,
                content=payload.content,
                explanation_level=payload.explanation_level,
                system_prompt=payload.system_prompt,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        return await service.send_message(
            user_id=payload.user_id,
            chat_id=chat_id,
            content=payload.content,
            explanation_level=payload.explanation_level,
            system_prompt=payload.system_prompt,
        )
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/users/{user_id}/chats", response_model=ChatListResponse)
async def list_user_chats(user_id: str, request: Request) -> ChatListResponse:
    """List active (non-archived) chats for a user."""
    service = get_chat_service(request)
    return await service.list_user_chats(user_id=user_id)


@router.get("/users/{user_id}/chats/archived", response_model=ArchivedChatsResponse)
async def list_archived_chats(user_id: str, request: Request) -> ArchivedChatsResponse:
    """List archived chats grouped by age since archival (within retention)."""
    service = get_chat_service(request)
    return await service.list_archived_chats_grouped(user_id=user_id)


@router.post(
    "/users/{user_id}/chats/{chat_id}/archive",
    response_model=ChatActionResponse,
)
async def archive_chat(user_id: str, chat_id: str, request: Request) -> ChatActionResponse:
    """Archive a chat (removes it from the active list)."""
    service = get_chat_service(request)
    try:
        return await service.archive_chat(user_id=user_id, chat_id=chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/users/{user_id}/chats/{chat_id}/restore",
    response_model=ChatActionResponse,
)
async def restore_chat(user_id: str, chat_id: str, request: Request) -> ChatActionResponse:
    """Restore an archived chat to the active list."""
    service = get_chat_service(request)
    try:
        return await service.restore_chat(user_id=user_id, chat_id=chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete(
    "/users/{user_id}/chats/{chat_id}",
    response_model=ChatActionResponse,
)
async def delete_chat_permanently(user_id: str, chat_id: str, request: Request) -> ChatActionResponse:
    """Permanently delete a chat and its messages."""
    service = get_chat_service(request)
    try:
        return await service.delete_chat_permanently(user_id=user_id, chat_id=chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/chats/{chat_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(chat_id: str, user_id: str, request: Request) -> ChatHistoryResponse:
    """Return the persisted history for a specific chat."""
    service = get_chat_service(request)

    try:
        return await service.get_chat_history(user_id=user_id, chat_id=chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
