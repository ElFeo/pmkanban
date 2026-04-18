# Code Review — April 17, 2026

> Reviewer: Claude Sonnet 4.6 (the AI that never sleeps and never pretends not to see your hardcoded secrets)

---

## Executive Summary

A clean, well-structured Kanban app with FastAPI + Next.js. The architecture is sensible, the code is readable, and someone clearly thought about separation of concerns. That said, there are a handful of issues ranging from "fix this before you show it to anyone" to "fine for a demo, but don't call it production."

---

## CRITICAL Issues (Fix These Now)

### 1. Exposed API Key in `.env`
**File:** `.env`

The OpenRouter API key is sitting right there in plaintext. If this repo has ever been pushed to a remote, that key is compromised. Rotate it immediately on your OpenRouter account.

- Add `.env` to `.gitignore`
- Use `.env.example` with placeholder values for documentation
- Consider `git filter-branch` or BFG Repo Cleaner to purge from history

### 2. Default JWT Secret
**File:** `backend/app/auth.py:11`

```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
```

The fact that it says "change-in-production" in the default means someone will forget to change it in production. Fail loudly if `JWT_SECRET_KEY` isn't set instead of silently accepting a known string.

### 3. Non-existent AI Test Endpoint
**File:** `backend/tests/test_ai.py:15`

```python
response = client.post("/api/ai/test", json={"prompt": "2+2"})
```

This endpoint does not exist in `main.py`. This test either always fails silently or gets skipped. Either implement the endpoint or delete the test — a test that never runs is worse than no test at all.

---

## HIGH Severity

### 4. Default Credentials
**File:** `backend/app/auth.py:20–21`

Hardcoded fallback to `username="user"`, `password="password"`. Fine for a demo. Embarrassing in production. Require explicit credential configuration and fail fast if not provided.

### 5. Rate Limiting Broken Behind a Reverse Proxy
**File:** `backend/app/main.py:60`

```python
client_ip = request.client.host if request.client else "unknown"
```

Behind any reverse proxy (nginx, Caddy, AWS ALB), all requests will appear to come from the same IP. Your rate limiter will either throttle every user simultaneously or none of them. Check `X-Forwarded-For` and configure trusted proxy handling.

### 6. SQLite Database Not Persisted in Docker
**File:** `docker-compose.yml`

The SQLite database lives inside the container with no volume mount. Every `docker compose down` is a data wipe. Add:

```yaml
volumes:
  - pm-data:/app/data.db
```

---

## MEDIUM Severity

### 7. HTTPException `detail` Passed as Dict
**File:** `backend/app/main.py:249–252`

```python
raise HTTPException(status_code=502, detail={"error": str(exc)})
```

FastAPI's `detail` parameter expects a string (or serializable type, but this can cause unexpected behavior). Use `detail=str(exc)`.

### 8. Unbounded AI Chat History
**File:** `backend/app/main.py` — `AIChatRequest`

No limit on how many messages can be sent in `history`. A long-running session accumulates an ever-growing payload sent to OpenRouter on every message. Add a cap (e.g., 20 messages).

### 9. No `min_length` Validators on String Fields
**File:** `backend/app/schemas.py`

`title`, `content` fields define `max_length` but allow empty strings. Empty card titles are technically valid per the schema. Add `min_length=1` to title fields.

### 10. Token Stored in Module-Level Variable (Non-Persistent)
**File:** `frontend/src/lib/api.ts:24`

```typescript
let _authToken: string | null = null;
```

Works fine but tokens don't survive page refreshes — the component has to restore from `sessionStorage` on every mount. Consider moving auth state into a context with proper initialization.

### 11. No `AbortController` on Fetch Requests
**File:** `frontend/src/lib/api.ts`

No request cancellation. If a user navigates away mid-fetch, the request completes and tries to update unmounted component state. Add `AbortController` to all fetch calls.

### 12. Auto-scroll Missing in Chat Sidebar
**File:** `frontend/src/components/ChatSidebar.tsx`

