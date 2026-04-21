"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  closestCorners,
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { arrayMove, horizontalListSortingStrategy, SortableContext } from "@dnd-kit/sortable";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { KanbanColumn } from "@/components/KanbanColumn";
import { createId, moveCard, type BoardData, type Card, type Priority } from "@/lib/kanban";

const SOON_MS = 3 * 24 * 60 * 60 * 1000;

type KanbanBoardProps = {
  board: BoardData;
  boardId: string;
  currentUser: string;
  onBoardChange: (board: BoardData) => void;
};

export const KanbanBoard = ({ board, boardId, currentUser, onBoardChange }: KanbanBoardProps) => {
  const [localBoard, setLocalBoard] = useState<BoardData>(() => board);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [activeColumnId, setActiveColumnId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [filterAssignee, setFilterAssignee] = useState("");
  const [filterDue, setFilterDue] = useState("");
  const [filterLabel, setFilterLabel] = useState("");
  const [hideArchived, setHideArchived] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLocalBoard(board);
  }, [board]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const updateBoard = (nextBoard: BoardData) => {
    setLocalBoard(nextBoard);
    onBoardChange(nextBoard);
  };

  const columnIds = useMemo(() => localBoard.columns.map((c) => c.id), [localBoard.columns]);

  const handleDragStart = (event: DragStartEvent) => {
    const id = event.active.id as string;
    if (columnIds.includes(id)) {
      setActiveColumnId(id);
    } else {
      setActiveCardId(id);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);
    setActiveColumnId(null);

    if (!over || active.id === over.id) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    // Column reorder
    if (columnIds.includes(activeId) && columnIds.includes(overId)) {
      const oldIndex = columnIds.indexOf(activeId);
      const newIndex = columnIds.indexOf(overId);
      updateBoard({
        ...localBoard,
        columns: arrayMove(localBoard.columns, oldIndex, newIndex),
      });
      return;
    }

    // Card move
    if (!columnIds.includes(activeId)) {
      updateBoard({
        ...localBoard,
        columns: moveCard(localBoard.columns, activeId, overId),
      });
    }
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    updateBoard({
      ...localBoard,
      columns: localBoard.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    });
  };

  const handleAddCard = (
    columnId: string,
    title: string,
    details: string,
    priority?: Priority | null,
    due_date?: string | null,
    labels?: string[]
  ) => {
    const id = createId("card");
    updateBoard({
      ...localBoard,
      cards: {
        ...localBoard.cards,
        [id]: {
          id,
          title,
          details: details || "",
          priority: priority ?? null,
          due_date: due_date ?? null,
          labels: labels ?? [],
        },
      },
      columns: localBoard.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    });
  };

  const handleEditCard = (_columnId: string, updated: Card) => {
    updateBoard({
      ...localBoard,
      cards: { ...localBoard.cards, [updated.id]: updated },
    });
  };

  const handleAddColumn = () => {
    const id = createId("col");
    updateBoard({
      ...localBoard,
      columns: [...localBoard.columns, { id, title: "New Column", cardIds: [] }],
    });
  };

  const handleDeleteColumn = (columnId: string) => {
    const col = localBoard.columns.find((c) => c.id === columnId);
    if (!col) return;
    const remainingCards = Object.fromEntries(
      Object.entries(localBoard.cards).filter(([id]) => !col.cardIds.includes(id))
    );
    updateBoard({
      ...localBoard,
      columns: localBoard.columns.filter((c) => c.id !== columnId),
      cards: remainingCards,
    });
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    const { [cardId]: _removed, ...remainingCards } = localBoard.cards;
    updateBoard({
      ...localBoard,
      cards: remainingCards,
      columns: localBoard.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) }
          : column
      ),
    });
  };

  const handleDuplicateCard = (columnId: string, cardId: string) => {
    const src = localBoard.cards[cardId];
    const col = localBoard.columns.find((c) => c.id === columnId);
    if (!src || !col) return;
    const newId = createId("card");
    const clone: Card = { ...src, id: newId, title: `${src.title} (copy)` };
    const insertAt = col.cardIds.indexOf(cardId) + 1;
    const newCardIds = [
      ...col.cardIds.slice(0, insertAt),
      newId,
      ...col.cardIds.slice(insertAt),
    ];
    updateBoard({
      ...localBoard,
      cards: { ...localBoard.cards, [newId]: clone },
      columns: localBoard.columns.map((c) =>
        c.id === columnId ? { ...c, cardIds: newCardIds } : c
      ),
    });
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string);
        if (parsed.columns && parsed.cards) {
          updateBoard(parsed as BoardData);
        }
      } catch {
        // Silently ignore invalid JSON.
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(localBoard, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "board-export.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const activeCard = activeCardId ? localBoard.cards[activeCardId] : null;

  const { allLabels, allAssignees } = useMemo(() => {
    const labels = new Set<string>();
    const assignees = new Set<string>();
    for (const card of Object.values(localBoard.cards)) {
      card.labels?.forEach((l) => labels.add(l));
      if (card.assignee) assignees.add(card.assignee);
    }
    return {
      allLabels: Array.from(labels).sort(),
      allAssignees: Array.from(assignees).sort(),
    };
  }, [localBoard.cards]);

  const hasActiveFilter = !!(
    searchQuery.trim() ||
    filterPriority ||
    filterAssignee ||
    filterDue ||
    filterLabel ||
    hideArchived
  );

  const clearFilters = () => {
    setSearchQuery("");
    setFilterPriority("");
    setFilterAssignee("");
    setFilterDue("");
    setFilterLabel("");
    setHideArchived(false);
  };

  const matchesSearch = useCallback(
    (card: Card): boolean => {
      if (hideArchived && card.archived) return false;
      if (filterPriority && card.priority !== filterPriority) return false;
      if (filterLabel && !(card.labels ?? []).includes(filterLabel)) return false;
      if (filterAssignee && card.assignee !== filterAssignee) return false;

      if (filterDue) {
        const dueMs = card.due_date ? new Date(card.due_date).getTime() : null;
        if (filterDue === "overdue" && (dueMs === null || dueMs >= Date.now())) return false;
        if (filterDue === "soon") {
          const diff = dueMs !== null ? dueMs - Date.now() : null;
          if (diff === null || diff < 0 || diff >= SOON_MS) return false;
        }
        if (filterDue === "none" && card.due_date) return false;
      }

      const q = searchQuery.trim().toLowerCase();
      if (!q) return true;
      return (
        card.title.toLowerCase().includes(q) ||
        (card.details ?? "").toLowerCase().includes(q) ||
        (card.labels ?? []).some((l) => l.toLowerCase().includes(q))
      );
    },
    [searchQuery, filterPriority, filterLabel, filterAssignee, filterDue, hideArchived]
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {localBoard.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
            <button
              type="button"
              onClick={handleAddColumn}
              className="rounded-full border border-dashed border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)] transition hover:border-[var(--primary-blue)]"
            >
              + Add column
            </button>
            <div className="ml-auto flex gap-2">
              <label
                className="cursor-pointer rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
                aria-label="Import board from JSON"
              >
                Import JSON
                <input
                  type="file"
                  accept=".json"
                  onChange={handleImport}
                  className="hidden"
                />
              </label>
              <button
                type="button"
                onClick={handleExport}
                aria-label="Export board as JSON"
                className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
              >
                Export JSON
              </button>
            </div>
          </div>

          {/* Filter bar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <input
                ref={searchRef}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search cards… (Ctrl+K)"
                aria-label="Search cards"
                className="w-52 rounded-xl border border-[var(--stroke)] bg-white px-4 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              />
            </div>
            <select
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              aria-label="Filter by priority"
              className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
            >
              <option value="">All priorities</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            {allLabels.length > 0 && (
              <select
                value={filterLabel}
                onChange={(e) => setFilterLabel(e.target.value)}
                aria-label="Filter by label"
                className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
              >
                <option value="">All labels</option>
                {allLabels.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            )}
            {allAssignees.length > 0 && (
              <select
                value={filterAssignee}
                onChange={(e) => setFilterAssignee(e.target.value)}
                aria-label="Filter by assignee"
                className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
              >
                <option value="">All assignees</option>
                {allAssignees.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            )}
            <select
              value={filterDue}
              onChange={(e) => setFilterDue(e.target.value)}
              aria-label="Filter by due date"
              className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
            >
              <option value="">All due dates</option>
              <option value="overdue">Overdue</option>
              <option value="soon">Due soon</option>
              <option value="none">No due date</option>
            </select>
            <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-[var(--gray-text)]">
              <input
                type="checkbox"
                checked={hideArchived}
                onChange={(e) => setHideArchived(e.target.checked)}
                className="h-4 w-4 accent-[var(--secondary-purple)]"
              />
              Hide archived
            </label>
            {hasActiveFilter && (
              <button
                type="button"
                onClick={clearFilters}
                className="rounded-full border border-[var(--stroke)] px-3 py-1.5 text-xs font-semibold text-[var(--gray-text)] transition hover:text-red-500"
              >
                Clear filters
              </button>
            )}
          </div>
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={columnIds} strategy={horizontalListSortingStrategy}>
            <section className="grid gap-6" style={{ gridTemplateColumns: `repeat(${localBoard.columns.length}, minmax(240px, 1fr))` }}>
              {localBoard.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds
                    .map((cardId) => localBoard.cards[cardId])
                    .filter(Boolean)
                    .filter(matchesSearch)}
                  canDelete={localBoard.columns.length > 1}
                  boardId={boardId}
                  currentUser={currentUser}
                  onRename={handleRenameColumn}
                  onDelete={handleDeleteColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                  onEditCard={handleEditCard}
                  onDuplicateCard={handleDuplicateCard}
                  isDragging={activeColumnId === column.id}
                />
              ))}
            </section>
          </SortableContext>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : activeColumnId ? (
              <div className="w-[280px] rounded-3xl border-2 border-dashed border-[var(--accent-yellow)] bg-white/70 p-4 text-sm font-semibold text-[var(--navy-dark)]">
                {localBoard.columns.find((c) => c.id === activeColumnId)?.title}
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
    </div>
  );
};
