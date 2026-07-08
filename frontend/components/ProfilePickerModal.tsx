"use client";

import { useEffect, useState } from "react";
import { getUserDetail, listUsers, UserCard, UserDetail } from "@/lib/api";
import { colorToHex, inkOn } from "@/lib/colors";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";

type Props = {
  open: boolean;
  selectedUserId: string | null;
  onClose: () => void;
  onSelect: (user: UserCard) => void;
};

export default function ProfilePickerModal({
  open,
  selectedUserId,
  onClose,
  onSelect,
}: Props) {
  const [users, setUsers] = useState<UserCard[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!open) return;
    listUsers().then((u) => {
      setUsers(u);
      setActiveId(selectedUserId ?? u[0]?.user_id ?? null);
    });
  }, [open, selectedUserId]);

  useEffect(() => {
    if (!activeId) return;
    setLoadingDetail(true);
    getUserDetail(activeId)
      .then(setDetail)
      .finally(() => setLoadingDetail(false));
  }, [activeId]);

  if (!open) return null;

  const active = users.find((u) => u.user_id === activeId) ?? null;
  const palette = detail?.style_dna?.palette_signature ?? [];
  const aestheticTags =
    detail?.style_dna?.aesthetic_tags ??
    detail?.style_signals?.aesthetic_tags_inferred ??
    [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-espresso-900/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-[min(1100px,92vw)] h-[min(720px,88vh)] bg-espresso-50 shadow-2xl rounded-sm overflow-hidden grid grid-cols-[300px_1fr] animate-fade-up"
      >
        {/* List */}
        <aside className="border-r border-espresso-200/60 bg-espresso-100/40 overflow-y-auto scrollbar-clean">
          <div className="px-7 pt-7 pb-3">
            <p className="text-[10px] uppercase tracking-brand text-espresso-500">
              Choose a profile
            </p>
            <p className="font-display text-2xl text-espresso-800 mt-1 leading-tight">
              The persona shapes the style
            </p>
          </div>

          <ul className="pb-6">
            {users.map((u) => (
              <li key={u.user_id}>
                <button
                  onClick={() => setActiveId(u.user_id)}
                  className={`w-full px-7 py-4 flex items-center gap-3 text-left hover:bg-espresso-100 transition-colors ${
                    activeId === u.user_id ? "bg-espresso-100" : ""
                  }`}
                >
                  {u.profile_photo?.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={`${API_BASE}${u.profile_photo.image_url}`}
                      alt={u.name ?? ""}
                      className="h-10 w-10 rounded-full object-cover object-top border border-espresso-200"
                    />
                  ) : (
                    <span className="h-10 w-10 rounded-full bg-espresso-300" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-espresso-800 truncate">
                      {u.name}
                    </p>
                    <p className="text-[11px] uppercase tracking-wider text-espresso-500">
                      {u.archetype ?? "—"}
                    </p>
                  </div>
                  {selectedUserId === u.user_id && (
                    <span className="text-[10px] uppercase tracking-brand text-accent">
                      Current
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Detail */}
        <section className="relative flex flex-col min-h-0">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 z-10 h-8 w-8 flex items-center justify-center rounded-full bg-espresso-50/90 backdrop-blur-sm text-espresso-500 hover:text-espresso-800 hover:bg-espresso-100 transition-colors"
            aria-label="Close"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>

          {active && (
            <>
              {/* Body — photo + scrollable text */}
              <div className="flex-1 min-h-0 grid grid-cols-[1fr_1.2fr]">
                {/* Photo */}
                <div className="bg-espresso-200/40 relative">
                  {active.profile_photo?.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={`${API_BASE}${active.profile_photo.image_url}`}
                      alt={active.name ?? ""}
                      className="absolute inset-0 h-full w-full object-cover object-top"
                    />
                  ) : null}
                </div>

                {/* Text — scrolls internally */}
                <div className="overflow-y-auto scrollbar-clean px-10 py-12">
                  <p className="text-[10px] uppercase tracking-brand text-espresso-500">
                    Profile
                  </p>
                  <h2 className="font-display text-4xl text-espresso-900 mt-2 leading-[1.05]">
                    {active.name}
                  </h2>

                  {detail?.identity?.occupation && (
                    <p className="text-sm text-espresso-600 mt-3 italic">
                      {detail.identity.occupation}
                      {detail.identity.location && (
                        <> · {detail.identity.location}</>
                      )}
                    </p>
                  )}

                  {/* Archetype */}
                  {detail?.archetype && (
                    <div className="mt-8">
                      <p className="text-[10px] uppercase tracking-brand text-espresso-500">
                        Archetype
                      </p>
                      <p className="font-display text-xl text-espresso-800 mt-1">
                        {detail.archetype.name}
                      </p>
                      {detail.archetype.think && (
                        <p className="text-sm text-espresso-600 mt-2 leading-relaxed">
                          {detail.archetype.think}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Personality */}
                  {detail?.personality?.primary && (
                    <div className="mt-6">
                      <p className="text-[10px] uppercase tracking-brand text-espresso-500">
                        Personality
                      </p>
                      <p className="font-display text-xl text-espresso-800 mt-1">
                        {detail.personality.primary.type}
                        {detail.personality.secondary && (
                          <span className="text-espresso-500 font-sans text-base font-normal ml-2">
                            + {detail.personality.secondary.type}
                          </span>
                        )}
                      </p>
                      {detail.personality.primary.think && (
                        <p className="text-sm text-espresso-600 mt-2 leading-relaxed">
                          {detail.personality.primary.think}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Palette */}
                  {palette.length > 0 && (
                    <div className="mt-6">
                      <p className="text-[10px] uppercase tracking-brand text-espresso-500">
                        Palette
                      </p>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {palette.slice(0, 8).map((c) => {
                          const hex = colorToHex(c);
                          return (
                            <span
                              key={c}
                              className="text-[11px] font-medium px-3 py-1 rounded-full border border-espresso-200/80"
                              style={{ backgroundColor: hex, color: inkOn(hex) }}
                            >
                              {c}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Aesthetic tags */}
                  {aestheticTags.length > 0 && (
                    <div className="mt-6">
                      <p className="text-[10px] uppercase tracking-brand text-espresso-500">
                        Style signal
                      </p>
                      <p className="text-sm text-espresso-700 mt-2 leading-relaxed">
                        {aestheticTags.slice(0, 5).join(" · ")}
                      </p>
                    </div>
                  )}

                  {loadingDetail && !detail && (
                    <p className="text-xs text-espresso-400 mt-4">Loading…</p>
                  )}
                </div>
              </div>

              {/* Sticky footer — always visible */}
              <div className="flex-none border-t border-espresso-200/60 bg-espresso-50 px-10 py-4 flex items-center justify-end gap-3">
                <button
                  onClick={onClose}
                  className="px-5 py-2.5 text-sm text-espresso-600 hover:text-espresso-900 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => onSelect(active)}
                  className="px-7 py-2.5 text-sm font-medium tracking-wide bg-espresso-800 text-espresso-50 hover:bg-espresso-900 transition-colors rounded-sm"
                >
                  Style with {active.name?.split(" ")[0]}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
