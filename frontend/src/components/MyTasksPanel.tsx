"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { getMyTasks, type TaskCard } from "@/lib/api";

type Props = { currentUser: string };

const PRIORITY_CLS: Record<string, string> = {
  urgent: "bg-red-50 text-red-600",
  high: "bg-orange-50 text-orange-600",
  medium: "bg-yellow-50 text-yellow-700",
  low: "bg-blue-50 text-blue-600",
};

const SOON_MS = 3 * 24 * 60 * 60 * 1000;

type DueStatus = "overdue" | "soon" | "later" | "none";

function dueStatusFor(due: string | null | undefined): DueStatus {
  if (!due) return "none";
  const diff = new Date(due).getTime() - Date.now();
  if (diff < 0) return "overdue";
  if (diff < SOON_MS) return "soon";
  return "later";
}

const DUE_CLASS: Record<DueStatus, string> = {
  overdue: "text-red-500",
  soon: "text-yellow-600",
  later: "text-[var(--gray-text)]",
  none: "text-[var(--gray-text)]",
};

export const MyTasksPanel = ({ currentUser }: Props) => {
  const [tasks, setTasks] = useState<TaskCard[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getMyTasks()
      .then(setTasks)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [currentUser]);

  const active = tasks.filter((t) => !t.archived);
  const taskStatuses = active.map((task) => ({ task, status: dueStatusFor(task.due_date) }));
  const overdueCount = taskStatuses.filter((t) => t.status === "overdue").length;
  const soonCount = taskStatuses.filter((t) => t.status === "soon").length;

  return (
    <div className="rounded-[24px] border border-[var(--stroke)] bg-white p-6 shadow-[var(--shadow)]">
      <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
        My Tasks
      </p>

      {loading && <p className="text-xs text-[var(--gray-text)]">Loading…</p>}

      {!loading && active.length === 0 && (
        <p className="text-xs text-[var(--gray-text)]">No tasks assigned to you.</p>
      )}

      {!loading && (overdueCount > 0 || soonCount > 0) && (
        <div className="mb-3 flex gap-3">
          {overdueCount > 0 && (
            <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-[10px] font-semibold text-red-600">
              {overdueCount} overdue
            </span>
          )}
          {soonCount > 0 && (
            <span className="rounded-full bg-yellow-50 px-2.5 py-0.5 text-[10px] font-semibold text-yellow-700">
              {soonCount} due soon
            </span>
          )}
        </div>
      )}

      {!loading && active.length > 0 && (
        <div className="space-y-2">
          {taskStatuses.map(({ task, status }) => (
            <div
              key={task.card_id}
              className="rounded-xl border border-[var(--stroke)] px-3 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-[var(--navy-dark)]">{task.title}</p>
                {task.priority && (
                  <span className={clsx("shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", PRIORITY_CLS[task.priority])}>
                    {task.priority}
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-[11px] text-[var(--gray-text)]">
                {task.board_title} · {task.column_title}
              </p>
              {task.due_date && (
                <p className={clsx("mt-1 text-[11px] font-medium", DUE_CLASS[status])}>
                  Due {task.due_date}
                  {status === "overdue" && " · Overdue"}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
