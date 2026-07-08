"use client";

import { useState } from "react";
import Header from "@/components/Header";
import ProfilePickerModal from "@/components/ProfilePickerModal";
import ChatPanel, { ChatMessage } from "@/components/ChatPanel";
import VtoCanvas, { VtoState } from "@/components/VtoCanvas";
import { Verdict } from "@/components/OutfitCard";
import {
  newSessionId,
  postTurn,
  Signal,
  UserCard,
} from "@/lib/api";

let messageCounter = 0;
const newMessageId = () => `m_${++messageCounter}`;

export default function Page() {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [user, setUser] = useState<UserCard | null>(null);
  const [sessionId, setSessionId] = useState<string>(newSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [vtoState, setVtoState] = useState<VtoState>({ kind: "empty" });
  const [isThinking, setIsThinking] = useState(false);

  // Verdict per outfit-card MESSAGE id (not label) so two outfits that happen
  // to share a label don't share verdict state. Each outfit card in chat is a
  // distinct message with its own id. The VTO canvas's verdict is *derived*
  // from this map (see currentLookMessageId), so the chat card and the
  // image stay in sync — they're literally the same state.
  const [verdicts, setVerdicts] = useState<Record<string, Verdict>>({});

  // Signals queued for the next /turn call. Keyed by label so toggling
  // the same outfit label before send replaces rather than duplicates.
  const [pendingByLabel, setPendingByLabel] = useState<Record<string, Signal>>({});

  // The outfit message the VTO image is currently rendering — used to derive
  // the canvas verdict and to send the right label on backend signals.
  const [currentLookMessageId, setCurrentLookMessageId] = useState<string | null>(null);
  const [currentLookLabel, setCurrentLookLabel] = useState<string | null>(null);

  const vtoVerdict: Verdict =
    (currentLookMessageId && verdicts[currentLookMessageId]) || null;

  const resetSession = (u: UserCard) => {
    // Strict cleanup — every piece of session-scoped state goes here.
    setUser(u);
    setSessionId(newSessionId());
    setMessages([]);
    setVtoState({ kind: "empty" });
    setVerdicts({});
    setPendingByLabel({});
    setCurrentLookMessageId(null);
    setCurrentLookLabel(null);
    setPickerOpen(false);
  };

  // Outfit-card thumbs: keyed by message id (visual) but signal goes to
  // backend with the outfit's label.
  const onCardVerdictChange = (
    messageId: string,
    label: string,
    next: Verdict
  ) => {
    setVerdicts((v) => ({ ...v, [messageId]: next }));
    setPendingByLabel((p) => {
      const out = { ...p };
      if (next === null) {
        delete out[label];
      } else {
        out[label] = {
          kind: next === "up" ? "thumb_up" : "thumb_down",
          label,
        };
      }
      return out;
    });
  };

  // VTO canvas thumb: writes to the same verdicts slot as the outfit card the
  // image is rendering — that's how the two surfaces stay in sync.
  const onVtoVerdictChange = (next: Verdict) => {
    if (!currentLookMessageId || !currentLookLabel) return;
    onCardVerdictChange(currentLookMessageId, currentLookLabel, next);
  };

  const send = async (text: string) => {
    if (!user) return;

    setMessages((m) => [...m, { id: newMessageId(), role: "user", text }]);

    // Speculatively flip the canvas to loading on plausible VTO phrasing.
    // Backend response is authoritative — we revert if wrong.
    const looksLikeVto = /\b(show|try|see|let me see|render|visuali[sz]e|look like)\b/i.test(text);
    let speculativelyLoading = false;
    if (looksLikeVto && vtoState.kind !== "loading") {
      setVtoState({ kind: "loading", phase: "composing" });
      speculativelyLoading = true;
      setTimeout(() => {
        setVtoState((s) =>
          s.kind === "loading" ? { kind: "loading", phase: "rendering" } : s
        );
      }, 2500);
    }

    setIsThinking(true);
    try {
      const queued = Object.values(pendingByLabel);
      const signals = queued.length > 0 ? queued : undefined;
      setPendingByLabel({});

      const resp = await postTurn({
        session_id: sessionId,
        user_id: user.user_id,
        message: text,
        signals,
      });

      // Render outfit card and VTO image independently — a single turn can
      // produce both (e.g. "show me a different style").
      if (resp.outfit_card) {
        const outfitMessageId = newMessageId();
        setMessages((m) => [
          ...m,
          {
            id: outfitMessageId,
            role: "assistant",
            kind: "outfit",
            text: resp.text,
            outfit: resp.outfit_card!,
          },
        ]);
        // The VTO canvas (if it renders this turn) shows this outfit. Bind
        // the canvas verdict to this message so thumbs stay in sync.
        setCurrentLookMessageId(outfitMessageId);
        setCurrentLookLabel(resp.outfit_card.label);
      } else {
        setMessages((m) => [
          ...m,
          {
            id: newMessageId(),
            role: "assistant",
            kind: "text",
            text: resp.text,
          },
        ]);
      }

      if (resp.vto) {
        setVtoState({ kind: "image", data: resp.vto });
      } else if (speculativelyLoading) {
        setVtoState((s) => (s.kind === "loading" ? { kind: "empty" } : s));
      }
    } catch (err) {
      console.error("turn failed", err);
      const errText =
        err instanceof Error ? err.message : "Something went wrong. Try again.";
      setMessages((m) => [
        ...m,
        {
          id: newMessageId(),
          role: "assistant",
          kind: "text",
          text: `(${errText})`,
        },
      ]);
      if (speculativelyLoading || vtoState.kind === "loading") {
        setVtoState({ kind: "empty" });
      }
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <main className="h-screen flex flex-col bg-espresso-50">
      <Header
        selectedUser={user}
        onPickerOpen={() => setPickerOpen(true)}
      />

      <div className="flex-1 min-h-0 grid grid-cols-[minmax(0,1.4fr)_minmax(380px,1fr)] overflow-hidden">
        <VtoCanvas
          state={vtoState}
          hasUser={!!user}
          verdict={vtoVerdict}
          onPickProfile={() => setPickerOpen(true)}
          onVerdictChange={onVtoVerdictChange}
        />
        <ChatPanel
          user={user}
          messages={messages}
          isThinking={isThinking}
          verdicts={verdicts}
          onVerdictChange={onCardVerdictChange}
          onSend={send}
        />
      </div>

      <ProfilePickerModal
        open={pickerOpen}
        selectedUserId={user?.user_id ?? null}
        onClose={() => setPickerOpen(false)}
        onSelect={resetSession}
      />
    </main>
  );
}
