"""
Axis Deal Engine - Core Business Logic

Architecture Version: 1.1
Document Reference: core/architecture/DEAL_ENGINE_v1.1_SPECIFICATION.md

This module provides the canonical Deal Engine pipeline:
1. Ingestion (ValidatedAsset schema)
2. Structural Validation (hard rejection rules)
3. Market Reality Layer (comp-based EMV)
4. Confidence Gating (caps and downgrades)
5. Scoring & Ranking (deterministic)
6. Output Classification (Strong / Moderate / Weak / Avoid / Overpriced)
"""

from .models import PropertyListing, SearchCriteria, DealAnalysis
from .scoring import BMVScorer

# Comp Engine v1.0 - Comparable Sales Valuation
from .comp_engine import (
    ComparableSale,
    SubjectProperty,
    PropertyType,
    Tenure,
    CompSelectionResult,
    ValuationResult,
    Confidence,
    Recommendation,
    CompEligibilityFilter,
    CompValuationEngine,
)

# Deal Analyzer - Integrated Comp Engine Pipeline
from .deal_analyzer import DealAnalyzer, EnrichedAnalysis

# Land Registry Service
from .land_registry import LandRegistryService, get_land_registry_service

# Ingestion Layer (DSXF v1.0)
from .ingestion import (
    ValidatedAsset,
    SourceMetadata,
    SourceCategory,
    ListingStatus,
    RejectionRecord,
    REJECTION_CODES,
    SourceRegistration,
    SOURCE_REGISTRY,
    get_source,
    register_source,
    SourceAdapter,
)

# Property Intake (Step 1 & 2)
from .intake import (
    PropertyIntake,
    Disclosures,
    DisclosureStatus,
    IntakeStatus,
    IntakeValidationResult,
    ListingSource,
    REQUIRED_INTAKE_FIELDS,
    REQUIRED_DISCLOSURE_FIELDS,
    PropertyLogbook,
    LogbookVersion,
    LogbookStatus,
    SubmittedBy,
    validate_intake,
    validate_disclosures,
    create_intake,
)

__all__ = [
    # Original exports (legacy - being deprecated)
    "PropertyListing",
    "SearchCriteria",
    "DealAnalysis",
    "BMVScorer",
    # Comp Engine v1.0
    "ComparableSale",
    "SubjectProperty",
    "PropertyType",
    "Tenure",
    "CompSelectionResult",
    "ValuationResult",
    "Confidence",
    "Recommendation",
    "CompEligibilityFilter",
    "CompValuationEngine",
    # Deal Analyzer (integrated pipeline)
    "DealAnalyzer",
    "EnrichedAnalysis",
    # Land Registry Service
    "LandRegistryService",
    "get_land_registry_service",
    # Ingestion Layer (DSXF v1.0)
    "ValidatedAsset",
    "SourceMetadata",
    "SourceCategory",
    "ListingStatus",
    "RejectionRecord",
    "REJECTION_CODES",
    "SourceRegistration",
    "SOURCE_REGISTRY",
    "get_source",
    "register_source",
    "SourceAdapter",
    # Property Intake (Step 1 & 2)
    "PropertyIntake",
    "Disclosures",
    "DisclosureStatus",
    "IntakeStatus",
    "IntakeValidationResult",
    "ListingSource",
    "REQUIRED_INTAKE_FIELDS",
    "REQUIRED_DISCLOSURE_FIELDS",
    "PropertyLogbook",
    "LogbookVersion",
    "LogbookStatus",
    "SubmittedBy",
    "validate_intake",
    "validate_disclosures",
    "create_intake",
]
