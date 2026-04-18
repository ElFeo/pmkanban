"use client";

import { useEffect, useState, type FormEvent } from "react";
import { changePassword, getProfile, type UserProfile } from "@/lib/api";

type UserProfileModalProps = {
  username: string;
  onClose: () => void;
};

export const UserProfileModal = ({ username, onClose }: UserProfileModalProps) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => null);
  }, []);

  const handleChangePassword = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(false);
    if (pwForm.next !== pwForm.confirm) {
      setPwError("New passwords do not match.");
      return;
    }
    if (pwForm.next.length < 8) {
      setPwError("New password must be at least 8 characters.");
      return;
    }
    setSaving(true);
    try {
      await changePassword(pwForm.current, pwForm.next);
      setPwSuccess(true);
      setPwForm({ current: "", next: "", confirm: "" });
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-md rounded-[24px] border border-[var(--stroke)] bg-white p-8 shadow-[0_24px_48px_rgba(3,33,71,0.16)]">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold text-[var(--navy-dark)]">Profile</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
          >
            Close
          </button>
        </div>

        <div className="mb-6 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">Account</p>
          <p className="mt-2 text-lg font-semibold text-[var(--navy-dark)]">{username}</p>
          {profile && (
            <p className="mt-1 text-sm text-[var(--gray-text)]">
              {profile.board_count} {profile.board_count === 1 ? "board" : "boards"}
            </p>
          )}
        </div>

        <div>
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Change password
          </p>
          <form onSubmit={handleChangePassword} className="space-y-3">
            <input
              type="password"
              placeholder="Current password"
              value={pwForm.current}
              onChange={(e) => setPwForm((p) => ({ ...p, current: e.target.value }))}
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              required
            />
            <input
              type="password"
              placeholder="New password"
              value={pwForm.next}
              onChange={(e) => setPwForm((p) => ({ ...p, next: e.target.value }))}
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              required
              minLength={8}
            />
            <input
              type="password"
              placeholder="Confirm new password"
              value={pwForm.confirm}
              onChange={(e) => setPwForm((p) => ({ ...p, confirm: e.target.value }))}
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              required
            />
            {pwError && <p className="text-sm font-semibold text-[var(--secondary-purple)]">{pwError}</p>}
            {pwSuccess && <p className="text-sm font-semibold text-green-600">Password changed successfully.</p>}
            <button
              type="submit"
              disabled={saving}
              className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:opacity-60"
            >
              {saving ? "Saving..." : "Change password"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
