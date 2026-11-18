import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import * as maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
maplibregl.setWorkerUrl(workerUrl);
import type { Location, Session } from "./types";
import { circleCoordinates } from "./geography";

export default function LocationMap({
  locations,
  rings = false,
  editPin = false,
  previewOnly = false,
  onPinChange,
}: {
  locations: Location[];
  rings?: boolean;
  editPin?: boolean;
  previewOnly?: boolean;
  onPinChange?: (lat: number, lon: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false),
    [tilesFailed, setTilesFailed] = useState(false);
  const config = useQueryClient().getQueryData<Session>(["session"])?.map;
  const pinned = locations.filter(
    (item) =>
      item.current_revision.lat !== null && item.current_revision.lon !== null,
  );
  // Geometry signature avoids reinitializing the map when unrelated notes change.
  const signature = JSON.stringify(
    pinned.map((item) => [
      item.id,
      item.name,
      item.current_revision.lat,
      item.current_revision.lon,
      item.current_revision.confirmed,
      item.ring_preset,
    ]),
  );
  useEffect(() => {
    if (!host.current || !pinned.length) return;
    delete host.current.dataset.ready;
    delete host.current.dataset.rings;
    setUnavailable(false);
    setTilesFailed(false);
    let map: maplibregl.Map | undefined;
    try {
      const style: StyleSpecification = {
        version: 8,
        sources: config?.tile_url
          ? {
              basemap: {
                type: "raster",
                tiles: [config.tile_url],
                tileSize: 256,
                attribution:
                  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
                maxzoom: 19,
              },
            }
          : {},
        layers: [
          {
            id: "background",
            type: "background",
            paint: { "background-color": "#e8ecdf" },
          },
          ...(config?.tile_url
            ? [
                {
                  id: "basemap",
                  type: "raster" as const,
                  source: "basemap",
                  paint: { "raster-saturation": -0.65, "raster-opacity": 0.9 },
                },
              ]
            : []),
        ],
      };
      map = new maplibregl.Map({
        container: host.current,
        style,
        center: [
          pinned[0].current_revision.lon!,
          pinned[0].current_revision.lat!,
        ],
        zoom: 10,
        attributionControl: { compact: false },
        renderWorldCopies: false,
        cooperativeGestures: true,
      });
      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-right",
      );
      map.addControl(
        new maplibregl.ScaleControl({ unit: "imperial" }),
        "bottom-left",
      );
      map
        .getCanvas()
        .setAttribute(
          "aria-label",
          "Location map. Use arrow keys to pan and plus or minus to zoom. Property links are also available in the list.",
        );
      const bounds = new maplibregl.LngLatBounds();
      for (const item of pinned) {
        const pin = item.current_revision;
        bounds.extend([pin.lon!, pin.lat!]);
        const button = document.createElement("button");
        button.type = "button";
        button.className = `map-marker ${pin.confirmed ? "verified" : ""}`;
        button.setAttribute("aria-label", `Show ${item.name} on map`);
        const popupContent = document.createElement("div");
        popupContent.className = "map-popup";
        const label = document.createElement("strong");
        label.textContent = item.name;
        const detail = document.createElement("p");
        detail.textContent = pin.confirmed
          ? "Team-confirmed pin"
          : `${pin.method.replaceAll("_", " ")} · verify building position`;
        const link = document.createElement("a");
        link.href = `#/locations/${item.id}`;
        link.textContent = "Open property profile →";
        popupContent.append(label, detail);
        if (!previewOnly) popupContent.append(link);
        const marker = new maplibregl.Marker({
          element: button,
          draggable: editPin,
        })
          .setLngLat([pin.lon!, pin.lat!])
          .setPopup(
            new maplibregl.Popup({ offset: 18 }).setDOMContent(popupContent),
          )
          .addTo(map);
        if (editPin)
          marker.on("dragend", () => {
            const point = marker.getLngLat();
            onPinChange?.(point.lat, point.lng);
          });
      }
      if (pinned.length > 1)
        map.fitBounds(bounds, { padding: 65, maxZoom: 12, duration: 0 });
      else
        map.jumpTo({ zoom: editPin ? 17 : previewOnly ? 16 : rings ? 10 : 13 });
      map.on("error", () => setTilesFailed(true));
      map.on("load", () => {
        if (host.current) host.current.dataset.ready = "true";
        if (!rings || !map) return;
        const item = pinned[0],
          pin = item.current_revision;
        const distances = item.ring_preset
          .split("/")
          .map(Number)
          .sort((a, b) => b - a);
        for (const miles of distances) {
          const id = `ring-${miles}`;
          map.addSource(id, {
            type: "geojson",
            data: {
              type: "Feature",
              properties: { miles },
              geometry: {
                type: "Polygon",
                coordinates: [circleCoordinates(pin.lon!, pin.lat!, miles)],
              },
            },
          });
          map.addLayer({
            id: `${id}-fill`,
            type: "fill",
            source: id,
            paint: { "fill-color": "#507849", "fill-opacity": 0.035 },
          });
          map.addLayer({
            id: `${id}-line`,
            type: "line",
            source: id,
            paint: {
              "line-color": "#365e35",
              "line-width": 1.5,
              "line-dasharray": [3, 2],
            },
          });
        }
        if (host.current) host.current.dataset.rings = String(distances.length);
        const largest = distances[0];
        const ringBounds = new maplibregl.LngLatBounds();
        circleCoordinates(pin.lon!, pin.lat!, largest).forEach((point) =>
          ringBounds.extend([point[0], point[1]]),
        );
        map.fitBounds(ringBounds, { padding: 30, duration: 0 });
      });
    } catch {
      setUnavailable(true);
      map?.remove();
      map = undefined;
    }
    return () => map?.remove();
  }, [signature, rings, editPin, previewOnly, config?.tile_url]);
  if (!pinned.length)
    return (
      <div className="map-empty">
        <h3>No pins to display</h3>
        <p>
          Unplaced records remain available in the list. A missing pin is not an
          empty trade area.
        </p>
      </div>
    );
  return (
    <div className="map-wrapper">
      <div
        ref={host}
        className="location-map"
        aria-label={
          rings ? "Property pin and distance rings" : "Portfolio location map"
        }
        role="region"
      />
      {unavailable ? (
        <p className="map-status" role="status">
          Map unavailable: this browser could not initialize WebGL. All records
          remain in the list.
        </p>
      ) : tilesFailed ? (
        <p className="map-status" role="status">
          Basemap tiles unavailable. Pins and distance rings show saved
          coordinates; use the list for property details.
        </p>
      ) : !config?.tile_url ? (
        <p className="map-status">Basemap disabled. Coordinate overlay only.</p>
      ) : null}
      <div className="map-caption">
        <span>
          {pinned.length} placed · {locations.length - pinned.length} missing
          pins
        </span>
        <span>
          {rings
            ? `${pinned[0].ring_preset} mile radii · display only`
            : "Reference pins; ownership and pin confirmation are separate."}
        </span>
      </div>
      <p className="map-privacy">
        {config?.tile_url
          ? "Map tiles: OpenStreetMap. The tile provider receives your IP and viewed map area; no property names or notes are sent."
          : "External tile requests are disabled."}{" "}
        <a
          href="https://www.openstreetmap.org/fixthemap"
          target="_blank"
          rel="noreferrer"
        >
          Report a basemap issue
        </a>
      </p>
    </div>
  );
}
