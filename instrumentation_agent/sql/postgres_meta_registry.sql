
CREATE TABLE IF NOT EXISTS meta_features (
  feature_id TEXT PRIMARY KEY,
  -- [{"event_name","journey_order","ch_table","row_count"}, ...]
  journey JSONB NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,              -- ok | failed
  spec_path TEXT NOT NULL,
  events_path TEXT NOT NULL,
  run_id UUID NOT NULL,
  event_count BIGINT NOT NULL DEFAULT 0,
  error TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta_events (
  event_name TEXT PRIMARY KEY,
  feature_id TEXT NOT NULL REFERENCES meta_features(feature_id) ON DELETE CASCADE,
  journey_order INT NOT NULL,
  ch_table TEXT NOT NULL,
  row_count BIGINT NOT NULL DEFAULT 0,
  run_id UUID NOT NULL,
  columns JSONB NOT NULL DEFAULT '{}',
  registered_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_meta_events_feature_journey
  ON meta_events (feature_id, journey_order);
