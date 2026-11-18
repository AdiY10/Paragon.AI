import {
  sqliteTable,
  text,
  integer,
  primaryKey,
} from "drizzle-orm/sqlite-core";
export const records = sqliteTable(
  "records",
  {
    ownerId: text("owner_id").notNull(),
    id: text("id").notNull(),
    version: integer("version").notNull(),
    token: text("token"),
    document: text("document").notNull(),
  },
  (t) => [primaryKey({ columns: [t.ownerId, t.id] })],
);
export const audits = sqliteTable(
  "audits",
  {
    ownerId: text("owner_id").notNull(),
    id: text("id").notNull(),
    locationId: text("location_id").notNull(),
    document: text("document").notNull(),
  },
  (t) => [primaryKey({ columns: [t.ownerId, t.id] })],
);
export const revisions = sqliteTable(
  "revisions",
  {
    ownerId: text("owner_id").notNull(),
    id: text("id").notNull(),
    locationId: text("location_id").notNull(),
    document: text("document").notNull(),
  },
  (t) => [primaryKey({ columns: [t.ownerId, t.id] })],
);
export const geocodeLookups = sqliteTable(
  "geocode_lookups",
  {
    ownerId: text("owner_id").notNull(),
    id: text("id").notNull(),
    locationId: text("location_id").notNull(),
    addressHash: text("address_hash").notNull(),
    checkedAt: text("checked_at").notNull(),
    expiresAt: text("expires_at").notNull(),
    document: text("document").notNull(),
  },
  (t) => [primaryKey({ columns: [t.ownerId, t.id] })],
);
export const sourceChecks = sqliteTable(
  "source_checks",
  {
    ownerId: text("owner_id").notNull(),
    id: text("id").notNull(),
    locationId: text("location_id").notNull(),
    checkedAt: text("checked_at").notNull(),
    document: text("document").notNull(),
  },
  (t) => [primaryKey({ columns: [t.ownerId, t.id] })],
);
