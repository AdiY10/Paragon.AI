CREATE TABLE `geocode_lookups` (
	`owner_id` text NOT NULL,
	`id` text NOT NULL,
	`location_id` text NOT NULL,
	`address_hash` text NOT NULL,
	`checked_at` text NOT NULL,
	`expires_at` text NOT NULL,
	`document` text NOT NULL,
	PRIMARY KEY(`owner_id`, `id`)
);
--> statement-breakpoint
CREATE TABLE `source_checks` (
	`owner_id` text NOT NULL,
	`id` text NOT NULL,
	`location_id` text NOT NULL,
	`checked_at` text NOT NULL,
	`document` text NOT NULL,
	PRIMARY KEY(`owner_id`, `id`)
);
