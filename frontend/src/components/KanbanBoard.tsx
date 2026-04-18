"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { createId, moveCard, type BoardData, type Card } from "@/lib/kanban";

type KanbanBoardProps = {
  board: BoardData;
  boardId: string;
  currentUser: string;
  onBoardChange: (board: BoardData) => void;
};

export const KanbanBoard = ({ board, boardId, currentUser, onBoardChange }: KanbanBoardProps) => {
  const [localBoard, setLocalBoard] = useState<BoardData>(() => board);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLocalBoard(board);
  }, [board]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => localBoard.cards, [localBoard.cards]);

  const updateBoard = (nextBoard: BoardData) => {
    setLocalBoard(nextBoard);
    onBoardChange(nextBoard);
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    updateBoard({
      ...localBoard,
      columns: moveCard(
        localBoard.columns,
        active.id as string,
        over.id as string
      ),
    });
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
    priority?: import("@/lib/kanban").Priority | null,
    due_date?: string | null,
    labels?: string[]
  ) => {
    const id = createId("card");
    updateBoard({
      ...localBoard,
      cards: {
        ...localBoard.cards,
        [id]: { id, title, details: details || "", priority: priority ?? null, due_date: due_date ?? null, labels: labels ?? [] },
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
    updateBoard({
      ...localBoard,
      cards: Object.fromEntries(
        Object.entries(localBoard.cards).filter(([id]) => id !== cardId)
      ),
      columns: localBoard.columns.map((column) =>
        column.id === columnId
          ? {
              ...column,
              cardIds: column.cardIds.filter((id) => id !== cardId),
            }
          : column
      ),
    });
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  const [filterPriority, setFilterPriority] = useState<string>("");
  const [filterAssignee, setFilterAssignee] = useState<string>("");
  const [filterDue, setFilterDue] = useState<string>("");
  const [hideArchived, setHideArchived] = useState(false);

  const allLabels = useMemo(() => {
    const set = new Set<string>();
    Object.values(localBoard.cards).forEach((c) => (c.labels ?? []).forEach((l) => set.add(l)));
    return Array.from(set).sort();
  }, [localBoard.cards]);

  const [filterLabel, setFilterLabel] = useState<string>("");

  const allAssignees = useMemo(() => {
    const set = new Set<string>();
    Object.values(localBoard.cards).forEach((c) => { if (c.assignee) set.add(c.assignee); });
    return Array.from(set).sort();
  }, [localBoard.cards]);

  const hasActiveFilter = !!(searchQuery.trim() || filterPriority || filterAssignee || filterDue || filterLabel || hideArchived);

  const clearFilters = () => {
    setSearchQuery("");
    setFilterPriority("");
    setFilterAssignee("");
    setFilterDue("");
    setFilterLabel("");
    setHideArchived(false);
  };

  const matchesSearch = useCallback((card: Card): boolean => {
    if (hideArchived && card.archived) return false;
    if (filterPriority && card.priority !== filterPriority) return false;
    if (filterLabel && !(card.labels ?? []).includes(filterLabel)) return false;
    if (filterAssignee && card.assignee !== filterAssignee) return false;
    if (filterDue === "overdue") {
      if (!card.due_date || new Date(card.due_date).getTime() >= Date.now()) return false;
    } else if (filterDue === "soon") {
      const diff = card.due_date ? new Date(card.due_date).getTime() - Date.now() : null;
      if (diff === null || diff < 0 || diff >= 3 * 24 * 60 * 60 * 1000) return false;
    } else if (filterDue === "none") {
      if (card.due_date) return false;
    }
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      card.title.toLowerCase().includes(q) ||
      (card.details ?? "").toLowerCase().includes(q) ||
      (card.labels ?? []).some((l) => l.toLowerCase().includes(q))
    );
  }, [searchQuery, filterPriority, filterLabel, filterAssignee, filterDue, hideArchived]);

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(localBoard, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "board-export.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  // Ctrl+K / Cmd+K focuses search
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
            <button
              type="button"
              onClick={handleExport}
              aria-label="Export board as JSON"
              className="ml-auto rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
            >
              Export JSON
            </button>
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
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
    </div>
  );
};
