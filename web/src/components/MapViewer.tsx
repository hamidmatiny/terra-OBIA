import { useCallback, useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { FeatureCollection, GeoFeature } from "../types/api";
import { coverColor } from "../lib/colors";

interface MapViewerProps {
  features: FeatureCollection | null;
  selectedObjectId: number | null;
  onSelectFeature: (feature: GeoFeature | null) => void;
}

function enrichFeatures(fc: FeatureCollection): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: fc.features.map((f) => {
      const cover = String(f.properties.cover_type ?? "unknown");
      const confidence = Number(f.properties.confidence ?? 0);
      return {
        ...f,
        properties: {
          ...f.properties,
          _fillColor: coverColor(cover, confidence),
        },
      };
    }),
  };
}

export function MapViewer({
  features,
  selectedObjectId,
  onSelectFeature,
}: MapViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onSelectRef = useRef(onSelectFeature);
  onSelectRef.current = onSelectFeature;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm",
          },
        ],
      },
      center: [-66.5, 46.5],
      zoom: 10,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      map.addSource("segments", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: "segments-fill",
        type: "fill",
        source: "segments",
        paint: {
          "fill-color": ["get", "_fillColor"],
          "fill-opacity": 0.55,
        },
      });

      map.addLayer({
        id: "segments-outline",
        type: "line",
        source: "segments",
        paint: {
          "line-color": "#1e293b",
          "line-width": 1,
        },
      });

      map.addLayer({
        id: "segments-selected",
        type: "line",
        source: "segments",
        filter: ["==", ["get", "object_id"], -1],
        paint: {
          "line-color": "#f59e0b",
          "line-width": 3,
        },
      });
    });

    map.on("click", "segments-fill", (e) => {
      const feature = e.features?.[0];
      if (!feature) return;
      onSelectRef.current(feature as unknown as GeoFeature);
    });

    map.on("mouseenter", "segments-fill", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "segments-fill", () => {
      map.getCanvas().style.cursor = "";
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const fitToFeatures = useCallback((fc: FeatureCollection) => {
    const map = mapRef.current;
    if (!map || fc.features.length === 0) return;

    const bounds = new maplibregl.LngLatBounds();
    for (const feature of fc.features) {
      if (feature.geometry.type === "Polygon") {
        for (const ring of feature.geometry.coordinates) {
          for (const coord of ring) {
            bounds.extend(coord as [number, number]);
          }
        }
      } else if (feature.geometry.type === "MultiPolygon") {
        for (const poly of feature.geometry.coordinates) {
          for (const ring of poly) {
            for (const coord of ring) {
              bounds.extend(coord as [number, number]);
            }
          }
        }
      }
    }
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 48, maxZoom: 16 });
    }
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !features) return;

    const enriched = enrichFeatures(features);
    const source = map.getSource("segments") as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(enriched);
      fitToFeatures(enriched);
    } else {
      map.once("load", () => {
        const s = map.getSource("segments") as maplibregl.GeoJSONSource;
        s?.setData(enriched);
        fitToFeatures(enriched);
      });
    }
  }, [features, fitToFeatures]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setFilter("segments-selected", [
      "==",
      ["get", "object_id"],
      selectedObjectId ?? -1,
    ]);
  }, [selectedObjectId]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full rounded-lg border border-slate-200 shadow-inner"
      data-testid="map-viewer"
    />
  );
}