New assistant messages appear below the fold with no auto-scroll. Users will miss responses. Add a `useRef` + `useEffect` to scroll to bottom on new messages.

### 13. Broken `useMemo` Optimization
**File:** `frontend/src/components/KanbanBoard.tsx:37`

```typescript
const cardsById = useMemo(() => localBoard.cards, [localBoard.cards]);
```

The dependency is the `cards` object reference, which changes every render. This memoization does nothing. Fix or remove.

### 14. No HEALTHCHECK in Dockerfile

No health check defined. Docker and orchestrators have no way to detect if the app is up or stuck.

```dockerfile
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1
```

### 15. No CORS Middleware

If the frontend and backend ever run on different origins (development, staging), there's no CORS configuration. Add `CORSMiddleware` with appropriate allowed origins.

---

## LOW Severity

### 16. No Confirmation on Card Delete
**File:** `frontend/src/components/KanbanCard.tsx:44`

"Remove" deletes immediately with no confirmation or undo. Fine for a demo. Mildly infuriating for real users.

### 17. No `maxLength` on Frontend Inputs
**File:** `frontend/src/components/NewCardForm.tsx`

Backend enforces limits via Pydantic, but the frontend inputs have no `maxLength` attribute. Users type 5,000 characters and only find out at submission. Add `maxLength` to form inputs.

### 18. Column `position` Field Unused
**File:** `backend/app/db.py`

The `position` column exists in the database schema and is populated, but queries don't use it for ordering — the insertion order handles that. Either use it explicitly in ORDER BY clauses or drop it.

### 19. Message Keys Using Array Index
**File:** `frontend/src/components/ChatSidebar.tsx:61`

```typescript
key={`${message.role}-${index}`}
```

Index-based keys are fragile if the list is ever reordered or filtered. Use a stable ID (timestamp or UUID per message).

### 20. ID Collision Risk in `createId`
**File:** `frontend/src/lib/kanban.ts:164–168`

```typescript
const randomPart = Math.random().toString(36).slice(2, 8);
const timePart = Date.now().toString(36);
```

Two simultaneous card creations in the same millisecond could collide. Very unlikely, but use `crypto.randomUUID()` for correctness.

---

## What's Actually Good (Yes, Really)

- **Architecture is clean.** Single Docker container, FastAPI serving static files, clear data flow. Not overengineered.
- **Auth is properly enforced.** JWT on protected routes, `HTTPBearer`, proper 401 responses with `WWW-Authenticate` headers.
- **Security headers middleware is implemented.** Someone actually thought about this.
- **Database tests use real SQLite with `tmp_path`.** No mocking the database — the codebase explicitly rejects that pattern. The tests that exist are trustworthy.
- **AI schema validation is solid.** `test_ai_schema.py` covers malformed JSON, missing fields, and bad board structure. The `_parse_ai_content` / `_apply_ai_result` separation is sensible.
- **Pure functions in `kanban.ts`.** Board manipulation is testable and side-effect-free.
- **Rate limiting on the AI endpoint.** Someone remembered this is expensive to call.

---

## Priority Action Items

| Priority | Action |
|----------|--------|
| Immediate | Rotate the OpenRouter API key |
| Immediate | Add `.env` to `.gitignore`, scrub from git history |
| Immediate | Fix or delete `test_ai.py` — it tests a phantom endpoint |
| Short-term | Require `JWT_SECRET_KEY` env var, no fallback default |
| Short-term | Add SQLite volume mount to `docker-compose.yml` |
| Short-term | Fix rate limiting for reverse proxy (`X-Forwarded-For`) |
| Short-term | Add auto-scroll to `ChatSidebar.tsx` |
| Short-term | Add `HEALTHCHECK` to `Dockerfile` |
| Medium-term | Add `AbortController` to all fetch calls |
| Medium-term | Cap AI chat history length |
| Medium-term | Fix the broken `useMemo` in `KanbanBoard.tsx` |

---

*Generated by Claude Sonnet 4.6 on 2026-04-17. The AI takes no responsibility for issues introduced after this review, but reserves the right to say "I told you so."*
