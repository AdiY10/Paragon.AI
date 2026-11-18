/** Display geometry only. Metric aggregation uses versioned server-side geography. */
export const EARTH_RADIUS_METERS = 6371008.8;
export const METERS_PER_MILE = 1609.344;
const radians = (degrees: number) => (degrees * Math.PI) / 180;
const degrees = (radians: number) => (radians * 180) / Math.PI;

export function circleCoordinates(
  lon: number,
  lat: number,
  miles: number,
  segments = 128,
): number[][] {
  if (
    ![lon, lat, miles].every(Number.isFinite) ||
    Math.abs(lat) > 90 ||
    Math.abs(lon) > 180 ||
    miles <= 0 ||
    segments < 16 ||
    !Number.isInteger(segments)
  )
    throw new Error("Invalid ring geometry");
  const centerLat = radians(lat),
    centerLon = radians(lon),
    distance = (miles * METERS_PER_MILE) / EARTH_RADIUS_METERS;
  const coordinates: number[][] = [];
  for (let step = 0; step < segments; step++) {
    const bearing = (2 * Math.PI * step) / segments;
    const nextLat = Math.asin(
      Math.sin(centerLat) * Math.cos(distance) +
        Math.cos(centerLat) * Math.sin(distance) * Math.cos(bearing),
    );
    const nextLon =
      centerLon +
      Math.atan2(
        Math.sin(bearing) * Math.sin(distance) * Math.cos(centerLat),
        Math.cos(distance) - Math.sin(centerLat) * Math.sin(nextLat),
      );
    coordinates.push([degrees(nextLon), degrees(nextLat)]);
  }
  coordinates.push([...coordinates[0]]);
  return coordinates;
}
