# Code Review: Project Management MVP

## Overview

The project is well-structured with clear separation between frontend (NextJS 16) and backend (FastAPI). The architecture is appropriate for the MVP scope. Overall code quality is good with clean patterns and consistent styling.

---

## Critical Issues

### 1. Hardcoded JWT Secret
**File:** `backend/app/auth.py:11`
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
```
**Severity:** Critical

The default secret is a security risk. Any deployment with this default would be vulnerable to token forgery. All tokens signed with the default key could be forged by attackers.

**Recommendation:** Remove the default fallback and require the secret to be set via environment variable, or generate a secure random key on first startup if none is provided.

---

### 2. Session Storage Vulnerable to XSS
**File:** `frontend/src/components/AuthGate.tsx:37-38`

JWT tokens stored in `sessionStorage` can be stolen by any XSS attack:
```typescript
const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
```

**Recommendation:** Consider using `httpOnly` cookies for token storage in production. The current approach is acceptable for MVP but should be noted as a limitation.

---

### 3. Rate Limiter Not Persistent
**File:** `backend/app/main.py:53-54`
```python
_ai_request_log: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()
```

The in-memory rate limiter resets on server restart. An attacker can bypass rate limits by waiting for restart or triggering a restart.

**Recommendation:** For production, use a persistent store (Redis, database) for rate limit tracking.

---

### 4. Missing `/api/ai/test` Endpoint
**Severity:** Medium

Backend tests reference `POST /api/ai/test` but this endpoint is not implemented in `main.py`. This creates a gap between documented API and implementation.

**Recommendation:** Either implement the endpoint or remove references from tests.

---

## Medium Issues

### 5. No Backend URL Configuration
**File:** `frontend/src/lib/api.ts`

The frontend assumes the API is served from the same origin (root `/`). If the backend URL needs to change, it requires code modification.

**Recommendation:** Add an environment variable for the API base URL for flexibility.

---

### 6. No Debouncing on Board Saves
**File:** `frontend/src/components/AuthGate.tsx:100-116`

Every card move, rename, add, or delete triggers an API call:
```typescript
const handleBoardChange = (nextBoard: BoardData) => {
  // ... immediately calls saveBoard
  saveBoard(loggedInUsername!, nextBoard)
```

Rapid user actions will flood the server with requests.

**Recommendation:** Add debouncing (e.g., 500ms delay) before triggering API calls.

---

### 7. No Card Editing Feature
**Files:** `frontend/src/components/KanbanCard.tsx`, `frontend/src/components/KanbanBoard.tsx`

Users can add and delete cards but cannot edit existing card content. This is a significant UX gap for a Kanban app.

**Recommendation:** Add inline editing or a modal to edit card title and details.

---

### 8. No Toast/Notification System
**File:** `frontend/src/components/AuthGate.tsx:169-175`

Errors are displayed inline in a simple div. For better UX, implement a toast notification system.

**Recommendation:** Add a toast/notification library (e.g., `react-hot-toast`) for user feedback.

---

## Minor Issues

### 9. Redundant State in AuthGate
**File:** `frontend/src/components/AuthGate.tsx`

The component maintains `board`, `loggedInUsername`, `chatHistory`, etc. Some state could be consolidated or derived.

**Recommendation:** Consider using React Context or a simpler state management approach.

---

### 10. Column Rename Has No Save Indicator
**File:** `frontend/src/components/KanbanBoard.tsx:66-73`

Column renaming saves immediately but shows no visual feedback, unlike board saves which display "Saving...".

**Recommendation:** Add a visual indicator during column rename saves.

---

### 11. AI Response Schema Strict Mode
**File:** `backend/app/main.py:155`
```python
return {"name": "kanban_response", "schema": schema, "strict": True}
```

OpenRouter's `gpt-oss-120b` model may not reliably return strict JSON schema-conformant responses.

**Recommendation:** Add fallback parsing logic and more robust error handling for malformed AI responses.

---

### 12. CORS Not Configured
**File:** `backend/app/main.py`

No CORS middleware is present. This works for Docker (same-origin) but limits local development if frontend runs separately.

**Recommendation:** Add CORS middleware if supporting separate frontend/backend development.

---

### 13. Duplicate Seed Data
**Files:** `frontend/src/lib/kanban.ts:18-72`, `backend/app/db.py:100-150`

Seed data is defined twice with identical content. Changes to one won't reflect in the other.

**Recommendation:** Consider sharing seed data or generating it programmatically from a single source.

---

## Code Quality Positives

- Clean separation of concerns in `lib/` utilities
- Good use of TypeScript types throughout frontend
- Proper error boundaries and API error handling
- Consistent use of CSS variables for theming
- Good test coverage for core `moveCard` logic
- Security headers middleware is implemented correctly
- Database schema includes proper indexes
- Foreign key constraints enabled for data integrity
- JWT token includes proper expiration

---

## Testing Assessment

**Frontend (Vitest):**
- Good coverage of `moveCard` logic
- AuthGate tests cover login flow and session restoration
- ChatSidebar tests cover message sending

**Backend (pytest):**
- Auth tests cover credential validation
- Board CRUD tests include authorization checks
- AI schema tests validate response parsing

**E2E (Playwright):**
- Kanban workflow tests configured

**Recommendation:** Add integration tests for the full AI chat flow and edge cases in board operations.

---

## Recommendations Summary

| Priority | Issue | Action |
|----------|-------|--------|
| High | Hardcoded JWT secret | Require env var or generate secure key |
| High | Rate limiter not persistent | Use Redis/database for production |
| Medium | Missing `/api/ai/test` endpoint | Implement or remove test references |
| Medium | No card editing | Add edit functionality |
| Medium | No debouncing | Add debounce for board saves |
| Low | Session storage XSS risk | Document as limitation, plan httpOnly cookies |
| Low | Duplicate seed data | Consolidate to single source |
| Low | Column rename no indicator | Add save feedback |

---

## Conclusion

The codebase demonstrates solid fundamentals with good structure and clean code. For MVP, the critical security issues (JWT secret) should be addressed before any deployment. The medium-priority items (card editing, debouncing) would significantly improve UX. Overall, this is a well-implemented MVP that provides a good foundation for future development.
