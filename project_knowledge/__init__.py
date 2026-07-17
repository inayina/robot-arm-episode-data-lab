"""Project Evidence Agent V1 public package."""

from .core import (
    CatalogEntry,
    EvidenceChunk,
    EvidenceMetadata,
    QueryResult,
    Repository,
    build_catalog,
    load_registry,
    query_project,
    route_mode,
)

__all__ = [
    "CatalogEntry",
    "EvidenceChunk",
    "EvidenceMetadata",
    "QueryResult",
    "Repository",
    "build_catalog",
    "load_registry",
    "query_project",
    "route_mode",
]

__version__ = "1.0.0"
