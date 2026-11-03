"use client";

import { useEffect, useMemo } from "react";

import { cn } from "@/lib/utils";

import { splitFeatures } from "./geo-summary";
import { parseMapArtifactDocumentFlexible } from "./map-document";
import type { MapArtifactDocument } from "./map-document";
import {
  fitMapToGeoJSON,
  Map,
  MapClusterLayer,
  MapControls,
  MapGeoJsonFillLayer,
  MapMarker,
  MapRoute,
  MarkerContent,
  MarkerLabel,
  MarkerPopup,
  useMap,
} from "./map";

const CLUSTER_POINT_THRESHOLD = 10;

function featureKey(
  feature: GeoJSON.Feature,
  prefix: string,
  index: number
): string {
  if (feature.id !== undefined && feature.id !== null) {
    return `${prefix}-${String(feature.id)}`;
  }
  return `${prefix}-${index}`;
}

/** MapRoute expects 2D pairs; GeoJSON `Position` may include elevation (3+ numbers). */
function toLonLatPairs(positions: GeoJSON.Position[]): [number, number][] {
  const pairs: [number, number][] = [];
  for (const p of positions) {
    pairs.push([p[0], p[1]]);
  }
  return pairs;
}

function lineColorFromProperties(
  properties: GeoJSON.GeoJsonProperties
): string {
  if (
    properties &&
    typeof properties === "object" &&
    "stroke" in properties &&
    typeof (properties as { stroke?: string }).stroke === "string"
  ) {
    return (properties as { stroke: string }).stroke;
  }
  if (
    properties &&
    typeof properties === "object" &&
    "color" in properties &&
    typeof (properties as { color?: string }).color === "string"
  ) {
    return (properties as { color: string }).color;
  }
  return "#4285F4";
}

function MapFitCollection({
  collection,
  compact,
}: {
  collection: GeoJSON.FeatureCollection;
  compact: boolean;
}) {
  const { map, isLoaded } = useMap();
  const serialized = useMemo(() => JSON.stringify(collection), [collection]);

  useEffect(() => {
    if (!(isLoaded && map)) {
      return;
    }
    map.resize();
    const settle = window.setTimeout(() => map.resize(), 250);
    const parsed = JSON.parse(serialized) as GeoJSON.FeatureCollection;
    fitMapToGeoJSON(
      map,
      parsed,
      compact
        ? { duration: 0, maxZoom: 15, padding: 32 }
        : { duration: 450, maxZoom: 15, padding: 48 }
    );
    return () => window.clearTimeout(settle);
  }, [compact, isLoaded, map, serialized]);

  return null;
}

/** Hides the canvas until the map is ready to avoid flash/jump in compact chat previews. */
function CompactPreviewMask({ compact }: { compact: boolean }) {
  const { isLoaded } = useMap();
  if (!compact) {
    return null;
  }
  return (
    <div
      aria-hidden
      className={cn(
        "absolute inset-0 z-30 bg-muted/15 transition-opacity duration-200 ease-out motion-reduce:transition-none",
        isLoaded ? "pointer-events-none opacity-0" : "opacity-100"
      )}
    />
  );
}

export function MapArtifactPreview({
  content,
  className,
  compact = false,
}: {
  content: string;
  className?: string;
  /** Shorter minimum height for inline tool cards (chat). */
  compact?: boolean;
}) {
  const doc: MapArtifactDocument = useMemo(
    () => parseMapArtifactDocumentFlexible(content),
    [content]
  );

  const split = useMemo(() => splitFeatures(doc.collection), [doc.collection]);

  const pointCollection = useMemo(
    (): GeoJSON.FeatureCollection<GeoJSON.Point> => ({
      features: split.points,
      type: "FeatureCollection",
    }),
    [split.points]
  );

  const polygonCollection = useMemo(
    (): GeoJSON.FeatureCollection => ({
      features: split.polygons,
      type: "FeatureCollection",
    }),
    [split.polygons]
  );

  const useCluster = split.points.length >= CLUSTER_POINT_THRESHOLD;

  const shellClass = compact
    ? "relative flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[calc(var(--radius)+2px)]"
    : "relative flex min-h-[min(50dvh,520px)] min-w-0 flex-1 flex-col overflow-hidden rounded-[calc(var(--radius)+2px)]";

  return (
    <div className={cn(shellClass, className)}>
      <Map
        className={
          compact
            ? "pointer-events-none absolute inset-0 h-full min-h-0 w-full select-none [&_.maplibregl-marker]:pointer-events-none [&_.maplibregl-popup]:pointer-events-none"
            : "absolute inset-0 h-full min-h-[320px] w-full"
        }
        interactive={!compact}
      >
        <CompactPreviewMask compact={compact} />
        <MapFitCollection collection={doc.collection} compact={compact} />
        {compact ? null : (
          <MapControls
            position="bottom-right"
            showCompass
            showFullscreen
            showLocate={false}
            showZoom
          />
        )}
        {polygonCollection.features.length > 0 ? (
          <MapGeoJsonFillLayer
            data={polygonCollection}
            interactive={!compact}
          />
        ) : null}
        {split.lineStrings.map((f, i) => (
          <MapRoute
            color={lineColorFromProperties(f.properties)}
            coordinates={toLonLatPairs(f.geometry.coordinates)}
            interactive={!compact}
            key={featureKey(f, "line", i)}
          />
        ))}
        {split.multiLineStrings.flatMap((f, mi) =>
          f.geometry.coordinates.map((coords, li) => (
            <MapRoute
              color={lineColorFromProperties(f.properties)}
              coordinates={toLonLatPairs(coords)}
              interactive={!compact}
              key={`${featureKey(f, "mline", mi)}-${li}`}
            />
          ))
        )}
        {useCluster ? (
          pointCollection.features.length > 0 ? (
            <MapClusterLayer data={pointCollection} />
          ) : null
        ) : (
          split.points.map((f, i) => {
            const [longitude, latitude] = f.geometry.coordinates;
            const name =
              f.properties &&
              typeof f.properties === "object" &&
              "name" in f.properties
                ? String((f.properties as { name?: string }).name ?? "")
                : "";
            const description =
              f.properties &&
              typeof f.properties === "object" &&
              "description" in f.properties
                ? String(
                    (f.properties as { description?: string }).description ?? ""
                  )
                : "";
            return (
              <MapMarker
                key={featureKey(f, "pt", i)}
                latitude={latitude}
                longitude={longitude}
              >
                <MarkerContent>
                  {name ? <MarkerLabel>{name}</MarkerLabel> : null}
                </MarkerContent>
                {description && !compact ? (
                  <MarkerPopup>
                    <p className="max-w-xs text-sm">{description}</p>
                  </MarkerPopup>
                ) : null}
              </MapMarker>
            );
          })
        )}
      </Map>
    </div>
  );
}
