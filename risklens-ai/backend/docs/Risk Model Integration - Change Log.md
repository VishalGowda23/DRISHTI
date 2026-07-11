# Risk Model Integration — Change Log

**Author:** AI-assisted integration pass  
**Date:** 2026-07-11  
**Scope:** Phase 2 — Kafka-native risk model wired into the RiskLens AI backend

---

## Overview

This document describes every file that was **created** or **modified** when integrating Claude's risk model (`concentration_rules.py`, `correlation_rules.py`, `claude_client.py`, `risk_analysis_service.py`) into the existing backend codebase.

### Why these changes exist

The original backend had:
- A stateless, REST-triggered `RiskAnalysisService` that re-reads Mongo and calls Yahoo Finance on every analysis request.
- A LangChain-backed `ClaudeClient` that sends free-form JSON prompts.

Claude's risk model adds a parallel **Kafka-native hot path** that:
- Maintains **in-memory O(1) state** per portfolio (no Mongo re-read per tick).
- Feeds **online Welford volatility** accumulators from every price tick.
- Runs **sector-bucketed correlation clustering** on a 180-second timer.
- Calls Claude only when a threshold is crossed, using **tool_use** + **prompt caching** for token efficiency.
- Falls back gracefully through Sonnet → Haiku → rule-engine-only if AI is unavailable.

**The original REST path (`RiskAnalysisService`, `ClaudeClient`) is completely untouched.** Both paths coexist.

---

## New Files

### 1. `app/domain/rules/concentration_rules_v2.py`
**Path:** `risklens-ai/backend/app/domain/rules/concentration_rules_v2.py`

**What it is:**  
A stateful concentration rules engine. Replaces the need to re-scan all positions on every tick.

**Key classes / functions:**

| Symbol | Description |
|---|---|
| `CheckStatus` | Enum: `OK`, `WARNING`, `BREACH` |
| `ConcentrationLimits` | Dataclass mirroring the `risk_limits` Mongo document. Has `from_mongo_doc()` and `from_defaults()` constructors. |
| `PortfolioConcentrationState` | In-memory state per portfolio: NAV, issuer/sector/geo/asset-class exposure buckets, holdings count. |
| `apply_position_delta(state, ...)` | **Hot path — O(1).** Updates the four exposure buckets for the changed position only. Returns only the non-OK check rows for the touched entities. Called on every `portfolio.positions.changed` event. |
| `full_recompute(positions, limits)` | **Cold path — O(n).** Rebuilds state from scratch from the `positions` list. Called once on `portfolio.created` and periodically to correct float drift. |
| `build_rule_engine_results(state, limits)` | Produces the full `issuer_checks / sector_checks / geography_checks / asset_class_checks / diversification_flags` dict — the exact schema used by the `assessments` Mongo collection. |

**Why v2 (not replacing the original):**  
The original `concentration_rules.py` is used by `RiskAnalysisService.analyze_portfolio()` for REST-triggered analysis. Renaming it to `_v2` keeps that path intact.

---

### 2. `app/domain/rules/correlation_rules_v2.py`
**Path:** `risklens-ai/backend/app/domain/rules/correlation_rules_v2.py`

**What it is:**  
An online streaming correlation + volatility engine. Replaces the Yahoo Finance batch correlation pull.

**Key classes / functions:**

| Symbol | Description |
|---|---|
| `WelfordAccumulator` | Online mean/variance — O(1) per update. Used for realized volatility without storing price history. |
| `SymbolReturnSeries` | Per-symbol: rolling 30-day log-return deque (for correlation) + two Welford accumulators (this quarter / prior quarter). |
| `ReturnSeriesStore` | Central store for all symbols. Call `on_price_tick(symbol, price)` on every price event. `volatility_snapshot(symbol)` returns realized vol + QoQ change. `get_window(symbol)` returns the 30-day return series for correlation. |
| `compute_correlation_clusters(symbols_by_sector, store, threshold)` | Runs `np.corrcoef` within each sector bucket only (not across the whole portfolio), then groups highly-correlated pairs into clusters via union-find. Returns a `FLAGGED` cluster list matching the `assessments` schema. |
| `CorrelationCache` | Throttle wrapper around `compute_correlation_clusters`. Only recomputes every 180 seconds regardless of how often it's called. |

**Design decision — sector bucketing:**  
Cross-sector correlation is rarely the concentrated-bet risk this check exists to catch. Bucketing by sector reduces cost from O(n² × window) to O(Σ bucket_size² × window) and produces more actionable groupings.

---

### 3. `app/services/kafka_risk_service.py`
**Path:** `risklens-ai/backend/app/services/kafka_risk_service.py`

