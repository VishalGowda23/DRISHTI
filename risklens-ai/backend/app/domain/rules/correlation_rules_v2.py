"""
domain/rules/correlation_rules_v2.py

Covers FR-10 (correlation/volatility signal detection).

This is the COLD path by design: 30-day rolling correlation does not
move meaningfully tick-to-tick, so it is refreshed on a timer
(default 180s), not on every price update from the
`market.prices.realtime` Kafka topic. Volatility is O(1) per tick via
an online (Welford) accumulator — no full history rescan ever.

Correlation itself is bucketed by sector before pairing, so cost is
O(sum of bucket_size^2 * window) instead of O(n^2 * window) across the
whole portfolio. This matters once a fund has more than ~30-40
holdings, and costs nothing when it doesn't.

NOTE: This is the v2 streaming engine. The original correlation_rules.py
(batch, used by RiskAnalysisService for REST-triggered analysis) is
preserved. This module is used by kafka_risk_service.py for the Kafka
hot-path.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class WelfordAccumulator:
    """Online mean/variance, O(1) per update, no stored history needed
    for the variance itself (the deque below is kept separately, only
    for the correlation matrix, which DOES need the raw series)."""

    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def realized_volatility_annualized(self) -> float:
        return math.sqrt(max(self.variance, 0.0) * 252)


@dataclass
class SymbolReturnSeries:
    """Per-symbol rolling window used ONLY for correlation (needs the
    raw vector). Volatility is read off the Welford accumulator, not
    this deque, so volatility stays O(1) even though this window is
    O(30)."""

    window: deque = field(default_factory=lambda: deque(maxlen=30))
    last_price: Optional[float] = None
    vol_this_quarter: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    vol_prior_quarter: WelfordAccumulator = field(default_factory=WelfordAccumulator)


class ReturnSeriesStore:
    """Consumes the `market.prices.realtime` Kafka stream. One call
    per price tick, O(1) work."""

    def __init__(self) -> None:
        self._series: dict[str, SymbolReturnSeries] = {}

    def on_price_tick(self, symbol: str, price: float, quarter_boundary: bool = False) -> None:
        s = self._series.setdefault(symbol, SymbolReturnSeries())
        if s.last_price is not None and s.last_price > 0 and price > 0:
            log_return = math.log(price / s.last_price)
            s.window.append(log_return)
            s.vol_this_quarter.update(log_return)
        s.last_price = price
        if quarter_boundary:
            s.vol_prior_quarter = s.vol_this_quarter
            s.vol_this_quarter = WelfordAccumulator()

    def volatility_snapshot(self, symbol: str) -> Optional[dict]:
        s = self._series.get(symbol)
        if s is None or s.vol_this_quarter.n < 2:
            return None
        current_vol = s.vol_this_quarter.realized_volatility_annualized
        prior_vol = s.vol_prior_quarter.realized_volatility_annualized
        qoq_change_pct = (
            round(((current_vol - prior_vol) / prior_vol) * 100, 2) if prior_vol > 0 else None
        )
        return {
            "symbol": symbol,
            "realized_volatility_annualized": round(current_vol, 4),
            "qoq_change_pct": qoq_change_pct,
        }

    def get_window(self, symbol: str) -> Optional[list[float]]:
        s = self._series.get(symbol)
        if s is None or len(s.window) < 5:  # need a minimum sample to correlate meaningfully
            return None
        return list(s.window)


# --- union-find, for turning a correlation graph into named clusters ---

class _DSU:
    def __init__(self, items: list[str]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def compute_correlation_clusters(
    symbols_by_sector: dict[str, list[str]],
    store: ReturnSeriesStore,
    threshold: float,
) -> list[dict]:
    """FR-10. Buckets holdings by sector, runs vectorized corrcoef
    within each bucket only, then groups anything above `threshold`
    into named clusters via union-find.

    Complexity: O(sum over sectors of (bucket_size^2 * window_len)),
    vs O(n^2 * window_len) for a flat pass across the whole portfolio.
    Cross-sector correlation is rarely the concentrated-bet risk this
    check exists to catch, so bucketing isn't just an optimization —
    it's the more meaningful grouping.
    """
    clusters: list[dict] = []

    for sector, symbols in symbols_by_sector.items():
        valid = [(sym, store.get_window(sym)) for sym in symbols]
        valid = [(sym, w) for sym, w in valid if w is not None]
        if len(valid) < 2:
            continue

        symbols_list = [sym for sym, _ in valid]
        min_len = min(len(w) for _, w in valid)
        matrix = np.array([w[-min_len:] for _, w in valid])  # n_bucket x min_len

        corr = np.corrcoef(matrix)
        dsu = _DSU(symbols_list)
        pair_correlations: dict[frozenset, float] = {}

        n = len(symbols_list)
        for i in range(n):
            for j in range(i + 1, n):
                c = corr[i, j]
                if c > threshold:
                    dsu.union(symbols_list[i], symbols_list[j])
                    pair_correlations[frozenset((symbols_list[i], symbols_list[j]))] = round(float(c), 4)

        groups: dict[str, list[str]] = {}
        for sym in symbols_list:
            groups.setdefault(dsu.find(sym), []).append(sym)

        for root, members in groups.items():
            if len(members) < 2:
                continue  # not a cluster, just an isolated holding
            member_pairs = [
                v for k, v in pair_correlations.items() if k <= frozenset(members)
            ]
            avg_corr = round(sum(member_pairs) / len(member_pairs), 4) if member_pairs else None
            clusters.append(
                {
                    "sector": sector,
                    "holdings": sorted(members),
                    "avg_correlation": avg_corr,
                    "status": "FLAGGED",
                }
            )

    return clusters


@dataclass
class CorrelationCache:
    """Throttle wrapper — the actual point of the cold-path design.
    Cheap to call every tick; only does real work every
    `refresh_interval_sec`."""

    clusters: list[dict] = field(default_factory=list)
    last_computed_at: float = 0.0
    refresh_interval_sec: float = 180.0

    def maybe_refresh(
        self,
        symbols_by_sector: dict[str, list[str]],
        store: ReturnSeriesStore,
        threshold: float,
        force: bool = False,
    ) -> list[dict]:
        now = time.time()
        if not force and (now - self.last_computed_at) < self.refresh_interval_sec:
            return self.clusters
        self.clusters = compute_correlation_clusters(symbols_by_sector, store, threshold)
        self.last_computed_at = now
        return self.clusters
