"use client";

import { UserCard } from "@/lib/api";

type Props = {
  selectedUser: UserCard | null;
  onPickerOpen: () => void;
};

export default function Header({ selectedUser, onPickerOpen }: Props) {
  return (
    <header className="flex items-center justify-between px-10 py-7 border-b border-espresso-200/60 bg-espresso-50/95 backdrop-blur-sm sticky top-0 z-30">
      <div className="flex items-baseline gap-3">
        <h1 className="font-display text-2xl tracking-tight text-espresso-800">
          RAVEN
        </h1>
        <span className="font-sans text-[10px] uppercase tracking-brand text-espresso-500">
          AI Stylist · Demo
        </span>
      </div>

      <button
        onClick={onPickerOpen}
        className="group flex items-center gap-3 pl-3 pr-4 py-2 rounded-full border border-espresso-300/60 hover:border-espresso-500 transition-colors"
      >
        {selectedUser?.profile_photo?.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001"}${selectedUser.profile_photo.image_url}`}
            alt={selectedUser.name ?? ""}
            className="h-7 w-7 rounded-full object-cover object-top border border-espresso-200"
          />
        ) : (
          <span className="h-7 w-7 rounded-full bg-espresso-200 flex items-center justify-center text-[11px] font-medium text-espresso-700">
            {selectedUser?.name?.[0] ?? "—"}
          </span>
        )}
        <span className="text-sm font-medium text-espresso-800">
          {selectedUser?.name ?? "Select profile"}
        </span>
        <svg
          className="h-3.5 w-3.5 text-espresso-500 group-hover:text-espresso-700 transition-colors"
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M3 5l3 3 3-3" />
        </svg>
      </button>
    </header>
  );
}