**What it is:**  
The main Kafka-native orchestrator. Wires the rule engines to Claude and maintains per-process state registries.

**Three public entry points (call these from worker code):**

```python
on_portfolio_created(positions: list[dict], limits_doc: dict) -> None
on_price_tick(symbol: str, price: float, quarter_boundary: bool = False) -> None
on_position_changed(portfolio_id, *, issuer, sector, country, asset_class,
                    is_cash, old_market_value, new_market_value,
                    limits_doc, sectors_map, claude_client,
                    portfolio_context) -> Optional[dict]
```

**Return value of `on_position_changed`:**  
Returns `None` on most calls (nothing crossed a threshold). Returns a full assessment dict when Claude is triggered. That dict is ready to insert into the `assessments` Mongo collection as-is.

**Token-optimization helpers (also exported):**

| Function | Purpose |
|---|---|
| `should_trigger_claude(rule_engine_results, clusters)` | FR-11 gate — skips Claude entirely on a clean scan. Biggest token-saving lever. |
| `build_claude_facts(rule_engine_results, clusters, volatility_snapshots)` | Drops all OK-status rows before building the Claude prompt. Only BREACH/WARNING/FLAGGED rows are sent. |
| `facts_hash(facts)` | SHA-256 hash of the rounded facts dict. Used to dedupe repeated Claude calls when the portfolio is in the same breach state across many ticks. |
| `AssessmentCache` | 15-minute TTL cache keyed by `facts_hash`. Prevents re-calling Claude when nothing material has changed. |

**In-process state registries** (swap for Redis to scale beyond one process):
- `_concentration_states` — one `PortfolioConcentrationState` per portfolio_id
- `_return_series_store` — single `ReturnSeriesStore` shared across all portfolios
- `_correlation_caches` — one `CorrelationCache` per portfolio_id
- `_assessment_cache` — shared `AssessmentCache`

---

## Modified Files

### 4. `app/infrastructure/ai/claude_client.py`
**Path:** `risklens-ai/backend/app/infrastructure/ai/claude_client.py`

**What changed:**  
Two additions were appended **after** the existing `get_claude_client()` singleton, separated by a clear comment block. Nothing above line 193 was changed.

**Added — `ClaudeAnalysisResult` dataclass:**
```python
@dataclass
class ClaudeAnalysisResult:
    claude_analysis: dict   # the emit_risk_assessment tool output
    model_info: dict        # model name, token usage, latency
    ai_unavailable: bool = False
```

**Added — `call_claude_for_analysis(client, portfolio_context, facts)`:**  
Direct `anthropic` SDK call (not LangChain). Uses:
- `tool_choice` → `emit_risk_assessment` tool for guaranteed structured JSON output
- `cache_control: ephemeral` on the static system prompt for prompt caching
- 3-tier fallback: Sonnet (3 retries with backoff) → Haiku → rule-engine-only verdict
- Never raises — always returns a usable `ClaudeAnalysisResult` even if all AI is down

**Also fixed:** The `from langchain.callbacks.tracers import LangChainTracer` import (line 13) was guarded with a `try/except ImportError` because this module moved in recent LangChain versions. The existing code was already broken on import; this makes it resilient.

**Two clients now coexist:**

| Client | Used by | SDK | Output type |
|---|---|---|---|
| `ClaudeClient` / `get_claude_client()` | `RiskAnalysisService` (REST path) | LangChain | `ClaudeAnalysis` (Pydantic) |
| `call_claude_for_analysis()` | `kafka_risk_service` (Kafka path) | `anthropic` direct | `ClaudeAnalysisResult` (dataclass) |

---

### 5. `app/workers/mock_price_poller.py`
**Path:** `risklens-ai/backend/app/workers/mock_price_poller.py`

**What changed:**

```diff
+ from app.services.kafka_risk_service import on_price_tick as _risk_on_price_tick
```

In `_publish_tick()`:
```diff
  # after successful Kafka send:
+ _risk_on_price_tick(symbol, price)

  # after direct Mongo fallback write:
+ _risk_on_price_tick(symbol, price)
```

**Why:** Every synthetic price tick emitted by the mock poller now feeds the `ReturnSeriesStore` in `kafka_risk_service`, keeping the Welford volatility accumulators and the 30-day return window up to date. Both the Kafka path and the direct-Mongo fallback path are covered.

---

### 6. `app/workers/price_consumer_worker.py`
**Path:** `risklens-ai/backend/app/workers/price_consumer_worker.py`

**What changed:**

```diff
+ from app.services.kafka_risk_service import on_price_tick as _risk_on_price_tick
```

