/** GeoJSON may arrive with string coords or bad model output — MapLibre rejects NaN. */
export function isValidLngLat(coords: unknown): boolean {
  if (!Array.isArray(coords) || coords.length < 2) {
    return false;
  }
  const lng = Number(coords[0]);
  const lat = Number(coords[1]);
  return Number.isFinite(lng) && Number.isFinite(lat);
}

export function isValidLineStringCoords(coords: unknown): boolean {
  if (!Array.isArray(coords) || coords.length < 2) {
    return false;
  }
  return coords.every((c) => isValidLngLat(c));
}

export function isValidMultiLineStringCoords(coords: unknown): boolean {
  if (!Array.isArray(coords) || coords.length === 0) {
    return false;
  }
  return coords.every((line) => isValidLineStringCoords(line));
}

export interface SplitFeatures {
  points: GeoJSON.Feature<GeoJSON.Point>[];
  lineStrings: GeoJSON.Feature<GeoJSON.LineString>[];
  multiLineStrings: GeoJSON.Feature<GeoJSON.MultiLineString>[];
  polygons: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon>[];
}

export function splitFeatures(
  collection: GeoJSON.FeatureCollection
): SplitFeatures {
  const points: GeoJSON.Feature<GeoJSON.Point>[] = [];
  const lineStrings: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const multiLineStrings: GeoJSON.Feature<GeoJSON.MultiLineString>[] = [];
  const polygons: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon>[] =
    [];

  for (const f of collection.features) {
    if (!f.geometry) {
      continue;
    }
    const g = f.geometry;
    if (g.type === "Point") {
      if (isValidLngLat(g.coordinates)) {
        points.push(f as GeoJSON.Feature<GeoJSON.Point>);
      }
    } else if (g.type === "LineString") {
      if (isValidLineStringCoords(g.coordinates)) {
        lineStrings.push(f as GeoJSON.Feature<GeoJSON.LineString>);
      }
    } else if (g.type === "MultiLineString") {
      if (isValidMultiLineStringCoords(g.coordinates)) {
        multiLineStrings.push(f as GeoJSON.Feature<GeoJSON.MultiLineString>);
      }
    } else if (g.type === "Polygon" || g.type === "MultiPolygon") {
      polygons.push(
        f as GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon>
      );
    }
  }

  return { lineStrings, multiLineStrings, points, polygons };
}

const MAX_NAMES = 4;

function collectFeatureNames(collection: GeoJSON.FeatureCollection): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const f of collection.features) {
    const p = f.properties;
    if (
      p &&
      typeof p === "object" &&
      "name" in p &&
      typeof (p as { name?: unknown }).name === "string"
    ) {
      const n = (p as { name: string }).name.trim();
      if (n.length > 0 && !seen.has(n)) {
        seen.add(n);
        out.push(n);
        if (out.length >= MAX_NAMES) {
          break;
        }
      }
    }
  }
  return out;
}

function buildSummaryParts(split: SplitFeatures): string[] {
  const parts: string[] = [];
  if (split.points.length > 0) {
    parts.push(
      `${split.points.length} stop${split.points.length === 1 ? "" : "s"}`
    );
  }
  const routeCount = split.lineStrings.length + split.multiLineStrings.length;
  if (routeCount > 0) {
    parts.push(`${routeCount} route${routeCount === 1 ? "" : "s"}`);
  }
  if (split.polygons.length > 0) {
    parts.push(
      `${split.polygons.length} area${split.polygons.length === 1 ? "" : "s"}`
    );
  }
  return parts;
}

export interface MapCollectionSummary {
  totalFeatures: number;
  renderableCount: number;
  labeledNames: string[];
  /** e.g. ["3 stops", "2 routes", "1 area"] */
  summaryParts: string[];
  split: SplitFeatures;
}

export function summarizeFeatureCollection(
  collection: GeoJSON.FeatureCollection | undefined
): MapCollectionSummary | null {
  if (!(collection && Array.isArray(collection.features))) {
    return null;
  }
  const split = splitFeatures(collection);
  const renderableCount =
    split.points.length +
    split.lineStrings.length +
    split.multiLineStrings.length +
    split.polygons.length;
  return {
    labeledNames: collectFeatureNames(collection),
    renderableCount,
    split,
    summaryParts: buildSummaryParts(split),
    totalFeatures: collection.features.length,
  };
}

export function formatMapToolSummaryLine(
  summary: MapCollectionSummary
): string {
  if (summary.summaryParts.length === 0) {
    return `${summary.totalFeatures} feature${summary.totalFeatures === 1 ? "" : "s"}`;
  }
  return summary.summaryParts.join(" · ");
}
