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
from core.submission.export import (
    # Contract
    VerifiedPropertyExport,
    # Enums
    TrustLevel,
    PlanningRestriction,
    # Nested dataclasses
    ExportMetadata,
    ExportVerificationSummary,
    AddressFacts,
    PhysicalFacts,
    TenureFacts,
    FinancialFacts,
    PlanningFacts,
    PropertyFacts,
    ExportDocumentRecord,
    ExportEpcRecord,
    ExportDocuments,
    ExportFlags,
    # Factory and validation
    create_verified_property_export,
    validate_export_version,
    parse_verified_property_export,
    compute_export_hash,
    # Exceptions
    ExportVersionError,
    ExportBlockedError,
    # Constants
    EXPORT_VERSION,
    SUPPORTED_EXPORT_VERSIONS,
)
from core.submission.auto_publish import (
    # Service
    AutoPublishService,
    # Result types
    AutoPublishResult,
    AutoPublishSuccess,
    AutoPublishBlocked,
    AutoPublishGatingFailed,
    AutoPublishExportFailed,
    AutoPublishValidationError,
    # Repository integration
    PublishRecord,
    # Convenience function
    try_auto_publish,
    # Constants
    BUYER_PDF_BASE_DIR,
    BLOCKED_TRUST_LEVELS,
)
from core.submission.invite import (
    # Model and enums
    InviteToken,
    InviteStatus,
    # Repository
    InviteTokenRepository,
    get_invite_repository,
    reset_invite_repository,
    # Validation
    InviteValidationResult,
    InviteValidationSuccess,
    InviteValidationFailure,
    validate_invite_token,
    # Factory
    create_invite_token,
    generate_token_value,
    # Constants
    TOKEN_BYTES,
    DEFAULT_EXPIRY_DAYS,
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
    # Export Contract (VerifiedPropertyExport v1.0)
    "VerifiedPropertyExport",
    "TrustLevel",
    "PlanningRestriction",
    "ExportMetadata",
    "ExportVerificationSummary",
    "AddressFacts",
    "PhysicalFacts",
    "TenureFacts",
    "FinancialFacts",
    "PlanningFacts",
    "PropertyFacts",
    "ExportDocumentRecord",
    "ExportEpcRecord",
    "ExportDocuments",
    "ExportFlags",
    "create_verified_property_export",
    "validate_export_version",
    "parse_verified_property_export",
    "compute_export_hash",
    "ExportVersionError",
    "ExportBlockedError",
    "EXPORT_VERSION",
    "SUPPORTED_EXPORT_VERSIONS",
    # Auto Publish (Buyer PDF Generation)
    "AutoPublishService",
    "AutoPublishResult",
    "AutoPublishSuccess",
    "AutoPublishBlocked",
    "AutoPublishGatingFailed",
    "AutoPublishExportFailed",
    "AutoPublishValidationError",
    "PublishRecord",
    "try_auto_publish",
    "BUYER_PDF_BASE_DIR",
    "BLOCKED_TRUST_LEVELS",
    # Invite Token System
    "InviteToken",
    "InviteStatus",
    "InviteTokenRepository",
    "get_invite_repository",
    "reset_invite_repository",
    "InviteValidationResult",
    "InviteValidationSuccess",
    "InviteValidationFailure",
    "validate_invite_token",
    "create_invite_token",
    "generate_token_value",
    "TOKEN_BYTES",
    "DEFAULT_EXPIRY_DAYS",
]
