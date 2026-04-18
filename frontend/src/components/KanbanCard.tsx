import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import type { Card, Priority } from "@/lib/kanban";
import { useState } from "react";
import { CardEditModal } from "@/components/CardEditModal";

type KanbanCardProps = {
  card: Card;
  onDelete: (cardId: string) => void;
  onEdit: (updated: Card) => void;
};

const PRIORITY_STYLES: Record<Priority, { label: string; cls: string }> = {
  low: { label: "Low", cls: "bg-blue-50 text-blue-600" },
  medium: { label: "Medium", cls: "bg-yellow-50 text-yellow-700" },
  high: { label: "High", cls: "bg-orange-50 text-orange-600" },
  urgent: { label: "Urgent", cls: "bg-red-50 text-red-600" },
};

const dueDateStatus = (due: string): "overdue" | "soon" | "ok" => {
  const diff = new Date(due).getTime() - Date.now();
  if (diff < 0) return "overdue";
  if (diff < 3 * 24 * 60 * 60 * 1000) return "soon";
  return "ok";
};

export const KanbanCard = ({ card, onDelete, onEdit }: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });
  const [editing, setEditing] = useState(false);

  const style = { transform: CSS.Transform.toString(transform), transition };
  const priority = card.priority ? PRIORITY_STYLES[card.priority] : null;
  const labels = card.labels ?? [];

  return (
    <>
    {editing && (
      <CardEditModal
        card={card}
        onSave={onEdit}
        onClose={() => setEditing(false)}
      />
    )}
    <article
      ref={setNodeRef}
      style={style}
      className={clsx(
        "rounded-2xl border border-transparent bg-white px-4 py-4 shadow-[0_12px_24px_rgba(3,33,71,0.08)]",
        "transition-all duration-150",
        isDragging && "opacity-60 shadow-[0_18px_32px_rgba(3,33,71,0.16)]"
      )}
      {...attributes}
      {...listeners}
      data-testid={`card-${card.id}`}
    >
      {/* Priority + delete row */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          {priority && (
            <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", priority.cls)}>
              {priority.label}
            </span>
          )}
          {labels.map((label) => (
            <span
              key={label}
              className="rounded-full bg-[var(--surface)] px-2 py-0.5 text-[10px] font-medium text-[var(--gray-text)]"
            >
              {label}
            </span>
          ))}
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setEditing(true); }}
            className="rounded-full border border-transparent px-2 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--primary-blue)]"
            aria-label={`Edit ${card.title}`}
          >
            Edit
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(card.id); }}
            className="rounded-full border border-transparent px-2 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
            aria-label={`Delete ${card.title}`}
          >
            Remove
          </button>
        </div>
      </div>

      {/* Title + details */}
      <h4 className="font-display text-base font-semibold text-[var(--navy-dark)]">
        {card.title}
      </h4>
      {card.details && (
        <p className="mt-1 text-sm leading-6 text-[var(--gray-text)]">{card.details}</p>
      )}

      {/* Due date */}
      {card.due_date && (
        <p
          className={clsx(
            "mt-2 text-xs font-medium",
            dueDateStatus(card.due_date) === "overdue" && "text-red-500",
            dueDateStatus(card.due_date) === "soon" && "text-yellow-600",
            dueDateStatus(card.due_date) === "ok" && "text-[var(--gray-text)]"
          )}
        >
          Due {card.due_date}
          {dueDateStatus(card.due_date) === "overdue" && " · Overdue"}
        </p>
      )}
    </article>
    </>
  );
};
