"""Small, deterministic graph queries for the analyst UI."""

import logging
from collections import deque

import pandas as pd


LOGGER = logging.getLogger(__name__)
COLUMNS = ["gid", "n_sources", "source_gids", "min_hops_from_any", "role"]


def common_receivers(G, gids: list[int], max_hops=4, min_sources=2) -> pd.DataFrame:
    """Find downstream nodes reachable from multiple supplied sources."""
    sources = sorted({int(gid) for gid in gids})
    valid = [gid for gid in sources if gid in G]
    unknown = [gid for gid in sources if gid not in G]
    if unknown:
        LOGGER.warning("Неизвестные gid пропущены: %s", unknown)
    if not valid:
        return pd.DataFrame(columns=COLUMNS)

    reached: dict[int, list[tuple[int, int]]] = {}
    for source in valid:
        queue = deque([(source, 0)])
        seen = {source}
        while queue:
            node, hops = queue.popleft()
            if hops >= max_hops:
                continue
            for neighbor in sorted(G.successors(node)):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                reached.setdefault(neighbor, []).append((source, hops + 1))
                queue.append((neighbor, hops + 1))

    rows = []
    for gid, hits in sorted(reached.items()):
        source_gids = sorted({source for source, _ in hits})
        if len(source_gids) < min_sources:
            continue
        rows.append({
            "gid": gid,
            "n_sources": len(source_gids),
            "source_gids": ", ".join(map(str, source_gids)),
            "min_hops_from_any": min(hops for _, hops in hits),
            "role": G.nodes[gid].get("role", ""),
        })
    return pd.DataFrame(rows, columns=COLUMNS)
