# syntax=docker/dockerfile:1
# --- Install Python deps into a venv (no compilers needed: wheels only) ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# Omit pytest and other dev-only lines from the production image
RUN pip install --upgrade pip \
    && grep -vE '^\s*(#|$)' requirements.txt | grep -vi pytest > /tmp/requirements.app.txt \
    && pip install --no-cache-dir -r /tmp/requirements.app.txt

# --- Minimal runtime: copy venv only (no pip, no build cache) --------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY chatbot ./chatbot
COPY alembic.ini .
COPY alembic ./alembic

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --no-create-home --home-dir /nonexistent appuser \
    && chown -R appuser:app /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "chatbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
