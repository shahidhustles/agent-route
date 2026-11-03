import mermaid from "mermaid";
import type { MermaidConfig } from "mermaid";

const HEX_COLOR = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i;
const RGB_OR_HSL = /^(?:rgb|hsl)a?\(/i;
/** Mermaid's parser rejects wide-gamut CSS serializations. */
const WIDE_GAMUT_SERIAL = /lab\(|oklch\(|lch\(|color\(/i;

function normalizeColorWithCanvas(raw: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return null;
  }
  try {
    ctx.fillStyle = raw;
    const out = ctx.fillStyle;
    if (typeof out !== "string") {
      return null;
    }
    if (!WIDE_GAMUT_SERIAL.test(out)) {
      return out;
    }
  } catch {
    return null;
  }
  return null;
}

function normalizeColorWithDomProbe(raw: string): string | null {
  if (typeof document === "undefined" || !document.body) {
    return null;
  }
  const el = document.createElement("div");
  el.style.cssText =
    "position:absolute;left:-9999px;top:0;width:1px;height:1px;opacity:0;pointer-events:none;";
  document.body.append(el);
  el.style.color = raw;
  const resolved = getComputedStyle(el).color;
  document.body.removeChild(el);
  if (!resolved || resolved === "rgba(0, 0, 0, 0)") {
    return null;
  }
  if (!WIDE_GAMUT_SERIAL.test(resolved)) {
    return resolved;
  }
  return normalizeColorWithCanvas(resolved);
}

/**
 * Mermaid / D3 only accept hex, rgb, hsl. Browsers may expose `lab()` / `oklch()`
 * from `getComputedStyle` — normalize via Canvas `fillStyle` (returns hex/rgb).
 */
export function resolveCssColorForMermaid(
  value: string,
  fallback: string
): string {
  if (typeof document === "undefined") {
    return fallback;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return fallback;
  }
  if (HEX_COLOR.test(trimmed) || RGB_OR_HSL.test(trimmed)) {
    return trimmed;
  }

  const fromCanvas = normalizeColorWithCanvas(trimmed);
  if (fromCanvas) {
    return fromCanvas;
  }

  const fromProbe = normalizeColorWithDomProbe(trimmed);
  if (fromProbe) {
    return fromProbe;
  }

  return fallback;
}

/** Read a CSS custom property from `:root` (for shadcn tokens). */
export function readCssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") {
    return fallback;
  }
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return raw || fallback;
}

export function resolveDarkMode(): boolean {
  if (typeof document === "undefined") {
    return false;
  }
  return (
    document.documentElement.classList.contains("dark") ||
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function readBodyFontFamily(): string {
  if (typeof document === "undefined") {
    return "ui-sans-serif, system-ui, sans-serif";
  }
  return (
    getComputedStyle(document.body).fontFamily ||
    "ui-sans-serif, system-ui, sans-serif"
  );
}

/**
 * Mermaid config aligned with app CSS variables (light/dark) plus flowchart spacing defaults.
 */
export function buildMermaidConfig(): MermaidConfig {
  const isDark = resolveDarkMode();
  const bg = resolveCssColorForMermaid(
    readCssVar("--background", ""),
    isDark ? "hsl(0 0% 3.9%)" : "hsl(0 0% 100%)"
  );
  const fg = resolveCssColorForMermaid(
    readCssVar("--foreground", ""),
    isDark ? "hsl(0 0% 98%)" : "hsl(0 0% 3.9%)"
  );
  const border = resolveCssColorForMermaid(
    readCssVar("--border", ""),
    isDark ? "hsl(240 3.7% 15.9%)" : "hsl(240 5.9% 90%)"
  );
  const card = resolveCssColorForMermaid(
    readCssVar("--card", ""),
    isDark ? "hsl(0 0% 3.9%)" : "hsl(0 0% 100%)"
  );
  const primary = resolveCssColorForMermaid(
    readCssVar("--primary", ""),
    isDark ? "hsl(0 0% 98%)" : "hsl(240 5.9% 10%)"
  );
  const primaryFg = resolveCssColorForMermaid(
    readCssVar("--primary-foreground", ""),
    isDark ? "hsl(240 5.9% 10%)" : "hsl(0 0% 98%)"
  );
  const muted = resolveCssColorForMermaid(
    readCssVar("--muted", ""),
    isDark ? "hsl(240 3.7% 15.9%)" : "hsl(240 4.8% 95.9%)"
  );
  const mutedFg = resolveCssColorForMermaid(
    readCssVar("--muted-foreground", ""),
    isDark ? "hsl(240 5% 64.9%)" : "hsl(240 3.8% 46.1%)"
  );
  const fontFamily = readBodyFontFamily();

  return {
    flowchart: {
      curve: "basis",
      // Plain SVG text. HTML labels let a label such as <img src=...> become a real element that the browser fetches.
      htmlLabels: false,
      nodeSpacing: 56,
      padding: 16,
      rankSpacing: 56,
      useMaxWidth: true,
    },
    htmlLabels: false,
    securityLevel: "strict",
    startOnLoad: false,
    theme: isDark ? "dark" : "default",
    themeVariables: {
      background: bg,
      clusterBkg: muted,
      clusterBorder: border,
      edgeLabelBackground: isDark ? "hsl(240 5.9% 10%)" : "hsl(240 4.8% 95.9%)",
      fontFamily,
      lineColor: mutedFg,
      mainBkg: card,
      primaryBorderColor: mutedFg,
      primaryColor: primary,
      primaryTextColor: fg,
      secondaryColor: muted,
      secondaryTextColor: mutedFg,
      tertiaryColor: muted,
      textColor: fg,
      titleColor: fg,
    },
  };
}

export function applyMermaidConfig(): void {
  mermaid.initialize(buildMermaidConfig());
}

/** Solid color for rasterizing SVG to PNG (matches page background token). */
export function canvasBackgroundForExport(): string {
  const isDark = resolveDarkMode();
  return resolveCssColorForMermaid(
    readCssVar("--background", ""),
    isDark ? "#0a0a0a" : "#ffffff"
  );
}
