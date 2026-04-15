# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Kanban project management app with an AI chat assistant. The architecture is a FastAPI backend (Python) serving a static Next.js frontend, deployed as a single Docker container.

- **Backend**: FastAPI + SQLite (`backend/data.db`), serves REST API at `/api/*` and hosts the built frontend static files
- **Frontend**: Next.js (App Router) + React 19 + Tailwind CSS v4 + @dnd-kit for drag-and-drop
- **AI**: OpenRouter API (`openai/gpt-oss-120b`) for the board chat assistant
- **Database**: SQLite with tables: `users`, `boards`, `columns`, `cards`

The board state is keyed by `username`. On first access, the board is seeded with default columns/cards.

## Running the App

```bash
# Start (builds and runs Docker container on port 8000)
./scripts/start.sh        # Mac/Linux
./scripts/start.ps1       # Windows PowerShell

# Stop
./scripts/stop.sh
./scripts/stop.ps1
```

Requires a `.env` file at the repo root with `OPENROUTER_API_KEY=...`.

## Backend Development

```bash
cd backend

# Install dependencies (uses uv)
uv pip install -r requirements.txt

# Run dev server (from repo root)
uvicorn backend.app.main:app --reload --port 8000

# Run all backend tests (from repo root)
pytest backend/

# Run a single test file
pytest backend/tests/test_api.py

# Run a single test
pytest backend/tests/test_api.py::test_get_board_seeds_default
```

Backend tests use `monkeypatch.setenv("PM_DB_PATH", ...)` with `tmp_path` to isolate SQLite databases — no mocking of the database.

## Frontend Development

```bash
cd frontend

npm install

# Dev server (port 3000, proxies /api to backend)
npm run dev

# Unit tests (Vitest)
npm run test:unit

# Watch mode
npm run test:unit:watch

# E2E tests (Playwright — not required for this project)
npm run test:e2e

# Build static export
npm run build
```

## Architecture Notes

### Data Flow

The `BoardData` schema (`backend/app/schemas.py`) is the shared data contract:
- `columns: list[Column]` — ordered list with `cardIds` arrays defining card order
- `cards: dict[str, Card]` — flat map of all cards by id

`save_board` does a full clear-and-reinsert on every save (not partial updates).

### AI Chat (`POST /api/ai/chat`)

Sends the full board JSON + conversation history to OpenRouter. The AI returns `AIChatResult` JSON with an optional `reply` string and optional updated `BoardData`. If the board is updated, it is validated and saved before responding.

### Frontend Board State

`KanbanBoard.tsx` owns all board state client-side. The board data mirrors `BoardData` from the backend. `src/lib/kanban.ts` contains the `moveCard` logic for drag-and-drop reordering and cross-column moves.

### Static Serving

In production (Docker), the built Next.js output (`frontend/out`) is mounted and served by FastAPI's `StaticFiles` at `/`. The frontend must be built with `output: 'export'` (static export mode).
