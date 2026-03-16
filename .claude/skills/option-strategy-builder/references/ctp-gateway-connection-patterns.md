# CTP Gateway Connection Patterns

Use this optional appendix when the target venue is CTP or a CTP-like futures gateway and you need concrete connection, session, recovery, and cancel-identity guidance. Keep the surrounding strategy architecture platform-neutral; use this appendix only for gateway-specific sequencing and state design.

## Recommended inputs

Make the gateway input surface explicit before you design callbacks or persistence:

- environment_name for sim, test, prod, or disaster-recovery routing
- broker_id
- user_id
- password
- trade_front
- md_front
- app_id
- auth_code
- user_product_info
- flow_path for CTP flow files and session artifacts
- instrument universe or subscription plan when market-data startup depends on strategy scope

Do not infer flow_path from the current working directory. Choose it explicitly so `.con` files and other session artifacts land in a known runtime path.

## Suggested internal abstractions

These names are illustrative, not required:

- Recommended internal events
  - `ConnectionStateChanged`
  - `GatewayLoginSucceeded`
  - `SettlementConfirmed`
  - `GatewayWarmupCompleted`
  - `MarketDataTick`
  - `OrderEvent`
  - `TradeFill`
  - `PositionSnapshot`
- Recommended internal state objects
  - `TradeSessionState`
  - `MdSessionState`
  - `GatewayIdentityState`
  - `WarmupBarrierState`

The goal is not to force naming. The goal is to separate transport state, recovery progress, and normalized execution facts so the rest of the system does not depend on CTP callback shapes.

## Trade channel lifecycle

Model the trade channel as an explicit state machine:

`CreateApi -> RegisterSpi -> RegisterFront -> SubscribePublicTopic/SubscribePrivateTopic -> Init -> OnFrontConnected -> ReqAuthenticate -> OnRspAuthenticate -> ReqUserLogin -> OnRspUserLogin -> ReqSettlementInfoConfirm -> recovery queries -> trade_ready`

Recommended behavior:

- Create the trader API with an explicit flow_path when the deployment uses flow files.
- Register SPI and front before calling `Init()`.
- Subscribe public and private topics before `Init()` when the API requires it.
- On `OnFrontConnected`, authenticate instead of sending trading requests immediately.
- On successful `OnRspAuthenticate`, send `ReqUserLogin`.
- On successful `OnRspUserLogin`, capture `front_id`, `session_id`, `trading_day`, and the order-ref baseline if the venue or wrapper exposes one.
- After login, send `ReqSettlementInfoConfirm` before marking the trade channel ready.
- After settlement confirmation, run recovery queries in an explicit chain. A common default is orders, then trades, then positions, with account or instrument queries added only when the strategy depends on them.
- Advance the recovery chain on callback completion signals such as `bIsLast`, not on fixed sleeps.
- Mark `trade_ready` only after the recovery barrier finishes and normalized order, fill, and position projections are rebuilt.

This is the part of the `temp/ordermanager` pattern worth preserving: trade-session readiness should be stronger than raw login success.

## Market-data lifecycle

Model the market-data channel independently from the trade channel:

`CreateApi -> RegisterSpi -> RegisterFront -> Init -> OnFrontConnected -> ReqUserLogin -> OnRspUserLogin -> SubscribeMarketData -> md_ready`

Recommended behavior:

- Create the market-data API with an explicit flow path if the runtime uses one.
- Keep market-data login independent from trade-session recovery.
- Subscribe from an orchestrated subscription plan rather than building subscriptions ad hoc inside trading callbacks.
- Mark `md_ready` only after the project-defined subscription barrier is met, such as subscription acknowledgements or the first accepted snapshot batch.
- Rebuild subscriptions after reconnect. Do not assume prior subscriptions survive a new market-data session.

## Readiness gate

Keep `trade_ready` and `md_ready` as separate states.

- Default safe rule: allow strategy-generated order submission only after `trade_ready`.
- If market data comes up first, allow passive data collection and warm caches, but block order routing in orchestration until trade recovery is complete.
- Treat logged-in as weaker than ready. Ready means the session is established and the required recovery or warmup barrier has finished.
- Keep the gate in orchestration or application services, not inside pricing, signal, or SPI transport code.

## Identity and cancel semantics

CTP cancel and recovery flows depend on session-scoped and venue-scoped identifiers. Preserve them explicitly.

- Centralize `req_id`, `front_id`, `session_id`, `trading_day`, `order_ref`, `order_action_ref`, `exchange_id`, `instrument_id`, `broker_order_id`, and `trade_id` in a session or order-identity store instead of scattering them across globals.
- Preserve both internal identifiers and external identifiers.
- A common lineage is `signal_event_id -> internal_order_ref -> CTP order_ref/front_id/session_id/broker_order_id -> trade_id -> position update`.
- Design cancel instructions to retain whatever the deployment needs for deterministic cancel submission. At minimum, preserve `front_id`, `session_id`, `order_ref`, and exchange or instrument context when the API path depends on them.
- Do not collapse the authoritative order identity to one internal UUID if the venue later requires CTP session identifiers to cancel or reconcile the order.

The `temp/ordermanager` example makes this need visible by using `front_id`, `session_id`, and `order_ref` during cancel requests. Keep that dependency, but move the state into owned runtime structures instead of unscoped globals.

## Recovery and reconnect

Treat reconnects as normal control flow.

- On trade disconnect, set `trade_ready` false and stop new order entry immediately.
- Reconnect through the full trade path again: authenticate, login, settlement confirm, and recovery queries.
- On market-data disconnect, set `md_ready` false, reconnect, login again, and resubscribe.
- During recovery, rebuild active-order, fill, and position projections from normalized events or explicit query responses. Do not trust stale in-memory state from before the disconnect.
- Deduplicate returned callbacks and query responses with stable keys so replay and reconnect do not double-count events.
- Distinguish fatal configuration or authentication errors from recoverable transport disconnects and heartbeat warnings.

## Callback normalization boundary

Keep SPI callbacks transport-focused and deterministic.

- Convert `OnRtnDepthMarketData` into `MarketDataTick` or another normalized quote event.
- Convert `OnRtnOrder` and `OnRspQryOrder` into normalized `OrderEvent` records.
- Convert `OnRtnTrade` and `OnRspQryTrade` into normalized `TradeFill` records.
- Convert `OnRspQryInvestorPosition` into `PositionSnapshot` inputs or another explicit recovery fact.
- Send normalized events into orchestration or application services, which then coordinate persistence, replay, risk, and execution workflows.
- Do not put contract selection, signal generation, risk checks, or trade decisions directly inside SPI handlers.

This is where the `temp/ordermanager` example should be improved rather than copied: it is useful as a session-sequencing example, but not as a blueprint for placing domain logic inside `MdSpi::OnRtnDepthMarketData`.

## Anti-patterns

- Sharing `front_id`, `session_id`, or `order_ref` as unowned process-wide globals.
- Driving recovery query chains with `sleep()` instead of callback completion or explicit barriers.
- Letting `MdSpi` call into `TraderSpi` or mutate domain state directly as a coordination shortcut.
- Placing selection, signal, or risk rules inside `OnRtnDepthMarketData`.
- Treating every recoverable gateway error as a process-fatal exit from callback code.
- Using the current working directory as the implicit location for `.con` or other flow files.
- Assuming market-data login is enough to enable order submission.
