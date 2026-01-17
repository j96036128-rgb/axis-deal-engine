"""
Axis Deal Engine - Ingestion Layer

Provides the canonical ValidatedAsset schema and source adapter interface
for the Data Source Expansion Framework (DSXF v1.0).

This module is the single entry point for all property data entering the
Deal Engine pipeline. All sources must normalise to ValidatedAsset.
"""

from core.ingestion.schema import (
    ValidatedAsset,
    SourceMetadata,
    SourceCategory,
    ListingStatus,
    RejectionRecord,
    REJECTION_CODES,
)
from core.ingestion.registry import (
    SourceRegistration,
    SOURCE_REGISTRY,
    get_source,
    register_source,
)
from core.ingestion.adapter import SourceAdapter

__all__ = [
    # Core schema
    "ValidatedAsset",
    "SourceMetadata",
    "SourceCategory",
    "ListingStatus",
    # Rejection handling
    "RejectionRecord",
    "REJECTION_CODES",
    # Source registration
    "SourceRegistration",
    "SOURCE_REGISTRY",
    "get_source",
    "register_source",
    # Adapter interface
    "SourceAdapter",
]
