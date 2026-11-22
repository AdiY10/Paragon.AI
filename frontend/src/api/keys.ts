/** TanStack Query keys, in one place so invalidation stays consistent. */
export const keys = {
  session: ["session"] as const,
  locations: ["locations"] as const,
  location: (id: string) => ["location", id] as const,
  analysis: (id: string) => ["analysis", id] as const,
  analyses: ["analyses"] as const,
  signals: (status = "active") => ["signals", status] as const,
  sources: ["sources"] as const,
  compare: (ids: string[]) => ["compare", ids.join(",")] as const,
  history: (id: string) => ["history", id] as const,
};
