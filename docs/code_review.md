# Code Review Report

**Project**: Kanban Project Management App  
**Date**: 2026-04-15  
**Reviewer**: Claude Code (claude-sonnet-4-6)  
**Scope**: Full repository review — backend, frontend, configuration, tests, Docker

---

## Table of Contents

1. [Immediate Actions Required](#immediate-actions-required)
2. [Critical Security Issues](#critical-security-issues)
3. [High Security Issues](#high-security-issues)
4. [Bugs and Correctness Issues](#bugs-and-correctness-issues)
5. [Code Quality Issues](#code-quality-issues)
6. [Performance Issues](#performance-issues)
7. [Test Coverage Gaps](#test-coverage-gaps)
8. [Dependency and Configuration Issues](#dependency-and-configuration-issues)
9. [Architectural Issues](#architectural-issues)
10. [Summary](#summary)
11. [Recommended Improvements by Priority](#recommended-improvements-by-priority)

---

## Immediate Actions Required

These must be addressed before any production or public deployment:

| # | Action | Reason |
|---|--------|--------|
| 1 | **Implement server-side authentication** | All endpoints are currently unprotected |
| 2 | **Validate auth on every API endpoint** | Username param is trusted blindly from the request |
| 3 | **Add rate limiting to AI endpoint** | Unguarded endpoint can exhaust OpenRouter quota |

---

## Critical Security Issues

### 1. Hardcoded Credentials in Frontend Bundle

**File**: `frontend/src/components/AuthGate.tsx` (lines 10–11)  
**Severity**: Critical

> Note: `.env` is correctly listed in `.gitignore` and is not committed to the repository. API key management is handled properly.

```typescript
const VALID_USERNAME = "user";
const VALID_PASSWORD = "password";
```

Client-side authentication is fundamentally insecure — the credentials are shipped in the JavaScript bundle and visible to anyone who opens DevTools. There is no server-side check on login.

**Fix**: Implement a proper login endpoint (`POST /api/auth/login`) that returns a signed JWT or sets an HTTP-only session cookie. Never store credentials in JavaScript.

---

### 3. No Authentication on API Endpoints

**File**: `backend/app/main.py` (all routes)  
**Severity**: Critical

Every API endpoint accepts a `username` parameter from the request body or path, but nothing verifies that the caller actually owns that username. Any user can read or overwrite any other user's board by supplying a different username.

```python
@app.get("/api/board/{username}")   # line 168 — no auth check
@app.put("/api/board/{username}")   # line 172 — no auth check
```

**Fix**: Extract the authenticated user's identity from a verified token (JWT or session). The username used for database queries must come from the token, not from the request.

---

## High Security Issues

### 4. Sensitive Data Leaked in Error Responses

**File**: `backend/app/main.py` (lines 156–159)  
**Severity**: High

When the OpenRouter call fails, the full upstream response object is returned to the client:

```python
raise HTTPException(
    status_code=502,
    detail={
        "error": str(exc),
        "openrouter_response": response_data,  # may contain prompt context or internal data
    },
)
```

**Fix**: Log the full response server-side; return only a generic error message to the client.

---

### 5. No Rate Limiting

**File**: `backend/app/main.py`  
**Severity**: High

There is no rate limiting on any endpoint, especially `POST /api/ai/chat`. An attacker (or malfunctioning client) can issue unlimited requests, exhausting OpenRouter quota and creating unexpected costs.

**Fix**: Add `slowapi` or equivalent FastAPI middleware to rate-limit per IP or per user.

---

### 6. No Input Length Validation

**Files**: `backend/app/main.py`, `frontend/src/components/KanbanCard.tsx`  
**Severity**: Medium

Card titles and details have no maximum length constraint — neither in the Pydantic schemas nor in the frontend form inputs. Very large strings could degrade performance or cause issues in the AI prompt (which includes the full board JSON).

**Fix**: Add `max_length` constraints to Pydantic schema fields and `maxLength` attributes to `<input>` / `<textarea>` elements.

---

## Bugs and Correctness Issues

### 7. Optimistic UI Update Can Diverge from Server State

**File**: `frontend/src/components/AuthGate.tsx` (lines 78–91)  
**Severity**: Medium

`handleBoardChange()` updates React state immediately (optimistic update), then fires the save request asynchronously:

```typescript
setBoard(nextBoard);          // instant local update
saveBoard(VALID_USERNAME, nextBoard)
  .then((saved) => {
    setBoard(saved);          // may conflict if user acted again
  });
```

If the user performs a second action before the first save resolves, or if the save fails, the in-memory state and the stored state diverge silently.

**Fix**: Disable interactions while a save is in flight, or implement a proper queue/conflict-resolution strategy.

---

### 8. Potential `KeyError` When Inserting Board

**File**: `backend/app/db.py` (line 191)  
**Severity**: Medium

`_insert_board()` iterates over `column.cardIds` and accesses `board.cards[card_id]` without checking if the card exists:

```python
card = board.cards[card_id]  # KeyError if AI omits a card that a column references
```

This can crash the endpoint with an unhelpful 500 error when an AI-generated board has inconsistent references.

**Fix**: Raise a `ValueError` with a descriptive message before attempting the insert, or validate consistency in `_apply_ai_result`.

---

### 9. Ambiguous AI Response Parsing Logic

**File**: `backend/app/main.py` (lines 54–71)  
**Severity**: Medium

`_parse_ai_content()` has two overlapping branches: one that wraps a raw `BoardData` JSON payload (no `reply` field) and one that parses a proper `AIChatResult`. The conditions can be confusing and it is unclear which branch takes precedence when both match. A comment explaining the decision tree would help, and the logic could be simplified by always requiring `AIChatResult` format.

---

### 10. Auth State Persists Indefinitely

**File**: `frontend/src/components/AuthGate.tsx` (line 29)  
**Severity**: Low

Login state is persisted in `localStorage` with no expiry:

```typescript
localStorage.setItem("pm-authenticated", "true");
```

Once logged in, the session never expires on that device. Combined with the client-side-only auth model, this means a shared or compromised device gives permanent access.

**Fix**: After implementing server-side auth, use HTTP-only cookies with an expiry. Remove the `localStorage` approach.

---

## Code Quality Issues

### 11. Seed Data Duplicated in Two Places

**Files**: `backend/app/db.py` (lines 100–150) and `frontend/src/lib/kanban.ts` (lines 18–72)  
**Severity**: Medium

Default board data is defined independently in both backend and frontend. If the data diverges, the UX is inconsistent (first load shows different data depending on whether the board was seeded by the backend or initialised client-side).

**Fix**: Define seed data in a single JSON file; have the backend load it at startup and the frontend load it from the API on first access only.

---

### 12. Magic Strings Scattered Throughout

**Severity**: Low

| Value | Location |
|-------|----------|
| `"openai/gpt-oss-120b"` | `main.py` line 19 |
| `"data.db"` | `db.py` line 10 |
| `"pm-authenticated"` | `AuthGate.tsx` line 9 |
| `"user"` / `"password"` | `AuthGate.tsx` lines 10–11 |

**Fix**: Consolidate into a config module (`config.py`) or a constants file. At minimum, the model name and DB path should come from environment variables so they can be changed without code edits.

---

### 13. Validation Duplicated Between `main.py` and `db.py`

**Files**: `backend/app/main.py` (lines 103–111), `backend/app/db.py` (line 191)  
**Severity**: Low

The check that all `cardIds` referenced by columns actually exist in `cards` is performed in two places. If either check is updated without updating the other, the behaviour diverges.

**Fix**: Centralise this validation in a single schema or utility function.

---

### 14. No Runtime Type Validation on API Responses (Frontend)

**File**: `frontend/src/lib/api.ts`  
**Severity**: Low

API responses are cast to TypeScript types with `as`:

```typescript
const errorBody = (await response.json()) as ApiError;
```

TypeScript types are erased at runtime, so if the server returns an unexpected shape the cast silently succeeds and downstream code fails unpredictably.

**Fix**: Use a schema validation library such as [zod](https://zod.dev) to parse and validate API responses at runtime.

---

### 15. Inconsistent Error Handling Across the Frontend

**Files**: `AuthGate.tsx`, `api.ts`, `ChatSidebar.tsx`  
**Severity**: Low

- `api.ts` line 33: silently swallows JSON parse errors on failed responses.
- `ChatSidebar.tsx`: error state is set on failure but never cleared on the next successful request.
- `AuthGate.tsx` line 44: all errors are collapsed into a single generic message.

**Fix**: Adopt a consistent error handling pattern — log errors to the console in development, show user-friendly messages, and clear error state when the operation succeeds.

---

## Performance Issues

### 16. Full Board Delete-and-Reinsert on Every Save

**File**: `backend/app/db.py` (lines 251–261)  
**Severity**: Low

`save_board()` deletes all rows for a user and inserts the entire board fresh on every save, even for a single card title change. For large boards, this is wasteful and loses the ability to track incremental history.

**Fix**: For now this is acceptable at MVP scale. For production, move to partial UPDATE statements.

---

### 17. Full Board JSON Sent with Every AI Request

**File**: `backend/app/main.py` (line 83)  
**Severity**: Low

```python
"content": "Current board JSON:\n" + json.dumps(board.model_dump()),
```

As the board grows, each AI request becomes larger and more expensive. The model context window also limits how large a board can be handled.

**Fix**: Send a compact summary of the board (column names + card counts) unless the user's request requires card-level detail.

---

### 18. Two Separate Database Queries to Load a Board

**File**: `backend/app/db.py` (lines 216–248)  
**Severity**: Low

`get_board()` issues one query for columns and another for cards. This can be combined into a single JOIN query.

---

## Test Coverage Gaps

### 19. No Negative / Error Path Tests for the Backend API

**File**: `backend/tests/test_api.py`

Missing test cases:
- Invalid board data (orphaned card references, duplicate IDs).
- HTTP error responses (404 for unknown user, 422 for malformed request body).
- AI endpoint when OpenRouter returns an error.
- Database failure simulation.

---

### 20. Minimal Frontend Unit Tests

**Directory**: `frontend/src/components/`

Missing:
- Tests for `KanbanCard` (title editing, drag state).
- Tests for `NewCardForm` (validation, submission).
- Tests for API error handling paths in `AuthGate`.
- Tests for `moveCard` edge cases in `kanban.ts`.

---

### 21. Playwright E2E Config Exists but No Tests

**File**: `frontend/playwright.config.ts`

The Playwright configuration is present but the `tests/` directory has no spec files. Either remove the dependency and config, or add at minimum a happy-path smoke test.

---

### 22. AI Response Parsing Not Thoroughly Tested

**File**: `backend/tests/test_ai_schema.py`

Missing:
- Malformed JSON from the model.
- Response where `board` is present but a required field is missing.
- Response exceeding a reasonable size limit.

---

## Dependency and Configuration Issues

### 23. Backend Dependencies Not Version-Pinned

**File**: `backend/requirements.txt`

Dependencies use open lower bounds (`>=0.110`) with no upper bound. A future breaking release of any library could silently break the app.

**Fix**: Pin to exact versions (`==`) or use a lock file (`uv lock`).

---

### 24. Missing `OPENROUTER_API_KEY` Startup Validation

**File**: `backend/app/main.py` (lines 27–29)

The API key is only checked when the first AI request is made. If the key is missing, the app starts fine but fails at runtime.

**Fix**: Add an `@app.on_event("startup")` check (or use FastAPI's lifespan context) that raises an error at boot if required env vars are absent.

---

### 25. No Security-Related HTTP Headers

**File**: `backend/app/main.py`

The app does not set standard security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`). While these matter more for user-facing HTML, they should be added when the frontend is served by FastAPI.

**Fix**: Add a middleware that sets appropriate security headers on all responses.

---

## Architectural Issues

### 26. Client-Only Auth with No Server-Side Session Management

**Severity**: Critical architectural gap

The backend treats every `username` parameter as trusted. There is no session, no token, and no way for the backend to distinguish legitimate users from anyone who knows a valid username. This is the root cause of issues #2 and #3 above.

**Recommended architecture**:
1. `POST /api/auth/login` — validates credentials server-side, returns a signed JWT.
2. All subsequent requests include the JWT in the `Authorization: Bearer <token>` header.
3. A FastAPI dependency extracts and verifies the token; routes use the verified identity, not a request param.

---

### 27. Python Serves Static Frontend Files

**File**: `backend/app/main.py` (lines 183–184)

```python
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

FastAPI/Uvicorn is efficient for API traffic but is not optimised for serving large numbers of static assets. For production, place nginx in front to serve static files directly and proxy only `/api/*` to Uvicorn.

---

### 28. SQLite Not Suitable for Multi-Instance Deployment

**File**: `backend/app/db.py` (line 10)

SQLite is stored on the container filesystem. Running multiple replicas would give each container its own database. This is acceptable for a single-instance demo but must be replaced with a networked database (e.g., PostgreSQL) before any scaled deployment.

---

### 29. No API Versioning

All endpoints are under `/api/*` with no version prefix. Any breaking API change will immediately break all clients.

**Fix**: Introduce a `/api/v1/*` prefix now, while the API surface is small.

---

## Summary

| Category | Severity | Count |
|----------|----------|-------|
| Security | Critical | 2 |
| Security | High | 2 |
| Security | Medium | 1 |
| Bugs | Medium | 3 |
| Bugs | Low | 1 |
| Code Quality | Medium | 1 |
| Code Quality | Low | 4 |
| Performance | Low | 3 |
| Testing | Medium | 4 |
| Config | Medium | 2 |
| Config | Low | 1 |
| Architecture | Critical | 1 |
| Architecture | Low | 3 |

---

## Recommended Improvements by Priority

### Immediate (Before Any External Access)

1. Implement `POST /api/auth/login` with password hashing (bcrypt via `passlib`).
2. Add JWT verification dependency to all API routes.
3. Add rate limiting to the AI chat endpoint.

### Short-Term (Next Sprint)

6. Remove hardcoded credentials from `AuthGate.tsx`.
7. Add startup validation for required environment variables.
8. Sanitise error responses — never return upstream API data to clients.
9. Add `max_length` constraints to Pydantic schemas and frontend inputs.
10. Fix optimistic UI update to handle save failures gracefully.

### Medium-Term (Code Health)

11. Consolidate seed data to a single source.
12. Replace magic strings with config/constants.
13. Add zod validation to frontend API response parsing.
14. Standardise error handling across the frontend.
15. Write negative-path tests for the backend API.
16. Add at least one Playwright E2E smoke test or remove the dependency.

### Long-Term (Production Readiness)

17. Move static file serving to nginx.
18. Replace SQLite with PostgreSQL.
19. Add structured request logging and an audit trail.
20. Add API versioning (`/api/v1/*`).
21. Add security response headers middleware.
22. Pin all backend dependency versions.
