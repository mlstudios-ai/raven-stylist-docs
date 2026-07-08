"use client";

import { OutfitCard as OutfitCardData } from "@/lib/api";
import { colorToHex } from "@/lib/colors";

export type Verdict = "up" | "down" | null;

type Props = {
  data: OutfitCardData;
  verdict: Verdict;
  onVerdictChange: (next: Verdict) => void;
};

export default function OutfitCard({ data, verdict, onVerdictChange }: Props) {
  const click = (clicked: "up" | "down") => {
    // Toggle: same = neutralise; opposite = switch.
    onVerdictChange(verdict === clicked ? null : clicked);
  };

  return (
    <div
      className={`my-3 border border-espresso-200/70 bg-espresso-50 rounded-sm overflow-hidden transition-all ${
        verdict === "down" ? "opacity-50" : ""
      }`}
    >
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-espresso-200/60">
        <p className="text-[10px] uppercase tracking-brand text-espresso-500">
          The look
        </p>
        <h3 className="font-display text-2xl text-espresso-900 mt-1 leading-tight">
          {data.label}
        </h3>
        {data.summary && (
          <p className="text-sm text-espresso-600 mt-3 leading-relaxed">
            {data.summary}
          </p>
        )}
      </div>

      {/* Pieces */}
      <ul className="divide-y divide-espresso-200/40">
        {data.pieces.map((piece, i) => {
          const hex = colorToHex(piece.color);
          return (
            <li key={i} className="px-6 py-4 flex items-start gap-4">
              <div
                className="flex-none mt-0.5 h-10 w-10 rounded-full border border-espresso-200/60"
                style={{ backgroundColor: hex }}
                title={piece.color}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-[10px] uppercase tracking-brand text-espresso-500">
                    {piece.role}
                  </span>
                  <span className="text-[10px] text-espresso-300">·</span>
                  <span className="text-xs text-espresso-700">
                    {piece.color}
                  </span>
                </div>
                <p className="text-sm font-medium text-espresso-900 mt-0.5">
                  {piece.category}
                </p>
                <p className="text-xs text-espresso-600 mt-1 leading-relaxed">
                  {piece.styling_note}
                </p>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Footer */}
      <div className="px-6 py-3 flex items-center justify-between border-t border-espresso-200/60 bg-espresso-100/40">
        <span className="text-[10px] uppercase tracking-brand text-espresso-500">
          {verdict === "up"
            ? "Saved"
            : verdict === "down"
            ? "Noted — I'll adjust"
            : "Tap to react"}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => click("up")}
            className={`h-8 w-8 flex items-center justify-center rounded-full transition-colors ${
              verdict === "up"
                ? "bg-espresso-800 text-espresso-50"
                : "text-espresso-500 hover:bg-espresso-200/60 hover:text-espresso-900"
            }`}
            aria-label="Thumb up"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
              <path d="M2 9h3v8H2V9zm14.5-1H11l1-3.5c.2-.7-.3-1.5-1-1.5h-.5c-.4 0-.8.3-.9.7L8 8H6v9h8.5c1 0 1.9-.6 2.2-1.6l1.6-4.6c.4-1.2-.5-2.4-1.8-2.4z" />
            </svg>
          </button>
          <button
            onClick={() => click("down")}
            className={`h-8 w-8 flex items-center justify-center rounded-full transition-colors ${
              verdict === "down"
                ? "bg-espresso-700 text-espresso-50"
                : "text-espresso-500 hover:bg-espresso-200/60 hover:text-espresso-900"
            }`}
            aria-label="Thumb down"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
              <path d="M18 11h-3V3h3v8zM3.5 12H9l-1 3.5c-.2.7.3 1.5 1 1.5h.5c.4 0 .8-.3.9-.7L12 12h2V3H5.5C4.5 3 3.6 3.6 3.3 4.6L1.7 9.2c-.4 1.2.5 2.4 1.8 2.4z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
