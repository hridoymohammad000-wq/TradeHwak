BEGIN;

CREATE TABLE IF NOT EXISTS bot_settings (
    id smallint PRIMARY KEY CHECK (id = 1),
    settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profit_tracking_state (
    id smallint PRIMARY KEY CHECK (id = 1),
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_state (
    id smallint PRIMARY KEY CHECK (id = 1),
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trade_history (
    id bigserial PRIMARY KEY,
    trade_key text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('open', 'closed')),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history(status);
CREATE INDEX IF NOT EXISTS idx_trade_history_created_at ON trade_history(created_at DESC);

CREATE TABLE IF NOT EXISTS journal (
    id bigserial PRIMARY KEY,
    trade_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scan_logs (
    id bigserial PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scan_logs_created_at ON scan_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS signal_logs (
    id bigserial PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_signal_logs_created_at ON signal_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS execution_logs (
    id bigserial PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_execution_logs_created_at ON execution_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS executed_signal_ids (
    id bigserial PRIMARY KEY,
    signal_id text NOT NULL,
    trade_day date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (signal_id, trade_day)
);
CREATE INDEX IF NOT EXISTS idx_executed_signal_ids_trade_day ON executed_signal_ids(trade_day);

COMMIT;
