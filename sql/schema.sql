-- 311 Pulse: PostgreSQL schema for Toronto 311 service requests.
--
-- Shape: one fact table (requests) pointing at small lookup tables (wards,
-- divisions, sections, request_types), plus a loads table that records each
-- yearly load. The design follows the profiling findings in NOTES.md:
--
-- * There's no request ID in the source, and some rows are genuine exact
--   duplicates. So requests get a surrogate key, and reloads replace a whole
--   source_year inside one transaction instead of upserting row by row.
-- * The city uses placeholders ("Unknown", "Intersection") instead of blanks.
--   The transform turns those into NULLs before they reach these tables.
--
-- Everything runs in one transaction, so a failed apply leaves no half-built
-- schema behind.

BEGIN;

-- The 25 city wards. The key is the official ward number (01 to 25), which
-- is stable and meaningful, so a surrogate key would add nothing.
CREATE TABLE wards (
    ward_id smallint PRIMARY KEY CHECK (ward_id BETWEEN 1 AND 25),
    name    text     NOT NULL UNIQUE
);

-- City divisions, kept exactly as published. The 2025 reorganization means
-- "Parks, Forestry & Recreation" and its successors are separate rows.
CREATE TABLE divisions (
    division_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text     NOT NULL UNIQUE
);

-- Sections belong to a division. The same section name can appear under two
-- divisions ("Forestry Operations" moved in 2025), so names are unique only
-- within a division. UNIQUE (division_id, section_id) exists so requests can
-- reference the pair with a composite foreign key.
CREATE TABLE sections (
    section_id  smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    division_id smallint NOT NULL REFERENCES divisions,
    name        text     NOT NULL,
    UNIQUE (division_id, name),
    UNIQUE (division_id, section_id)
);

-- What was requested, e.g. "Road - Pot hole". About 900 types. A few appear
-- under more than one division, so types are not tied to a division.
CREATE TABLE request_types (
    request_type_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text    NOT NULL UNIQUE
);

-- One row per yearly load: which file, when, and how many rows it produced.
-- Lets us trace any request back to the load that inserted it.
CREATE TABLE loads (
    load_id            integer     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_year        smallint    NOT NULL,
    file_last_modified timestamp,              -- from the Open Data API
    row_count          integer     NOT NULL CHECK (row_count >= 0),
    loaded_at          timestamptz NOT NULL DEFAULT now()
);

-- One row per 311 service request.
CREATE TABLE requests (
    -- Surrogate key: the source has no request ID. Values change on every
    -- reload of a year, so nothing outside the database should store them.
    request_id      bigint    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_id         integer   NOT NULL REFERENCES loads,

    -- The unit of reloading. Every row's date falls inside its file's year,
    -- and the CHECK keeps it that way.
    source_year     smallint  NOT NULL,

    -- Toronto local time, as published. The source has no time zone, so this
    -- stays a plain timestamp rather than guessing at DST offsets.
    created_at      timestamp NOT NULL,

    -- NULL means the city recorded "Unknown". Any other new value fails the
    -- load on purpose, so a change in the city's data gets noticed.
    status          text CHECK (status IN
                        ('New', 'In Progress', 'Completed', 'Closed', 'Cancelled')),

    -- Location: a postal code prefix (forward sortation area, e.g. "M5V"), or
    -- two cross streets when the request is at an intersection.
    postal_fsa      char(3)   CHECK (postal_fsa ~ '^M[0-9][A-Z]$'),
    street_1        text,
    street_2        text,

    ward_id         smallint  REFERENCES wards,
    request_type_id integer   REFERENCES request_types,
    division_id     smallint  REFERENCES divisions,
    section_id      smallint,

    CHECK (EXTRACT(YEAR FROM created_at) = source_year),

    -- division_id is stored directly so "requests per division" needs no
    -- extra join. The composite key guarantees it agrees with the section.
    FOREIGN KEY (division_id, section_id)
        REFERENCES sections (division_id, section_id),
    -- A composite foreign key isn't checked when one side is NULL, so a
    -- section without a division would slip through without this.
    CHECK (section_id IS NULL OR division_id IS NOT NULL)
);

-- Reloading a year starts with DELETE ... WHERE source_year = ?, which would
-- scan all 1.8 million rows without this index. Indexes for the analytics
-- queries are added in task 9, after timing those queries without them.
CREATE INDEX requests_source_year_idx ON requests (source_year);

COMMIT;
