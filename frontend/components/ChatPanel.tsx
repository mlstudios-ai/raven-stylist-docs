"use client";

import { useEffect, useRef, useState } from "react";
import { OutfitCard as OutfitCardData, UserCard } from "@/lib/api";
import OutfitCard, { Verdict } from "./OutfitCard";

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; kind: "text"; text: string }
  | {
      id: string;
      role: "assistant";
      kind: "outfit";
      text: string;
      outfit: OutfitCardData;
    };

type Props = {
  user: UserCard | null;
  messages: ChatMessage[];
  isThinking: boolean;
  /** keyed by chat-message id (not outfit label) */
  verdicts: Record<string, Verdict>;
  onVerdictChange: (messageId: string, label: string, next: Verdict) => void;
  onSend: (text: string) => void;
};

export default function ChatPanel({
  user,
  messages,
  isThinking,
  verdicts,
  onVerdictChange,
  onSend,
}: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isThinking]);

  // Restore focus to the textarea when thinking finishes — otherwise the
  // disabled state during the request strips focus and the user has to
  // click back into the box.
  useEffect(() => {
    if (!isThinking && user) {
      textareaRef.current?.focus();
    }
  }, [isThinking, user]);

  const submit = () => {
    const text = input.trim();
    if (!text || !user) return;
    onSend(text);
    setInput("");
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-espresso-50/60 border-l border-espresso-200/60">
      {/* Header */}
      <div className="flex-none px-6 py-4 border-b border-espresso-200/60 bg-espresso-100/50">
        <div className="flex items-baseline gap-2">
          <span className="text-[10px] uppercase tracking-brand text-espresso-500">
            Conversation
          </span>
          <span className="font-display text-base text-espresso-800">
            with Raven
          </span>
        </div>
      </div>

      {/* Messages — min-h-0 lets it scroll instead of growing past the flex parent */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto scrollbar-clean px-6 py-6 space-y-4"
      >
        {messages.length === 0 && user && (
          <div className="text-center py-12 animate-fade-up">
            <p className="font-display text-lg text-espresso-700 italic leading-relaxed max-w-xs mx-auto">
              &ldquo;Tell me what you&rsquo;re dressing for.&rdquo;
            </p>
            <p className="text-xs text-espresso-500 mt-3">
              An occasion, the weather, or how you want to feel.
            </p>
          </div>
        )}

        {messages.length === 0 && !user && (
          <div className="text-center py-12">
            <p className="font-display text-lg text-espresso-700 italic">
              Pick a profile to begin.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className="animate-fade-up">
            {m.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-[85%] bg-espresso-800 text-espresso-50 px-4 py-2.5 rounded-2xl rounded-br-sm text-sm leading-relaxed">
                  {m.text}
                </div>
              </div>
            ) : m.kind === "outfit" ? (
              <div className="space-y-2">
                {m.text && (
                  <p className="text-sm text-espresso-700 leading-relaxed">
                    {m.text}
                  </p>
                )}
                <OutfitCard
                  data={m.outfit}
                  verdict={verdicts[m.id] ?? null}
                  onVerdictChange={(next) =>
                    onVerdictChange(m.id, m.outfit.label, next)
                  }
                />
              </div>
            ) : (
              <div className="text-sm text-espresso-700 leading-relaxed">
                {m.text}
              </div>
            )}
          </div>
        ))}

        {isThinking && (
          <div className="flex items-center gap-2 text-espresso-400 animate-fade-in">
            <span className="text-xs italic">Raven is thinking</span>
            <span className="flex gap-1">
              <span className="h-1 w-1 rounded-full bg-espresso-400 animate-shimmer" />
              <span
                className="h-1 w-1 rounded-full bg-espresso-400 animate-shimmer"
                style={{ animationDelay: "0.2s" }}
              />
              <span
                className="h-1 w-1 rounded-full bg-espresso-400 animate-shimmer"
                style={{ animationDelay: "0.4s" }}
              />
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex-none border-t border-espresso-200/60 px-4 py-4 bg-espresso-50">
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            disabled={!user || isThinking}
            placeholder={user ? "What would you like to wear?" : "Pick a profile first"}
            rows={2}
            className="w-full resize-none px-4 py-3 pr-12 text-sm bg-espresso-100/40 border border-espresso-200/60 focus:border-espresso-500 focus:outline-none rounded-sm placeholder:text-espresso-400 text-espresso-900 disabled:opacity-50 disabled:cursor-not-allowed leading-relaxed"
          />
          <button
            onClick={submit}
            disabled={!input.trim() || !user || isThinking}
            className="absolute right-2 bottom-3 h-8 w-8 flex items-center justify-center rounded-full bg-espresso-800 text-espresso-50 hover:bg-espresso-900 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Send"
          >
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 14V2M3 7l5-5 5 5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
