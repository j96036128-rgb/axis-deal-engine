"""
Axis Deal Engine - Agent Property Submission Module

Private, invite-only property submission system for agents.
No public marketplace, no buyer browsing, no payments.

Principles:
1. Facts before marketing
2. Mandatory upfront information
3. Immutable submissions (versioned, not edited)
4. Standardised schema for every property
5. No opinions, no scoring at submission stage
"""

from core.submission.schema import (
    AgentSubmission,
    SaleRoute,
    DocumentType,
    DocumentRecord,
    SubmissionStatus,
    REQUIRED_SUBMISSION_FIELDS,
    REQUIRED_DOCUMENTS,
    LEASEHOLD_REQUIRED_DOCUMENTS,
)
from core.submission.storage import (
    DocumentStorage,
    get_document_storage,
)
from core.submission.logbook import (
    SubmissionLogbook,
    SubmissionVersion,
    VersionAction,
    verify_hash_chain,
    compute_version_hash,
)
from core.submission.validation import (
    validate_submission,
    create_submission,
    SubmissionValidationResult,
)
from core.submission.repository import (
    SubmissionRepository,
    get_submission_repository,
)
from core.submission.verification import (
    VerificationStatus,
    VerificationSource,
    FactCategory,
    VerificationRecord,
    FactVerificationState,
    PropertyVerificationSummary,
    create_verification_summary_from_submission,
    DealEngineGatingResult,
    check_deal_engine_readiness,
    extract_verified_submission_data,
    LAND_REGISTRY_VERIFIABLE,
    EPC_VERIFIABLE,
    DOCUMENT_VERIFIABLE,
    CLAIM_ONLY,
)

__all__ = [
    # Schema
    "AgentSubmission",
    "SaleRoute",
    "DocumentType",
    "DocumentRecord",
    "SubmissionStatus",
    "REQUIRED_SUBMISSION_FIELDS",
    "REQUIRED_DOCUMENTS",
    "LEASEHOLD_REQUIRED_DOCUMENTS",
    # Storage
    "DocumentStorage",
    "get_document_storage",
    # Logbook
    "SubmissionLogbook",
    "SubmissionVersion",
    "VersionAction",
    "verify_hash_chain",
    "compute_version_hash",
    # Validation
    "validate_submission",
    "create_submission",
    "SubmissionValidationResult",
    # Repository
    "SubmissionRepository",
    "get_submission_repository",
    # Verification
    "VerificationStatus",
    "VerificationSource",
    "FactCategory",
    "VerificationRecord",
    "FactVerificationState",
    "PropertyVerificationSummary",
    "create_verification_summary_from_submission",
    "DealEngineGatingResult",
    "check_deal_engine_readiness",
    "extract_verified_submission_data",
    "LAND_REGISTRY_VERIFIABLE",
    "EPC_VERIFIABLE",
    "DOCUMENT_VERIFIABLE",
    "CLAIM_ONLY",
]
