import clsx from "clsx";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Card, Column, Priority } from "@/lib/kanban";
import { KanbanCard } from "@/components/KanbanCard";
import { NewCardForm } from "@/components/NewCardForm";

type KanbanColumnProps = {
  column: Column;
  cards: Card[];
  canDelete: boolean;
  boardId: string;
  currentUser: string;
  onRename: (columnId: string, title: string) => void;
  onDelete: (columnId: string) => void;
  onAddCard: (columnId: string, title: string, details: string, priority?: Priority | null, due_date?: string | null, labels?: string[]) => void;
  onDeleteCard: (columnId: string, cardId: string) => void;
  onEditCard: (columnId: string, updated: Card) => void;
  onDuplicateCard: (columnId: string, cardId: string) => void;
  isDragging?: boolean;
};

export const KanbanColumn = ({
  column,
  cards,
  canDelete,
  boardId,
  currentUser,
  onRename,
  onDelete,
  onAddCard,
  onDeleteCard,
  onEditCard,
  onDuplicateCard,
  isDragging,
}: KanbanColumnProps) => {
  const { setNodeRef: setDropRef, isOver } = useDroppable({ id: column.id });
  const { attributes, listeners, setNodeRef: setSortRef, transform, transition } = useSortable({ id: column.id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <section
      ref={(node) => { setSortRef(node); setDropRef(node); }}
      style={style}
      className={clsx(
        "flex min-h-[520px] flex-col rounded-3xl border border-[var(--stroke)] bg-[var(--surface-strong)] p-4 shadow-[var(--shadow)] transition",
        isOver && "ring-2 ring-[var(--accent-yellow)]",
        isDragging && "opacity-40"
      )}
      data-testid={`column-${column.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-full">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div
                className="h-2 w-10 cursor-grab rounded-full bg-[var(--accent-yellow)] active:cursor-grabbing"
                {...attributes}
                {...listeners}
                aria-label="Drag to reorder column"
              />
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                {cards.length} cards
              </span>
              {column.wip_limit != null && (
                <span
                  className={clsx(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    cards.length >= column.wip_limit
                      ? "bg-red-50 text-red-600"
                      : cards.length >= column.wip_limit * 0.8
                      ? "bg-yellow-50 text-yellow-700"
                      : "bg-[var(--surface)] text-[var(--gray-text)]"
                  )}
                >
                  WIP {cards.length}/{column.wip_limit}
                </span>
              )}
            </div>
            {canDelete && (
              <button
                type="button"
                onClick={() => onDelete(column.id)}
                className="rounded-full border border-transparent px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:border-red-200 hover:text-red-500"
                aria-label={`Delete ${column.title} column`}
              >
                Delete col
              </button>
            )}
          </div>
          <input
            value={column.title}
            onChange={(event) => onRename(column.id, event.target.value)}
            className="mt-3 w-full bg-transparent font-display text-lg font-semibold text-[var(--navy-dark)] outline-none"
            aria-label="Column title"
          />
        </div>
      </div>
      <div className="mt-4 flex flex-1 flex-col gap-3">
        <SortableContext items={column.cardIds} strategy={verticalListSortingStrategy}>
          {cards.map((card) => (
            <KanbanCard
              key={card.id}
              card={card}
              boardId={boardId}
              currentUser={currentUser}
              onDelete={(cardId) => onDeleteCard(column.id, cardId)}
              onEdit={(updated) => onEditCard(column.id, updated)}
              onDuplicate={(cardId) => onDuplicateCard(column.id, cardId)}
            />
          ))}
        </SortableContext>
        {cards.length === 0 && (
          <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-[var(--stroke)] px-3 py-6 text-center text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Drop a card here
          </div>
        )}
      </div>
      <NewCardForm
        onAdd={(title, details, priority, due_date, labels) =>
          onAddCard(column.id, title, details, priority, due_date, labels)
        }
      />
    </section>
  );
};
