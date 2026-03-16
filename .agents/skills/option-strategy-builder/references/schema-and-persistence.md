# Schema and Persistence

## TOC

- Modeling principles
- Stable identifiers
- Cross-table vocabulary
- Suggested storage slices
- Bar history deep dive
- Signal events deep dive
- Orders and trades deep dive
- Replay and restart
- Gateway and execution persistence
- Anti-patterns
- Optional PostgreSQL appendix

## Modeling principles

- Model read paths first.
  - Live trading needs low-latency access to current state.
  - Warm restart needs compact and trustworthy recovery data.
  - Replay needs append-only historical facts.
  - Monitoring needs read-optimized projections.
  - Analytics needs causal links across decisions and fills.
- Separate static contract metadata, market facts, derived analytics, execution facts, and restart snapshots.
- Prefer shared market facts over per-strategy copies when multiple strategies can replay from the same normalized inputs.
- Keep exchange time, broker time, ingest time, and processing time distinct when the source provides them.
- Preserve raw payload fragments when upstream mappings are unstable or regulated workflows require auditability.
- Persist expensive or audit-critical derived analytics; recompute cheap deterministic values during replay.
- Use snapshots for recovery, not as a substitute for event history.
- When a slice must support replay and recovery, keep append-only facts and read-optimized projections separate.

## Stable identifiers

Use stable identifiers consistently across schemas, normalized objects, and logs:

- strategy_name
- gateway_name
- exchange
- underlying_symbol
- venue_symbol
- option_type
- strike
- expiry
- multiplier
- trading_day
- event_time
- ingest_time
- signal_event_id
- evaluation_id
- causation_id
- correlation_id
- order_ref
- broker_order_id
- trade_id
- position_key
- trace_id

Treat instrument_identity as the normalized contract identity built from exchange, underlying_symbol, venue_symbol, option_type, strike, expiry, and multiplier.

Do not treat a naked symbol string as enough identity for an option contract when expiry, strike, option type, or venue can change meaning.

## Cross-table vocabulary

- instrument_identity
  - The normalized contract identity used across bars, quotes, signals, orders, fills, positions, and logs. Represent it as explicit columns or a stable value object, not a naked symbol.
- bar_status
  - The normalized lifecycle of a bar, such as building, final, or corrected.
- trigger_type
  - What caused a signal evaluation, such as bar_close, timer, order_callback, trade_callback, or restart_recovery.
- decision_outcome
  - The normalized result of a signal evaluation, such as no_op, hold, open, close, roll, hedge, or blocked.
- evaluation_id
  - The stable identifier for one full signal evaluation cycle, used even when the outcome is no_op or hold.
- causation_id
  - The identifier that points to the fact or workflow step that directly caused the current event.
- correlation_id
  - The identifier that groups related events across a multi-step workflow, retry sequence, or operator-visible episode.
- order_event_type
  - The normalized label for an order lifecycle event, such as submitted, acknowledged, partially_filled, replaced, canceled, rejected, or expired.
- order_state_projection
  - A current-state view rebuilt from append-only order events and trade fills for restart or operator queries.

## Suggested storage slices

Use these as design slices, not mandatory table names.

- Contract master
  - Store listed option metadata and lifecycle state.
  - Example fields: symbol identity, underlying, strike, expiry, option type, multiplier, tick size, listed_at, delisted_at, status, raw_payload.
- Chain snapshots
  - Store point-in-time contract universe views for an underlying and expiry set.
  - Example fields: underlying, snapshot_time, atm_reference, expiry_set, contracts_payload.
- Market quotes or ticks
  - Store append-only top-of-book or depth events.
  - Example fields: symbol identity, bid and ask prices, bid and ask volumes, last price, volume, open interest, depth payload, raw_payload.
- Bar history
  - Store shared replay and indicator warmup inputs for both underlyings and option contracts.
  - Example fields: instrument_identity, asset_kind, interval, bar_open_time, bar_close_time, trading_day, OHLCV, turnover, open_interest, bar_status, revision.
- Pricing snapshots
  - Store theoretical values, IV, greeks, and model metadata when these outputs matter beyond the current tick.
