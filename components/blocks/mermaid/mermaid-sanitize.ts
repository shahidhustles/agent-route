/**
 * Repairs common invalid Mermaid emitted by LLMs before render/export.
 * Mermaid attribute syntax is `type name KEY` (e.g. `string id PK`), not `type PK id, id2`.
 */

const FENCE_OPEN = /^```(?:mermaid)?\s*\n?/i;
const FENCE_CLOSE = /\n?```\s*$/;

const SMART_QUOTES: Record<string, string> = {
  "\u2018": "'",
  "\u2019": "'",
  "\u201C": '"',
  "\u201D": '"',
};

function normalizeQuotes(source: string): string {
  let out = source;
  for (const [from, to] of Object.entries(SMART_QUOTES)) {
    out = out.split(from).join(to);
  }
  return out;
}

function stripMarkdownFences(source: string): string {
  let out = source.trim();
  if (FENCE_OPEN.test(out)) {
    out = out.replace(FENCE_OPEN, "");
  }
  if (FENCE_CLOSE.test(out)) {
    out = out.replace(FENCE_CLOSE, "");
  }
  return out.trim();
}

function trailingComment(line: string): string {
  const match = line.match(/(\s+"[^"]*")\s*$/);
  return match?.[1] ?? "";
}

function lineIndent(line: string): string {
  return line.match(/^\s*/)?.[0] ?? "";
}

/**
 * Expand invalid ER attribute lines such as `string PK post_id, tag`.
 */
function fixErAttributeLine(line: string): string[] {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("%%")) {
    return [line];
  }

  const indent = lineIndent(line);
  const comment = trailingComment(trimmed);

  const compositePk = trimmed.match(
    /^(\w+)\s+PK\s+([\w]+(?:\s*,\s*[\w]+)+)\s*$/
  );
  if (compositePk) {
    const [, type, namesList] = compositePk;
    const names = namesList.split(/\s*,\s*/).filter(Boolean);
    return names.map((name) => `${indent}${type} ${name} PK${comment}`);
  }

  const pkOnlyComposite = trimmed.match(/^PK\s+([\w]+(?:\s*,\s*[\w]+)+)\s*$/);
  if (pkOnlyComposite) {
    const names = pkOnlyComposite[1].split(/\s*,\s*/).filter(Boolean);
    return names.map((name) => `${indent}${name} PK${comment}`);
  }

  const singleWrongOrder = trimmed.match(/^(\w+)\s+PK\s+(\w+)\s*$/);
  if (singleWrongOrder) {
    const [, type, name] = singleWrongOrder;
    return [`${indent}${type} ${name} PK${comment}`];
  }

  const compositeFk = trimmed.match(
    /^(\w+)\s+FK\s+([\w]+(?:\s*,\s*[\w]+)+)\s*$/
  );
  if (compositeFk) {
    const [, type, namesList] = compositeFk;
    const names = namesList.split(/\s*,\s*/).filter(Boolean);
    return names.map((name) => `${indent}${type} ${name} FK${comment}`);
  }

  const fkOnlyComposite = trimmed.match(/^FK\s+([\w]+(?:\s*,\s*[\w]+)+)\s*$/);
  if (fkOnlyComposite) {
    const names = fkOnlyComposite[1].split(/\s*,\s*/).filter(Boolean);
    return names.map((name) => `${indent}${name} FK${comment}`);
  }

  const singleFkWrongOrder = trimmed.match(/^(\w+)\s+FK\s+(\w+)\s*$/);
  if (singleFkWrongOrder) {
    const [, type, name] = singleFkWrongOrder;
    return [`${indent}${type} ${name} FK${comment}`];
  }

  if (/\bPRIMARY\s+KEY\b/i.test(trimmed)) {
    return [line.replaceAll(/\bPRIMARY\s+KEY\b/gi, "PK")];
  }

  if (/\bFOREIGN\s+KEY\b/i.test(trimmed)) {
    return [line.replaceAll(/\bFOREIGN\s+KEY\b/gi, "FK")];
  }

  return [line];
}

function fixErDiagramAttributes(source: string): string {
  return source
    .split("\n")
    .flatMap((line) => fixErAttributeLine(line))
    .join("\n");
}

/** Quote flowchart node labels that contain parentheses when unquoted. */
function quoteRiskyFlowchartLabels(source: string): string {
  const firstLine = source.trim().split("\n")[0]?.trim() ?? "";
  if (!/^(?:flowchart|graph)\s/i.test(firstLine)) {
    return source;
  }

  return source.replaceAll(
    /(\b[\w-]+)\[([^\]"]*\([^^\]"]*)[^\]]*\]/g,
    (match, id: string, label: string) => {
      if (label.startsWith('"') || label.endsWith('"')) {
        return match;
      }
      const escaped = label.replaceAll('"', '\\"');
      return `${id}["${escaped}"]`;
    }
  );
}

/**
 * Normalize diagram type aliases models often mix up.
 */
function normalizeDiagramHeader(source: string): string {
  const lines = source.split("\n");
  let headerFixed = false;

  const normalized = lines.map((line) => {
    if (headerFixed) {
      return line;
    }
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("%%")) {
      return line;
    }
    headerFixed = true;
    if (/^graph\s+(TD|TB|LR|RL|BT)\b/i.test(trimmed)) {
      return line.replace(/^graph\b/i, "flowchart");
    }
    return line;
  });

  return normalized.join("\n");
}

export function sanitizeMermaidSource(source: string): string {
  if (!source.trim()) {
    return source;
  }

  let out = stripMarkdownFences(source);
  out = normalizeQuotes(out);
  out = normalizeDiagramHeader(out);
  if (/^erDiagram\b/im.test(out)) {
    out = fixErDiagramAttributes(out);
  }
  out = quoteRiskyFlowchartLabels(out);
  return out.trim();
}
