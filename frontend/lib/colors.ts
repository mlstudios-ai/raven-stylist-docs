/**
 * Resolve free-text color names from the Sigmoi style output to actual hex
 * values for rendering swatches. The model often returns multi-color
 * descriptions ("charcoal, deep olive, dark taupe, or soft black") — we
 * pick the first reasonable token and map it. Fall back to a neutral
 * espresso shade if nothing matches.
 */

const COLORS: Record<string, string> = {
  // Neutrals
  black: "#0E0A07",
  "soft black": "#1A1612",
  "washed black": "#2A2520",
  charcoal: "#3A3835",
  "deep charcoal": "#2E2C2A",
  graphite: "#3F3D3B",
  grey: "#7F7C78",
  gray: "#7F7C78",
  "warm grey": "#8A847B",
  "warm gray": "#8A847B",
  "light grey": "#C8C4BD",
  "light gray": "#C8C4BD",
  white: "#F5F2EC",
  "off-white": "#EFE9DD",
  cream: "#F1E8D8",
  "warm cream": "#EEDEC4",
  "muted cream": "#E8DAC1",
  ivory: "#F2EAD6",
  beige: "#D7C7AC",
  ecru: "#D9CDB8",

  // Browns / earth
  brown: "#5A3F2A",
  "dark brown": "#3D2A1C",
  "matte dark brown": "#3A281B",
  chocolate: "#3B271A",
  "dark chocolate": "#2C1D12",
  tobacco: "#7A4F2F",
  tan: "#A6815C",
  taupe: "#9C8C76",
  "warm taupe": "#A89077",
  mushroom: "#A89A87",
  sand: "#CDB592",
  camel: "#B58E63",
  cognac: "#8C5A33",
  rust: "#9B4A2B",

  // Blues
  navy: "#1B2A3F",
  "dark navy": "#152035",
  "deep navy": "#172339",
  "washed navy": "#2C3A52",
  blue: "#2C5380",
  "dusty blue": "#6A8AA8",
  "slate blue": "#5C7798",
  "blue-gray": "#8898A8",
  "blue-grey": "#8898A8",
  "light blue": "#A9C0D6",

  // Greens
  olive: "#5B5A2E",
  "deep olive": "#454425",
  "muted olive": "#7B7551",
  "dark green": "#293F2E",
  "dark olive": "#3F4B26",
  forest: "#1F3A28",
  sage: "#9CA68C",

  // Reds / warm
  burgundy: "#5C1A22",
  oxblood: "#4D161C",
  plum: "#4A2837",
  "deep plum": "#3A1F2D",
  "muted plum": "#5C384A",
  maroon: "#5A1F1F",
  bordeaux: "#4F1A23",

  // Misc
  stone: "#B5A89A",
  bone: "#E5DDC9",
  "warm stone": "#C0AC91",
  "muted clay": "#A87C68",
  clay: "#9C6951",
  rose: "#B58A85",
  "muted warm tones": "#A89077",
  "soft olive": "#7F7E55",
  "deep brown": "#3F2A1C",
  "brushed gold": "#A28253",
  "muted gunmetal": "#5F5F60",
};

const FALLBACK = "#9F8568"; // muted bronze

/**
 * Pick the first plausible color token from a free-text description.
 * "charcoal, deep olive, or soft black" → "charcoal" → #3A3835.
 */
export function colorToHex(input: string | undefined | null): string {
  if (!input) return FALLBACK;
  const lower = input.toLowerCase().trim();

  // Try the whole string first (handles compound names like "deep navy").
  if (COLORS[lower]) return COLORS[lower];

  // Split on common separators — first token wins.
  const tokens = lower
    .split(/,| or | and |\//)
    .map((s) => s.trim())
    .filter(Boolean);

  for (const tok of tokens) {
    if (COLORS[tok]) return COLORS[tok];
    // Try last word of multi-word token (e.g. "soft warm stone" → "stone")
    const lastWord = tok.split(/\s+/).pop()!;
    if (COLORS[lastWord]) return COLORS[lastWord];
  }

  return FALLBACK;
}

/**
 * Decide whether a swatch needs a light or dark text overlay for legibility.
 * Returns a luminance-aware ink color.
 */
export function inkOn(hex: string): string {
  const c = hex.replace("#", "");
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  // Rec. 709 luminance
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 140 ? "#1F1812" : "#F5F2EC";
}
