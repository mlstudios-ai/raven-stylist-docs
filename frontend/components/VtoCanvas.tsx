"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { VtoBlock } from "@/lib/api";
import { Verdict } from "./OutfitCard";

export type VtoState =
  | { kind: "empty" }
  | { kind: "loading"; phase: "composing" | "rendering" }
  | { kind: "image"; data: VtoBlock };

type Props = {
  state: VtoState;
  hasUser: boolean;
  verdict: Verdict;
  onPickProfile?: () => void;
  onVerdictChange?: (next: Verdict) => void;
};

export default function VtoCanvas({
  state,
  hasUser,
  verdict,
  onPickProfile,
  onVerdictChange,
}: Props) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  // The lightbox is rendered via a portal into document.body so it escapes
  // any ancestor that creates a stacking / containing-block context (the
  // canvas root has `animate-fade-in`; the grid has `overflow-hidden`).
  // Mounted flag guards SSR where `document` doesn't exist.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Close the lightbox on ESC. Only listens while open.
  useEffect(() => {
    if (!lightboxOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxOpen(false);
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [lightboxOpen]);

  // If the image goes away (new turn, profile switch), force-close the modal
  // so we never end up stuck on a stale image.
  useEffect(() => {
    if (state.kind !== "image") setLightboxOpen(false);
  }, [state.kind]);

  const click = (clicked: "up" | "down") => {
    onVerdictChange?.(verdict === clicked ? null : clicked);
  };

  if (state.kind === "empty") {
    return (
      <div className="relative h-full w-full bg-gradient-to-br from-espresso-100 via-espresso-50 to-espresso-200/50 flex items-center justify-center overflow-hidden">
        {/* Decorative texture */}
        <div className="absolute inset-0 opacity-[0.04] mix-blend-multiply"
          style={{
            backgroundImage:
              "radial-gradient(circle at 30% 20%, #4A3A2A 0%, transparent 50%), radial-gradient(circle at 70% 80%, #6E5840 0%, transparent 50%)",
          }}
        />
        <div className="relative text-center max-w-md px-12 animate-fade-in">
          <p className="text-[10px] uppercase tracking-brand text-espresso-500">
            {hasUser ? "The look, on you" : "Welcome"}
          </p>
          {hasUser ? (
            <>
              <p className="font-display text-3xl text-espresso-800 mt-4 leading-tight italic">
                &ldquo;Style guides appear in chat. Ask Raven to show you.&rdquo;
              </p>
              <p className="text-sm text-espresso-500 mt-6 leading-relaxed">
                Try <span className="text-espresso-700 italic">&ldquo;show me what that looks like&rdquo;</span> after a recommendation lands.
              </p>
            </>
          ) : (
            <>
              <p className="font-display text-4xl text-espresso-800 mt-4 leading-[1.05] italic">
                Style. Made for you.
              </p>
              <p className="text-sm text-espresso-500 mt-6 leading-relaxed">
                Choose a profile to begin. Each persona styles differently — that&rsquo;s the point.
              </p>
              {onPickProfile && (
                <button
                  onClick={onPickProfile}
                  className="mt-8 px-7 py-3 text-sm font-medium tracking-wide bg-espresso-800 text-espresso-50 hover:bg-espresso-900 transition-colors rounded-sm"
                >
                  Choose a profile
                </button>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <div className="relative h-full w-full bg-espresso-100/60 flex items-center justify-center overflow-hidden">
        {/* Skeleton silhouette */}
        <div
          className="absolute inset-0 animate-shimmer"
          style={{
            background:
              "linear-gradient(110deg, #E5D9C7 8%, #F2EBE0 18%, #E5D9C7 33%)",
            backgroundSize: "200% 100%",
          }}
        />
        <div className="relative text-center">
          <p className="text-[10px] uppercase tracking-brand text-espresso-600">
            Virtual try-on
          </p>
          <p className="font-display text-2xl text-espresso-800 italic mt-3">
            {state.phase === "composing"
              ? "Composing the scene…"
              : "Rendering the look…"}
          </p>
          <div className="flex items-center justify-center gap-1 mt-5">
            <span className="h-1.5 w-1.5 rounded-full bg-espresso-700 animate-shimmer" />
            <span
              className="h-1.5 w-1.5 rounded-full bg-espresso-700 animate-shimmer"
              style={{ animationDelay: "0.2s" }}
            />
            <span
              className="h-1.5 w-1.5 rounded-full bg-espresso-700 animate-shimmer"
              style={{ animationDelay: "0.4s" }}
            />
          </div>
        </div>
      </div>
    );
  }

  // image state
  const dataUrl = `data:${state.data.image_mime};base64,${state.data.image_b64}`;
  const scene = state.data.scene;

  return (
    <div className="relative h-full w-full bg-espresso-900 overflow-hidden group animate-fade-in">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={dataUrl}
        alt={state.data.description}
        className="absolute inset-0 h-full w-full object-contain transition-all duration-500"
      />

      {/* Caption overlay — bottom-left, editorial */}
      <div className="absolute bottom-0 left-0 right-0 p-10 bg-gradient-to-t from-espresso-900/90 via-espresso-900/40 to-transparent pointer-events-none">
        <div className="max-w-xl">
          <p className="text-[10px] uppercase tracking-brand text-espresso-200">
            {scene.time_of_day ?? "On you"}
          </p>
          {scene.occasion && (
            <p className="font-display text-2xl text-espresso-50 mt-2 leading-tight">
              {scene.occasion}
            </p>
          )}
          {scene.mood && (
            <p className="text-sm text-espresso-200/90 mt-2 italic leading-relaxed">
              {scene.mood}
            </p>
          )}
        </div>
      </div>

      {/* Action buttons — top-right */}
      <div className="absolute top-5 right-5 flex flex-col gap-2 opacity-90 group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => click("up")}
          className={`h-10 w-10 flex items-center justify-center rounded-full backdrop-blur-md transition-colors ${
            verdict === "up"
              ? "bg-espresso-50 text-espresso-900"
              : "bg-espresso-900/40 hover:bg-espresso-900/60 text-espresso-50"
          }`}
          aria-label="Thumb up"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
            <path d="M2 9h3v8H2V9zm14.5-1H11l1-3.5c.2-.7-.3-1.5-1-1.5h-.5c-.4 0-.8.3-.9.7L8 8H6v9h8.5c1 0 1.9-.6 2.2-1.6l1.6-4.6c.4-1.2-.5-2.4-1.8-2.4z" />
          </svg>
        </button>
        <button
          onClick={() => click("down")}
          className={`h-10 w-10 flex items-center justify-center rounded-full backdrop-blur-md transition-colors ${
            verdict === "down"
              ? "bg-espresso-50 text-espresso-900"
              : "bg-espresso-900/40 hover:bg-espresso-900/60 text-espresso-50"
          }`}
          aria-label="Thumb down"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
            <path d="M18 11h-3V3h3v8zM3.5 12H9l-1 3.5c-.2.7.3 1.5 1 1.5h.5c.4 0 .8-.3.9-.7L12 12h2V3H5.5C4.5 3 3.6 3.6 3.3 4.6L1.7 9.2c-.4 1.2.5 2.4 1.8 2.4z" />
          </svg>
        </button>
        <button
          onClick={() => setLightboxOpen(true)}
          className="h-10 w-10 flex items-center justify-center rounded-full bg-espresso-900/40 hover:bg-espresso-900/60 backdrop-blur-md text-espresso-50 transition-colors"
          aria-label="View fullscreen"
          title="View fullscreen"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 7V3h4M17 7V3h-4M3 13v4h4M17 13v4h-4" />
          </svg>
        </button>
      </div>

      {verdict && (
        <div className="absolute top-5 left-5 px-3 py-1.5 rounded-full bg-espresso-50/90 backdrop-blur-md text-[10px] uppercase tracking-brand text-espresso-800 animate-fade-in">
          {verdict === "up" ? "Saved" : "I'll adjust"}
        </div>
      )}

      {lightboxOpen && mounted &&
        createPortal(
          <div
            className="fixed inset-0 z-[1000] bg-espresso-900/95 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in"
            onClick={() => setLightboxOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-label="Fullscreen image"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={dataUrl}
              alt={state.data.description}
              className="max-h-full max-w-full object-contain"
              onClick={(e) => e.stopPropagation()}
            />
            <button
              onClick={() => setLightboxOpen(false)}
              className="absolute top-5 right-5 h-10 w-10 flex items-center justify-center rounded-full bg-espresso-900/60 hover:bg-espresso-900/80 backdrop-blur-md text-espresso-50 transition-colors"
              aria-label="Close fullscreen"
              title="Close (Esc)"
            >
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M5 5l10 10M15 5L5 15" />
              </svg>
            </button>
          </div>,
          document.body
        )}
    </div>
  );
}
