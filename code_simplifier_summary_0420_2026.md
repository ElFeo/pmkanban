# Code Simplifier Summary — April 20, 2026

## Overview

Full codebase simplification pass on the Kanban PM app. No functionality, API contracts, or test behavior changed.

**Verification:** 142 backend tests passed, 52 frontend unit tests passed, TypeScript source files clean.

---

## Backend (`backend/app/`)

### `main.py`
- Added `_forbidden()` and `_not_found()` helpers replacing ~15 duplicated `HTTPException(...)` blocks
- Cleaned up `_check_ai_rate_limit` dict churn
- Simplified `_apply_ai_result` missing-cards check
- Dropped comment section headers

### `db.py`
- Removed dead code: `get_first_board_id`, `get_board`, `save_board`
- Consolidated migration blocks
- Removed unused `username` param from `_get_or_create_default_board`
- Hoisted `date` import
- Simplified `get_board_stats`, `get_my_tasks`, `get_checklist` via `dict(row)` patterns

---

## Frontend (`frontend/src/`)

### `lib/api.ts`
- New `jsonHeaders()`, `errorMessage()`, `ensureOk()` helpers eliminate boilerplate across all request functions
- Unified error-parsing path

### `components/KanbanBoard.tsx`
- Introduced `SOON_MS` constant
- Grouped filter state hooks
- Removed redundant `cardsById` memo
- Combined `allLabels`/`allAssignees` into one `useMemo`
- Simplified `handleDeleteCard` / `handleDuplicateCard`
- Dropped unused imports

### `components/KanbanCard.tsx`
- Added `SOON_MS`, `DueStatus`, `DUE_STATUS_CLASS`
- Compute `dueStatus` once instead of 4 times

### `components/MyTasksPanel.tsx`
- Replaced nested ternary with `DUE_CLASS` record lookup
- Compute due statuses once

### `components/CardEditModal.tsx`
- Generic `updateField<K>(key, value)` helper replaces 7 inline `setFormState((p) => ({ ...p, … }))` calls

### `components/NewCardForm.tsx`
- Same `updateField` pattern replacing 5 inline state updaters

---

## Files Left Unchanged

- `CardChecklist.tsx`, `CardCommentsPanel.tsx` — structurally similar but already clean; a shared hook would hurt clarity
- `BoardSelector.tsx`, `UserProfileModal.tsx`, `AuthGate.tsx` — reviewed and consistent with project style
