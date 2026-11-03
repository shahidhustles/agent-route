import { z } from "zod";

/** GeoJSON geometry types we render on the map (excludes GeometryCollection). */
const geometryTypeEnum = z.enum([
  "Point",
  "LineString",
  "Polygon",
  "MultiPoint",
  "MultiLineString",
  "MultiPolygon",
]);

/**
 * One GeoJSON Feature — must not be `{}`. Requires geometry.type + coordinates
 * so models cannot satisfy the tool with empty feature objects.
 * Structured for Zod → JSON Schema (AI SDK tools).
 */
const geoJsonFeatureSchema = z
  .object({
    geometry: z
      .object({
        /**
         * Point: [lng, lat]; LineString / MultiPoint: Position[];
         * Polygon / MultiLineString / MultiPolygon: nested rings / lines per GeoJSON.
         */
        coordinates: z.array(z.unknown()).min(1),
        type: geometryTypeEnum,
      })
      .passthrough(),
    properties: z.record(z.string(), z.unknown()).optional(),
    type: z.literal("Feature"),
  })
  .passthrough();

const featureCollectionSchema = z
  .object({
    features: z.array(geoJsonFeatureSchema).min(1),
    type: z.literal("FeatureCollection"),
  })
  .passthrough();

export const mapArtifactDocumentSchema = z.object({
  collection: featureCollectionSchema,
  format: z.literal("geojson"),
});

/** Tool / API input: same shape as the persisted document. */
export const mapArtifactToolInputSchema = mapArtifactDocumentSchema;

export interface MapArtifactDocument {
  format: "geojson";
  collection: GeoJSON.FeatureCollection;
}

export function stringifyMapArtifactDocument(doc: MapArtifactDocument): string {
  return JSON.stringify(doc);
}

export function parseMapArtifactDocument(
  raw: string
): { ok: true; doc: MapArtifactDocument } | { ok: false; error: string } {
  if (!raw.trim()) {
    return { doc: defaultMapArtifactDocument(), ok: true };
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    const result = mapArtifactDocumentSchema.safeParse(parsed);
    if (!result.success) {
      return { error: result.error.message, ok: false };
    }
    return { doc: result.data as MapArtifactDocument, ok: true };
  } catch {
    return { error: "Invalid JSON", ok: false };
  }
}

/**
 * If the value is a bare GeoJSON FeatureCollection, wrap it as a map artifact document.
 */
export function parseMapArtifactDocumentFlexible(
  raw: string
): MapArtifactDocument {
  const strict = parseMapArtifactDocument(raw);
  if (strict.ok) {
    return strict.doc;
  }
  const trimmed = raw.trim();
  if (!trimmed) {
    return defaultMapArtifactDocument();
  }
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (
      parsed &&
      typeof parsed === "object" &&
      "format" in parsed &&
      (parsed as { format?: string }).format === "geojson" &&
      "collection" in parsed &&
      (parsed as { collection?: unknown }).collection &&
      typeof (parsed as { collection: unknown }).collection === "object"
    ) {
      const col = (parsed as { collection: GeoJSON.FeatureCollection })
        .collection;
      if (col.type === "FeatureCollection" && Array.isArray(col.features)) {
        const filtered = col.features.filter(
          (f) => geoJsonFeatureSchema.safeParse(f).success
        );
        if (filtered.length > 0) {
          return {
            collection: { ...col, features: filtered },
            format: "geojson",
          };
        }
      }
    }
    if (
      parsed &&
      typeof parsed === "object" &&
      "type" in parsed &&
      parsed.type === "FeatureCollection" &&
      "features" in parsed &&
      Array.isArray((parsed as GeoJSON.FeatureCollection).features)
    ) {
      const fc = parsed as GeoJSON.FeatureCollection;
      const filtered = fc.features.filter(
        (f) => geoJsonFeatureSchema.safeParse(f).success
      );
      if (filtered.length > 0) {
        return {
          collection: { ...fc, features: filtered },
          format: "geojson",
        };
      }
    }
  } catch {
    // fall through
  }
  return defaultMapArtifactDocument();
}

export function defaultMapArtifactDocument(): MapArtifactDocument {
  return {
    collection: {
      features: [
        {
          geometry: {
            coordinates: [-74.006, 40.7128],
            type: "Point",
          },
          properties: { name: "Example" },
          type: "Feature",
        },
      ],
      type: "FeatureCollection",
    },
    format: "geojson",
  };
}
