# Risk model — integration notes

Maps to `backend/app/domain/rules/`, `backend/app/services/`,
`backend/app/infrastructure/ai/` in your Phase 2 folder tree. Drop
these three files + this one in as-is.

## Wiring into your existing codebase

You already have: seeded portfolios, price poller, Kafka pub/sub,
Mongo consumer, trade simulator, shock API. This model expects to be
called from three places in that pipeline:

| Your existing component | Call this |
|---|---|
| Portfolio seed / Mongo consumer, on `portfolio.created` | `on_portfolio_created(positions, limits_doc)` — pull `positions` and `risk_limits` docs straight from Mongo, pass as-is |
| Price poller, on each price tick (before/alongside publishing to `market.prices.realtime`) | `on_price_tick(symbol, price, quarter_boundary=...)` |
| Kafka consumer for `portfolio.positions.changed` (trade simulator / shock API events land here) | `on_position_changed(...)` — this is the one that may return an assessment dict to persist |

`on_position_changed` returns `None` on most calls — that's
intentional, not a bug. It only returns a full assessment dict when a
tick actually crossed a threshold AND `should_trigger_claude` decided
there's something worth Claude's judgment. When it returns a dict,
that's your `assessments` document — write it to Mongo as-is, then
hand `portfolio_id` + `claude_analysis.severity` to your notification
service for the escalation fan-out (FR-15/16/17).

## `sectors_map` parameter

`on_position_changed` and correlation clustering need
`{sector: [symbol, ...]}` for the current portfolio. Since your
teammate owns synthetic data generation, this should come from
whatever already groups your seeded positions by sector — likely a
one-line `groupby` over the `positions` collection, cached alongside
`PortfolioConcentrationState` and refreshed whenever positions are
added/removed (not on every price tick).

## Dependencies

```
pip install anthropic numpy
```

## What's deliberately NOT here

- No Slack/email/Jira calls — that's the notification service (FR-15/16/17), consumes the `claude_analysis.severity` this produces.
- No FastAPI routes — `risk_analysis_service` functions are plain Python, callable from Dev1's endpoint handlers or Dev4's Kafka consumer directly.
- No audit log writes — call your audit service with the returned assessment dict; this module's job ends at producing that dict.
