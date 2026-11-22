/**
 * Screen-space clustering for HTML pins (no map glyphs). Greedy and deterministic: points are
 * visited in input order; each unclaimed point seeds a cluster that absorbs every unclaimed point
 * within `radius` pixels of the seed. Cluster position is the members' centroid.
 */
export interface ScreenPoint {
  id: string;
  x: number;
  y: number;
}
export interface Cluster {
  /** Stable key: member ids sorted and joined. */
  key: string;
  ids: string[];
  x: number;
  y: number;
}

export function clusterPoints(points: ScreenPoint[], radius = 40): Cluster[] {
  const r2 = radius * radius;
  const claimed = new Set<string>();
  const clusters: Cluster[] = [];
  // Bucket into a grid of `radius` cells so each seed only checks nearby points.
  const order = new Map(points.map((p, i) => [p.id, i]));
  const grid = new Map<string, ScreenPoint[]>();
  const cell = (v: number) => Math.floor(v / radius);
  for (const p of points) {
    const key = `${cell(p.x)}:${cell(p.y)}`;
    const bucket = grid.get(key);
    if (bucket) bucket.push(p);
    else grid.set(key, [p]);
  }
  for (const seed of points) {
    if (claimed.has(seed.id)) continue;
    const members: ScreenPoint[] = [];
    const cx = cell(seed.x),
      cy = cell(seed.y);
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (const p of grid.get(`${cx + dx}:${cy + dy}`) ?? []) {
          if (claimed.has(p.id)) continue;
          const ddx = p.x - seed.x,
            ddy = p.y - seed.y;
          if (ddx * ddx + ddy * ddy <= r2) members.push(p);
        }
    // Keep input order inside the cluster for predictable labels.
    members.sort((a, b) => order.get(a.id)! - order.get(b.id)!);
    for (const m of members) claimed.add(m.id);
    const ids = members.map((m) => m.id);
    clusters.push({
      key: [...ids].sort().join("|"),
      ids,
      x: members.reduce((sum, m) => sum + m.x, 0) / members.length,
      y: members.reduce((sum, m) => sum + m.y, 0) / members.length,
    });
  }
  return clusters;
}
