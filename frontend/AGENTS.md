# Frontend overview

## Stack

- Next.js App Router (Next 16)
- React 19
- Tailwind CSS v4 with CSS variables in globals
- Drag and drop via @dnd-kit
- Vitest + Testing Library for unit/integration tests
- Playwright configured but not required for this project scope

## Entry points

- src/app/layout.tsx: App shell, font setup (Space Grotesk + Manrope), global styles import
- src/app/page.tsx: Renders the Kanban board
- src/app/globals.css: Theme tokens (colors, shadows), Tailwind setup, base styles

## Core UI components

- src/components/KanbanBoard.tsx
  - Owns board state (columns + cards) using `initialData`
  - Handles drag-and-drop with `@dnd-kit/core` and `@dnd-kit/sortable`
  - Supports renaming columns, adding cards, deleting cards
  - Uses `DragOverlay` with `KanbanCardPreview`

- src/components/KanbanColumn.tsx
  - Column container with droppable area
  - Renders column title input and cards
  - Wraps cards in `SortableContext`
  - Hosts `NewCardForm`

- src/components/KanbanCard.tsx
  - Sortable card item with drag listeners
  - Delete button calls parent handler

- src/components/KanbanCardPreview.tsx
  - Visual-only preview used for drag overlay

- src/components/NewCardForm.tsx
  - Toggleable form to add a card
  - Simple local state and validation

## Board logic

- src/lib/kanban.ts
  - Data types: `Card`, `Column`, `BoardData`
  - `initialData` seed for the demo board
  - `moveCard` handles reordering and cross-column moves
  - `createId` generates card ids

## Tests

- src/components/KanbanBoard.test.tsx
  - Renders columns, renames a column, adds/removes a card

- src/lib/kanban.test.ts
  - Covers `moveCard` behavior (reorder, move columns, drop to end)

## Scripts

- `npm run dev` starts Next.js dev server
- `npm run build` builds Next.js
- `npm run test:unit` runs Vitest
