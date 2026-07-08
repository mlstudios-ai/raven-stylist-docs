/**
 * Backend HTTP clients.
 *
 * - Profile API (`backend/api`) on port 8001 — picker list + profile detail.
 * - Stylist orchestrator on port 8002 — POST /turn drives the chat.
 *
 * Override via env vars in `.env.local`:
 *   NEXT_PUBLIC_API_BASE
 *   NEXT_PUBLIC_STYLIST_BASE
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";
const STYLIST_BASE = process.env.NEXT_PUBLIC_STYLIST_BASE ?? "http://localhost:8002";

// ------- Profile API -------

export type UserCard = {
  user_id: string;
  name?: string | null;
  archetype?: string | null;
  profile_photo?: { image_url?: string | null } | null;
};

export type UserDetail = {
  user_id: string;
  identity?: {
    name?: string;
    age?: number;
    gender_identity?: string;
    pronouns?: string;
    location?: string;
    occupation?: string;
  };
  archetype?: { name?: string; think?: string; confidence?: number };
  personality?: {
    primary?: { type?: string; think?: string };
    secondary?: { type?: string; think?: string };
  };
  style_dna?: {
    palette_signature?: string[];
    aesthetic_tags?: string[];
  };
  style_signals?: {
    aesthetic_tags_inferred?: string[];
    photo_detected_attributes?: string[];
  };
  photos?: Array<{ photo_id?: string; image_url?: string | null }>;
};

export async function listUsers(): Promise<UserCard[]> {
  const r = await fetch(`${API_BASE}/users`);
  if (!r.ok) throw new Error(`/users → ${r.status}`);
  return r.json();
}

export async function getUserDetail(userId: string): Promise<UserDetail> {
  const r = await fetch(
    `${API_BASE}/users/${userId}?attributes=identity,archetype,personality,style_dna,style_signals,photos`
  );
  if (!r.ok) throw new Error(`/users/${userId} → ${r.status}`);
  return r.json();
}

// ------- Stylist orchestrator -------

export type Signal = {
  kind: "thumb_up" | "thumb_down";
  label: string;
  reason?: string;
};

export type Piece = {
  role: string;
  category: string;
  color: string;
  styling_note: string;
};

export type OutfitCard = {
  label: string;
  summary: string;
  pieces: Piece[];
};

export type VtoBlock = {
  image_b64: string;
  image_mime: string;
  description: string;
  scene: {
    occasion?: string;
    setting?: string;
    lighting?: string;
    time_of_day?: string;
    mood?: string;
  };
};

export type TurnResponse = {
  type: "chat" | "outfit" | "vto" | "outfit_vto" | "clarification";
  text: string;
  outfit_card: OutfitCard | null;
  vto: VtoBlock | null;
  session_id: string;
  turn_id: string;
};

export async function postTurn(payload: {
  session_id: string;
  user_id: string;
  message: string;
  signals?: Signal[];
}): Promise<TurnResponse> {
  const r = await fetch(`${STYLIST_BASE}/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`/turn → ${r.status}: ${await r.text()}`);
  return r.json();
}

export function newSessionId(): string {
  return `s_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;
}
