# PostgreSQL Schema Patterns

This appendix is optional. Use it only when the target repository explicitly runs on PostgreSQL and you want concrete physical patterns for bar_history, signal_events, and orders_and_trades. The core skill remains database-neutral.

## General notes

- Use timestamptz for exchange, broker, ingest, and processing timestamps.
- Use numeric for prices, quantities, greeks, or fee fields when rounding rules matter more than raw throughput.
- Keep instrument_identity as first-class columns instead of hiding contract identity inside jsonb.
- Use jsonb for raw_payload, auxiliary refs, or structured rationale that does not justify standalone columns yet.
- Partition only the large append-only fact tables. Keep projections compact and rebuildable.

## bar_history

Recommended columns:

- bar_id uuid primary key
- gateway_name text not null
- asset_kind text not null
- exchange text not null
- underlying_symbol text not null
- venue_symbol text not null
- option_type text null for non-options
- strike numeric null for non-options
- expiry date null for non-options
- multiplier numeric null when the venue does not imply it safely
- interval text not null
- trading_day date not null
- bar_open_time timestamptz not null
- bar_close_time timestamptz not null
- exchange_time timestamptz null
- ingest_time timestamptz not null
- processing_time timestamptz not null
- open numeric not null
- high numeric not null
- low numeric not null
- close numeric not null
- volume numeric null
- turnover numeric null
- open_interest numeric null
- vwap numeric null
- bar_status text not null
- is_final boolean not null default false
- revision integer not null default 0
- source_seq bigint null
- raw_payload jsonb null

Recommended constraints:

- Primary replay uniqueness on gateway_name plus instrument_identity plus interval plus bar_close_time plus revision.
- Check constraint that bar_close_time is strictly after bar_open_time.
- If both bar_status and is_final are stored, keep them consistent with a check constraint or derive is_final in a generated column or view.

Recommended partitioning and indexes:

- Partition by range on bar_close_time. Monthly partitions are a good default for daily and intraday bars; move to weekly partitions only when write volume is very high.
- Replay index on gateway_name, exchange, underlying_symbol, venue_symbol, option_type, strike, expiry, multiplier, interval, and bar_close_time desc.
- Partial index on final bars when warmup queries mostly ignore in-progress bars.
- Warmup or backfill index on trading_day, underlying_symbol, and interval when the repository frequently rehydrates recent history by trading day.

JSONB boundary:

- Keep raw_payload only when vendor mappings are unstable or audit requirements justify it.
- Do not use raw_payload as the only source of OHLCV or identity columns.

## signal_events

Recommended columns:

- signal_event_id uuid primary key
- strategy_name text not null
- gateway_name text null when the evaluation is not bound to one gateway
- evaluation_id text not null
- previous_signal_event_id uuid null
- position_key text null
- exchange text null when the signal is instrument-specific
- underlying_symbol text null when the signal is instrument-specific
- venue_symbol text null when the signal is instrument-specific
- option_type text null when the signal is instrument-specific
- strike numeric null when the signal is instrument-specific
- expiry date null when the signal is instrument-specific
- multiplier numeric null when the signal is instrument-specific
- trigger_type text not null
- decision_outcome text not null
- causation_id text not null
- correlation_id text null
- signal_event_time timestamptz not null
- market_event_time timestamptz null
- ingest_time timestamptz not null
- processing_time timestamptz not null
- config_version text not null
- input_bar_interval text null
- input_bar_close_time timestamptz null
- input_market_refs jsonb null
- rationale jsonb null
- confidence numeric null

Recommended constraints:

- Unique constraint on strategy_name and evaluation_id for idempotent writes.
- Self-reference from previous_signal_event_id to signal_event_id when sequential reasoning matters.
- Check constraint that confidence stays between 0 and 1 when it is present.

Recommended indexes:

- Operator query index on strategy_name and signal_event_time desc.
- Replay or dedupe index on strategy_name and evaluation_id.
- Causality lookup index on causation_id.
- Partial action index on strategy_name, decision_outcome, and signal_event_time desc when operator queries usually exclude no_op and hold outcomes.

Optional projection:

- latest_signal_state can keep one row per strategy_name plus position_key or per strategy_name plus instrument_identity.
- Store latest_signal_event_id, latest_decision_outcome, latest_signal_time, and any restart-critical summary fields.
- Rebuild this projection from signal_events. Do not treat it as the authoritative history.

JSONB boundary:

- Keep the core join and filter fields, such as trigger_type, decision_outcome, config_version, and key market refs, as normal columns.
- Use input_market_refs and rationale for overflow detail that would otherwise make the table unstable.

## orders_and_trades

Treat this slice as three physical tables by default.

### order_events

Recommended columns:

- order_event_id uuid primary key
- strategy_name text not null
- gateway_name text not null
- signal_event_id uuid null
- order_ref text not null
- parent_order_ref text null
- replaced_order_ref text null
- broker_order_id text null
- order_event_type text not null
- order_type text not null
- order_side text not null
- tif text null
- quantity numeric not null
- limit_price numeric null
- stop_price numeric null
- broker_status text null
- event_time timestamptz not null
- broker_time timestamptz null
- ingest_time timestamptz not null
- processing_time timestamptz not null
- source_seq bigint null
- idempotency_key text not null
- raw_payload jsonb null

Recommended constraints and indexes:

- Unique constraint on idempotency_key.
- Replay index on strategy_name, order_ref, and event_time desc.
- External lookup index on gateway_name, broker_order_id, and event_time desc.
- Lineage index on signal_event_id and event_time desc.

### trade_fills

Recommended columns:

- fill_id uuid primary key
- strategy_name text not null
- gateway_name text not null
- signal_event_id uuid null
- order_ref text null when the internal order is not known yet
- broker_order_id text null
- trade_id text not null
- position_key text null
- exchange text null
- underlying_symbol text null
- venue_symbol text null
- option_type text null
- strike numeric null
- expiry date null
- multiplier numeric null
- fill_time timestamptz not null
- trading_day date null
- fill_qty numeric not null
- fill_price numeric not null
- commission numeric null
- fee_currency text null
- liquidity_flag text null
- source_seq bigint null
- raw_payload jsonb null

Recommended constraints and indexes:

- Unique constraint on gateway_name and trade_id.
- Replay index on strategy_name, order_ref, and fill_time desc.
- External lookup index on gateway_name, broker_order_id, and fill_time desc.
- Position reconstruction index on position_key and fill_time desc.

### order_state_projection

Recommended columns:

- strategy_name text not null
- gateway_name text not null
- order_ref text primary key
- latest_order_event_id uuid not null
- broker_order_id text null
- signal_event_id uuid null
- latest_status text not null
- order_type text not null
- order_side text not null
- quantity numeric not null
- filled_qty numeric not null
- remaining_qty numeric not null
- avg_fill_price numeric null
- last_event_time timestamptz not null
- last_fill_time timestamptz null
- projection_updated_at timestamptz not null

Recommended indexes:

- Working-set index on latest_status and last_event_time desc.
- Partial working-order index when most operator queries focus on submitted, working, replace_requested, cancel_requested, or partially_filled rows.

Operational notes:

- Keep the lineage chain explicit as signal_event_id -> order_ref -> broker_order_id -> trade_id.
- Model partial fills as multiple trade_fills rows. Do not collapse them into one mutable order row.
- Keep raw_payload on order_events and trade_fills only. Do not store raw_payload on order_state_projection.
- Partition order_events by event_time and trade_fills by fill_time when event volume is high enough to justify it.