- Volatility surface snapshots
  - Store fitted surface parameters or dense surface points when they affect selection, risk, or replay.
- Selection runs
  - Store which candidates were considered, how they were scored, and which ones were selected.
- Signal events
  - Store append-only evaluation logs, including no_op or hold outcomes when replay reasoning matters.
  - Example fields: strategy_name, evaluation_id, trigger_type, decision_outcome, causation_id, previous_signal_event_id, rationale, confidence, input_market_refs, config_version.
- Orders and trades
  - Treat this as a logical slice that often maps to order_events, trade_fills, and order_state_projection tables.
  - Example fields: order_ref, broker_order_id, signal_event_id, order_event_type, order_type, status, replace_chain_refs, trade_id, fill_qty, fill_price, raw_payload.
- Position snapshots
  - Store current exposure and relevant valuation context for recovery and analytics.
- Strategy-state snapshots
  - Store compact restart state with an explicit schema version.

## Bar history deep dive

- Treat bar_history as normalized market facts shared across strategies. Do not duplicate the same vendor bar per strategy unless the strategy produces its own synthetic bars.
- The core identity should combine gateway_name, instrument_identity, interval, and bar_close_time. Add revision when vendor corrections can rewrite a previously published bar.
- Keep time fields explicit:
  - bar_open_time and bar_close_time define the market interval.
  - exchange_time records the source market timestamp when available.
  - ingest_time records when the system received the bar.
  - processing_time records when downstream normalization persisted it.
- Keep lifecycle and ordering explicit:
  - bar_status captures building, final, or corrected.
  - is_final is an optional convenience flag derived from bar_status when the codebase benefits from a fast predicate.
  - revision increments when the same logical bar is corrected.
  - source_seq stores the upstream sequence number when available to help deduplicate or order same-timestamp events.
- Carry asset_kind so the same slice can cover underlyings and option contracts without overloading naked symbols.
- Do not include strategy_name in the core uniqueness rule when the bar is shared market data rather than strategy-local output.
- If you must keep raw vendor payloads, do it for unstable mappings or regulated audit paths. Do not make raw JSON the only source of OHLCV truth.
- PostgreSQL note: use time-based range partitioning on bar_close_time and a replay index on gateway_name, instrument_identity, interval, and bar_close_time desc. See [postgresql-schema-patterns.md](postgresql-schema-patterns.md) for concrete patterns.

## Signal events deep dive

- Treat signal_events as append-only evaluation logs rather than only executed trade intents.
- In replay-first systems, record every evaluation, including no_op or hold outcomes, so later exits, rolls, or hedges can reconstruct why nothing happened earlier.
- The core identity is strategy_name plus evaluation_id. Use signal_event_id as the immutable row ID and previous_signal_event_id to chain related decisions when stateful reasoning matters.
- Keep trigger and causality explicit:
  - trigger_type names bar_close, timer, order_callback, trade_callback, restart_recovery, or similar clocks.
  - causation_id identifies the direct upstream fact or workflow step.
  - correlation_id groups multi-step workflows or retries that belong to one operator-visible episode.
- Keep decision fields explicit:
  - decision_outcome stores no_op, hold, open, close, roll, hedge, blocked, or similar outcomes.
  - config_version stores the strategy or parameter version used to evaluate the signal.
  - rationale and confidence explain the decision when explainability matters.
- Keep market inputs traceable:
  - Store first-class refs for the most important market drivers, such as bar interval plus bar_close_time or quote event_time.
  - Use input_market_refs only for supplementary references that do not justify standalone columns yet.
- Preserve lineage to execution by carrying signal_event_id forward into order instructions. The common chain is signal_event_id -> order_ref -> broker_order_id -> trade_id.
- Optional projection: maintain latest_signal_state for fast restart or operator queries, but rebuild it from signal_events instead of treating it as the authoritative history.
- PostgreSQL note: index strategy_name plus signal_event_time desc for operator queries and strategy_name plus evaluation_id for idempotent writes. See [postgresql-schema-patterns.md](postgresql-schema-patterns.md) for concrete patterns.

## Orders and trades deep dive

