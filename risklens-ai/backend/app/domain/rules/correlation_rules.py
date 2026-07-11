"""
RiskLens AI — Correlation Rules Engine
Detects clusters of highly correlated holdings.
"""

from typing import List, Dict
import numpy as np
from app.domain.enums import BreachStatus
from app.domain.models.risk import CorrelationCluster
from app.core.logger import get_logger

logger = get_logger("rules.correlation")


def compute_correlation_matrix(
    price_histories: Dict[str, List[float]],
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise correlation matrix from price histories.

    Args:
        price_histories: Dict mapping symbol -> list of daily returns (last 30 days)

    Returns:
        Nested dict: correlation_matrix[symbol_a][symbol_b] = correlation coefficient
    """
    symbols = list(price_histories.keys())
    n = len(symbols)

    if n < 2:
        return {}

    # Build returns matrix (each row = symbol, each col = day)
    min_length = min(len(v) for v in price_histories.values())
    if min_length < 5:
        logger.warning("Insufficient price history for correlation", min_length=min_length)
        return {}

    returns_matrix = np.array([
        price_histories[s][:min_length] for s in symbols
    ])

    # Compute correlation matrix
    corr_matrix = np.corrcoef(returns_matrix)

    # Convert to dict
    result: Dict[str, Dict[str, float]] = {}
    for i, sym_a in enumerate(symbols):
        result[sym_a] = {}
        for j, sym_b in enumerate(symbols):
            if i != j:
                result[sym_a][sym_b] = round(float(corr_matrix[i][j]), 4)

    return result


def detect_correlation_clusters(
    correlation_matrix: Dict[str, Dict[str, float]],
    threshold: float = 0.85,
    min_cluster_size: int = 3,
) -> List[CorrelationCluster]:
    """Detect clusters of holdings with correlation above threshold.

    Uses a simple greedy approach: for each pair above threshold,
    group connected components into clusters.

    Args:
        correlation_matrix: Pairwise correlation dict
        threshold: Minimum correlation to flag
        min_cluster_size: Minimum number of holdings to form a cluster

    Returns:
        List of CorrelationCluster objects
    """
    if not correlation_matrix:
        return []

    # Find all high-correlation pairs
    high_corr_pairs = set()
    symbols = list(correlation_matrix.keys())

    for sym_a in symbols:
        for sym_b, corr in correlation_matrix.get(sym_a, {}).items():
            if corr >= threshold and sym_a != sym_b:
                pair = tuple(sorted([sym_a, sym_b]))
                high_corr_pairs.add(pair)

    if not high_corr_pairs:
        return []

    # Build adjacency graph and find connected components
    adjacency: Dict[str, set] = {}
    for a, b in high_corr_pairs:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    # BFS to find connected components
    visited = set()
    clusters = []

    for start in adjacency:
        if start in visited:
            continue
        # BFS
        component = []
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(component) >= min_cluster_size:
            # Calculate average correlation within cluster
            corr_values = []
            for i, a in enumerate(component):
                for b in component[i + 1:]:
                    corr_val = correlation_matrix.get(a, {}).get(b, 0)
                    corr_values.append(corr_val)

            avg_corr = sum(corr_values) / len(corr_values) if corr_values else 0

            clusters.append(CorrelationCluster(
                holdings=sorted(component),
                avg_correlation=round(avg_corr, 4),
                status=BreachStatus.FLAGGED,
            ))

    logger.info(
        "Correlation analysis complete",
        clusters_found=len(clusters),
        threshold=threshold,
    )

    return clusters
