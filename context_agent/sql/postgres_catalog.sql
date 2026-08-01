-- AgentHouse catalog (minimal) — see context_agent/TABLES.md
-- Applied by: python -m context_agent.scripts.init_schema  (or scripts/init_schema.py)

CREATE TABLE IF NOT EXISTS meta_objects (
    name            TEXT NOT NULL PRIMARY KEY,
    feature_id      TEXT,
    kind            TEXT NOT NULL CHECK (kind IN ('raw', 'aggregate', 'mv', 'view')),
    engine          TEXT,
    order_by        TEXT,
    partition_by    TEXT,
    source          TEXT,
    target          TEXT,
    purpose         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta_events (
    feature_id      TEXT NOT NULL,
    event_name      TEXT NOT NULL,
    object_name     TEXT NOT NULL REFERENCES meta_objects (name),
    funnel_stage    INT NOT NULL DEFAULT 0,
    sample_count    BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_id, event_name)
);

CREATE TABLE IF NOT EXISTS meta_fields (
    feature_id      TEXT NOT NULL,
    event_name      TEXT NOT NULL,
    field_path      TEXT NOT NULL,
    column_name     TEXT NOT NULL,
    inferred_type   TEXT NOT NULL,
    null_rate       REAL NOT NULL DEFAULT 0,
    example_values  JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_id, event_name, field_path),
    FOREIGN KEY (feature_id, event_name)
        REFERENCES meta_events (feature_id, event_name)
);

CREATE TABLE IF NOT EXISTS context_versions (
    context_version TEXT NOT NULL PRIMARY KEY,
    parent_version  TEXT REFERENCES context_versions (context_version),
    source          TEXT NOT NULL,
    feature_id      TEXT,
    is_current      BOOLEAN NOT NULL DEFAULT false,
    summary         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS context_versions_one_current
    ON context_versions (is_current)
    WHERE is_current = true;

CREATE TABLE IF NOT EXISTS context_items (
    context_version TEXT NOT NULL REFERENCES context_versions (context_version),
    kind            TEXT NOT NULL CHECK (
        kind IN ('entity', 'metric', 'join', 'funnel_step', 'issue', 'contradiction')
    ),
    item_key        TEXT NOT NULL,
    label           TEXT,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (context_version, kind, item_key)
);

CREATE INDEX IF NOT EXISTS meta_events_object_name_idx ON meta_events (object_name);
CREATE INDEX IF NOT EXISTS meta_fields_column_name_idx ON meta_fields (column_name);
CREATE INDEX IF NOT EXISTS context_items_kind_idx ON context_items (context_version, kind);