- Treat orders_and_trades as a logical slice, not automatically one physical table.
- Default split:
  - order_events stores append-only lifecycle facts from internal submission through broker callbacks.
  - trade_fills stores append-only fill facts keyed by trade_id or the broker fill identifier.
  - order_state_projection stores the current reconstructed order state for restart and operator views.
- Keep identifiers and chains explicit:
  - order_ref is the stable internal order instruction key.
  - broker_order_id is the external broker key and may appear after submission.
  - signal_event_id links execution back to the evaluated signal.
  - parent_order_ref, replaced_order_ref, or similar fields keep replace and cancel chains visible.
- Model lifecycle explicitly:
  - order_event_type should cover submitted, acknowledged, working, partially_filled, fully_filled, replace_requested, replaced, cancel_requested, canceled, rejected, expired, and similar broker states.
  - order_type is an order instruction attribute such as market, limit, stop, or stop_limit. It is not the primary fact slice unless a project explicitly needs a governance dimension table.
- Model fills separately from order state:
  - Keep partial fills as separate trade facts.
  - Do not overwrite a single order row with the latest cumulative fill and lose intermediate events.
- Deduplicate with stable keys:
  - Prefer a normalized idempotency key built from gateway_name, external identifier, order_event_type, event_time, and source_seq when the source provides them.
  - Fall back to internal order_ref plus a stable event fingerprint only when the gateway cannot provide better keys.
- Keep raw_payload on order_events and trade_fills when audit or mapping-debug needs justify it. Do not store raw_payload on order_state_projection.
- PostgreSQL note: index working-state rows separately from historical replay paths, and partition large append-only event tables by event_time. See [postgresql-schema-patterns.md](postgresql-schema-patterns.md) for concrete patterns.

## Replay and restart

- Capture the minimum state needed to resume safely:
  - recent bars for indicator warmup
  - current contract universe for tracked underlyings
  - working orders and open positions
  - latest relevant decision context, including no_op, hold, or blocked outcomes when exits depend on prior reasoning
  - strategy parameters or config version used to build current state
- Use full replay when correctness depends on the whole event path.
- Reuse shared bar_history across strategies whenever the normalized market inputs are identical.
- Keep order_state_projection and other recovery projections separate from append-only order_events and trade_fills.
- Use snapshots when startup speed matters more and the snapshot is trustworthy.
- Keep snapshot contents versioned.
- Treat replay inputs, restart state, and monitoring projections as separate concerns.
- If PostgreSQL is the target, use [postgresql-schema-patterns.md](postgresql-schema-patterns.md) as an optional physical-design appendix, not a portability requirement.

## Gateway and execution persistence

- Normalize broker and vendor payloads before they reach repositories used by the rest of the system.
- Preserve both internal IDs and external IDs.
- Keep the causal chain visible:
  - contract discovery
  - selection result
  - signal_event_id
  - order_ref
  - broker_order_id
  - trade_id
  - position update
- Deduplicate duplicate callbacks using stable keys such as gateway name, external ID, event time, and status.
- Model partial fills, replace flows, and cancels explicitly when execution logic depends on them.

## Anti-patterns

- Strategy-specific copies of shared vendor bar history when the normalized bars are identical.
- One giant JSON blob for market data, signals, orders, and positions.
- Signal tables that store only executed orders and discard no_op, hold, or blocked evaluations in replay-first systems.
- One order row mutated in place with no append-only lifecycle or fill history.
- Signal logic that reads directly from databases or writes directly to broker APIs.
- Monitoring tables used as restart persistence.
- Contract identity that omits exchange, expiry, strike, or option type.
- Derived analytics stored without the market timestamp they depend on.
- Treating order_type as a separate core fact slice when it is only an instruction attribute.
- Partial fills collapsed into a final state row with no individual fill facts.
- Broker adapters that contain pricing, signal, or risk decisions.

## Optional PostgreSQL appendix

- See [postgresql-schema-patterns.md](postgresql-schema-patterns.md) for optional physical patterns for bar_history, signal_events, and orders_and_trades.
- The core guidance in this file should remain usable outside PostgreSQL.
