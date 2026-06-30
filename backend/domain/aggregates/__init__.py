"""Domain aggregate roots for Local Clip Studio.

Aggregates ensure consistency boundaries — they protect invariants
across multiple entities and serve as the entry point for all
modifications within the boundary.

Architecture:
    - Zero imports from infrastructure
    - Pure Python standard library only
"""

from backend.domain.aggregates.project_aggregate import ProjectAggregate

__all__ = [
    "ProjectAggregate",
]
