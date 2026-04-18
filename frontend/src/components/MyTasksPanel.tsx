"use client";

import { useEffect, useState } from "react";
import { getMyTasks, type TaskCard } from "@/lib/api";
import clsx from "clsx";

type Props = { currentUser: string };

const PRIORITY_CLS: Record<string, string> = {
  urgent: "bg-red-50 text-red-600",
  high: "bg-orange-50 text-orange-600",
  medium: "bg-yellow-50 text-yellow-700",
  low: "bg-blue-50 text-blue-600",
};

const dueDelta = (due: string) => new Date(due).getTime() - Date.now();

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
  const overdue = active.filter((t) => t.due_date && dueDelta(t.due_date) < 0);
  const upcoming = active.filter((t) => t.due_date && dueDelta(t.due_date) >= 0 && dueDelta(t.due_date) < 3 * 24 * 60 * 60 * 1000);

  return (
    <div className="rounded-[24px] border border-[var(--stroke)] bg-white p-6 shadow-[var(--shadow)]">
      <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
        My Tasks
      </p>

      {loading && (
        <p className="text-xs text-[var(--gray-text)]">Loading…</p>
      )}

      {!loading && active.length === 0 && (
        <p className="text-xs text-[var(--gray-text)]">No tasks assigned to you.</p>
      )}

      {!loading && (overdue.length > 0 || upcoming.length > 0) && (
        <div className="mb-3 flex gap-3">
          {overdue.length > 0 && (
            <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-[10px] font-semibold text-red-600">
              {overdue.length} overdue
            </span>
          )}
          {upcoming.length > 0 && (
            <span className="rounded-full bg-yellow-50 px-2.5 py-0.5 text-[10px] font-semibold text-yellow-700">
              {upcoming.length} due soon
            </span>
          )}
        </div>
      )}

      {!loading && active.length > 0 && (
        <div className="space-y-2">
          {active.map((t) => {
            const isOverdue = t.due_date && dueDelta(t.due_date) < 0;
            const isSoon = t.due_date && dueDelta(t.due_date) >= 0 && dueDelta(t.due_date) < 3 * 24 * 60 * 60 * 1000;
            return (
              <div
                key={t.card_id}
                className="rounded-xl border border-[var(--stroke)] px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-[var(--navy-dark)]">{t.title}</p>
                  {t.priority && (
                    <span className={clsx("shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", PRIORITY_CLS[t.priority])}>
                      {t.priority}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-[11px] text-[var(--gray-text)]">
                  {t.board_title} · {t.column_title}
                </p>
                {t.due_date && (
                  <p className={clsx("mt-1 text-[11px] font-medium", isOverdue ? "text-red-500" : isSoon ? "text-yellow-600" : "text-[var(--gray-text)]")}>
                    Due {t.due_date}{isOverdue ? " · Overdue" : ""}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
