CREATE TABLE `audits` (
	`owner_id` text NOT NULL,
	`id` text NOT NULL,
	`location_id` text NOT NULL,
	`document` text NOT NULL,
	PRIMARY KEY(`owner_id`, `id`)
);
--> statement-breakpoint
CREATE TABLE `records` (
	`owner_id` text NOT NULL,
	`id` text NOT NULL,
	`version` integer NOT NULL,
	`token` text,
	`document` text NOT NULL,
	PRIMARY KEY(`owner_id`, `id`)
);
--> statement-breakpoint
CREATE TABLE `revisions` (
	`owner_id` text NOT NULL,
	`id` text NOT NULL,
	`location_id` text NOT NULL,
	`document` text NOT NULL,
	PRIMARY KEY(`owner_id`, `id`)
);