In `_handle_price_tick()`:
```diff
  await apply_price_update(symbol, float(price), int(token), source)
+ _risk_on_price_tick(symbol, float(price))
```

**Why:** The price consumer is the Kafka-consume half of the data pipeline. It must also feed the `ReturnSeriesStore` so the streaming risk model sees real-market-driven ticks (not just mock ones).

---

### 7. `app/workers/trade_simulator.py`
**Path:** `risklens-ai/backend/app/workers/trade_simulator.py`

**What changed:**

```diff
+ from app.services.kafka_risk_service import on_position_changed as _risk_on_position_changed
+ try:
+     import anthropic as _anthropic
+     _ANTHROPIC_SDK_AVAILABLE = True
+ except ImportError:
+     _ANTHROPIC_SDK_AVAILABLE = False
```

After every successful portfolio mutation + Mongo write, the simulator now:
1. Builds a `sectors_map` from the current holdings (needed for correlation bucketing).
2. Calls `on_position_changed(...)` with the acted holding's delta.
3. If an assessment dict is returned (i.e., a threshold was crossed and Claude produced a verdict):
   - Inserts it into the `assessments` MongoDB collection.
   - Broadcasts it via `ws_manager.broadcast_assessment(...)` to connected WebSocket clients.
4. All risk-model errors are caught and logged as warnings — trade simulation continues regardless.

**Why `on_position_changed` returns `None` most of the time:**  
This is by design. It only returns a dict when (a) a concentration threshold was crossed, AND (b) `should_trigger_claude` determined it was worth a Claude call. A clean portfolio tick is a pure no-op from the risk model's perspective.

---

### 8. `requirements.txt`
**Path:** `risklens-ai/backend/requirements.txt`

**What changed:**

```diff
  # --- AI / LLM ---
+ anthropic>=0.40.0          # direct SDK for Kafka hot-path (tool_use + prompt caching)
  langchain==0.3.0
  langchain-anthropic==0.2.0
```

The `anthropic` package is the base SDK. `langchain-anthropic` (already present) wraps it for the LangChain path, but the direct SDK is needed for tool_use structured output and prompt caching in the Kafka path.

---

## Architecture — Before vs. After

```
BEFORE:
  REST request
    └── RiskAnalysisService.analyze_portfolio()
          ├── Yahoo Finance (prices)
          ├── concentration_rules.py   (stateless, O(n))
          ├── correlation_rules.py     (Yahoo Finance batch)
          └── ClaudeClient (LangChain, free-form JSON)

AFTER (both paths coexist):
  REST request
    └── RiskAnalysisService.analyze_portfolio()   [UNCHANGED]
          ├── Yahoo Finance (prices)
          ├── concentration_rules.py   (stateless, O(n))
          ├── correlation_rules.py     (Yahoo Finance batch)
          └── ClaudeClient (LangChain, free-form JSON)

  Kafka / price tick
    ├── mock_price_poller  ──► on_price_tick() ──► ReturnSeriesStore (O(1))
    └── price_consumer_worker ──► on_price_tick() ──► ReturnSeriesStore (O(1))

  Kafka / position change (trade_simulator, shock API)
    └── trade_simulator ──► on_position_changed()
            ├── apply_position_delta()   [O(1), concentration check]
            ├── CorrelationCache.maybe_refresh()   [cold, every 180s]
            ├── should_trigger_claude()  [gate — skips Claude on clean scans]
            ├── build_claude_facts()     [strip OK rows, build minimal prompt]
            ├── facts_hash() + AssessmentCache   [dedupe repeated breach states]
            ├── call_claude_for_analysis()        [Sonnet → Haiku → rule-only]
            └── returns assessment dict
                    ├── db["assessments"].insert_one(assessment)
                    └── ws_manager.broadcast_assessment(...)
```

---

## What Is Deliberately NOT Changed

- **No existing routes modified.** All `/api/v1/...` endpoints behave identically.
- **No Mongo schemas changed.** The assessment dict produced by `on_position_changed` matches the existing `assessments` collection shape.
- **No notification service calls added** inside the risk model. If the trade simulator produces an assessment, it writes to Mongo and broadcasts via WebSocket. The existing `NotificationService` (FR-15/16/17) should consume `claude_analysis.severity` from the `assessments` collection as before.
- **No audit log writes** inside the risk model. Call the existing audit service with the returned assessment dict from outside.

---

## Dependencies Added

| Package | Version | Reason |
|---|---|---|
| `anthropic` | `>=0.40.0` | Direct SDK for `tool_use` + prompt caching in Kafka hot-path |

> **Note:** `numpy` is already listed in `requirements.txt` and is required by `correlation_rules_v2.py` for `np.corrcoef`. No change needed there.
