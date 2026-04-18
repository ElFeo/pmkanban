"use client";

import { useEffect, useState } from "react";
import { getBoardStats, getBoardActivity, type BoardStats, type ActivityEntry } from "@/lib/api";

type BoardStatsPanelProps = {
  boardId: string;
  refreshKey?: number;
};

export const BoardStatsPanel = ({ boardId, refreshKey = 0 }: BoardStatsPanelProps) => {
  const [stats, setStats] = useState<BoardStats | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);

  useEffect(() => {
    if (!boardId) return;
    getBoardStats(boardId).then(setStats).catch(() => null);
    getBoardActivity(boardId).then(setActivity).catch(() => null);
  }, [boardId, refreshKey]);

  if (!stats) return null;

  const pb = stats.priority_breakdown;

  return (
    <aside className="flex flex-col gap-4 rounded-3xl border border-[var(--stroke)] bg-white/80 p-5 shadow-[var(--shadow)] backdrop-blur">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">Board stats</p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-center">
            <p className="text-2xl font-semibold text-[var(--navy-dark)]">{stats.total_cards}</p>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--gray-text)]">Total</p>
          </div>
          <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-center">
            <p className="text-2xl font-semibold text-red-500">{stats.overdue_count}</p>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--gray-text)]">Overdue</p>
          </div>
        </div>
      </div>

      {stats.columns.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">By column</p>
          <div className="space-y-1.5">
            {stats.columns.map((col) => (
              <div key={col.column_id} className="flex items-center gap-2">
                <span className="w-2 h-2 shrink-0 rounded-full bg-[var(--accent-yellow)]" />
                <span className="flex-1 truncate text-xs text-[var(--navy-dark)]">{col.column_title}</span>
                <span className="text-xs font-semibold text-[var(--gray-text)]">{col.card_count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">Priority</p>
        <div className="flex flex-wrap gap-2">
          {pb.urgent > 0 && <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-600">{pb.urgent} Urgent</span>}
          {pb.high > 0 && <span className="rounded-full bg-orange-50 px-2 py-0.5 text-[10px] font-semibold text-orange-600">{pb.high} High</span>}
          {pb.medium > 0 && <span className="rounded-full bg-yellow-50 px-2 py-0.5 text-[10px] font-semibold text-yellow-700">{pb.medium} Med</span>}
          {pb.low > 0 && <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-600">{pb.low} Low</span>}
          {pb.none > 0 && <span className="rounded-full bg-[var(--surface)] px-2 py-0.5 text-[10px] font-semibold text-[var(--gray-text)]">{pb.none} None</span>}
        </div>
      </div>

      {activity.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">Recent activity</p>
          <div className="space-y-2">
            {activity.slice(0, 5).map((entry) => (
              <div key={entry.id} className="text-xs text-[var(--gray-text)]">
                <span className="font-medium text-[var(--navy-dark)]">{entry.action.replace(/_/g, " ")}</span>
                {entry.detail && <span> — {entry.detail}</span>}
                <div className="text-[10px] opacity-60">{entry.created_at.slice(0, 16).replace("T", " ")}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
};
