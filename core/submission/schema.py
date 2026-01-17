"""
Agent Submission Schema - Mandatory Property Information

Defines the canonical schema for agent property submissions.
All required fields and documents must be provided - no inference or fallback.

Principles:
- Facts before marketing
- No free-text marketing descriptions
- Standardised schema enforced at submission
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Final, Optional

from core.comp_engine.models import PropertyType, Tenure


# =============================================================================
# Enums
# =============================================================================


class SaleRoute(Enum):
    """Expected sale route for the property."""

    AUCTION = "auction"
    PRIVATE_TREATY = "private_treaty"
    OFF_MARKET = "off_market"


class DocumentType(Enum):
    """Types of documents that can be uploaded."""

    TITLE_REGISTER = "title_register"
    EPC = "epc"
    FLOOR_PLAN = "floor_plan"
    LEASE = "lease"
    PLANNING_APPROVAL = "planning_approval"
    OTHER = "other"


class SubmissionStatus(Enum):
    """Status of property submission in the system."""

    # Initial states
    DRAFT = "draft"
    INCOMPLETE = "incomplete"  # Missing required fields/documents
    SUBMITTED = "submitted"  # Complete submission awaiting review

    # Review states
    UNDER_REVIEW = "under_review"
    UNEVALUATED = "unevaluated"  # Not yet evaluated by Deal Engine
    EVALUATED = "evaluated"  # Evaluated by Deal Engine

    # Final states
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    WITHDRAWN = "withdrawn"


# =============================================================================
# Constants
# =============================================================================

# UK postcode validation regex
UK_POSTCODE_REGEX: Final = re.compile(
    r"^([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})$", re.IGNORECASE
)

# Required submission fields - submission rejected if any missing
REQUIRED_SUBMISSION_FIELDS: Final[tuple[str, ...]] = (
    "full_address",
    "postcode",
    "property_type",
    "tenure",
    "floor_area_sqm",
    "guide_price",
    "sale_route",
    "agent_firm",
    "agent_name",
    "agent_email",
)

# Required documents for all submissions
REQUIRED_DOCUMENTS: Final[tuple[DocumentType, ...]] = (
    DocumentType.TITLE_REGISTER,
    DocumentType.EPC,
    DocumentType.FLOOR_PLAN,
)

# Additional required documents for leasehold properties
LEASEHOLD_REQUIRED_DOCUMENTS: Final[tuple[DocumentType, ...]] = (DocumentType.LEASE,)

# Valid file extensions for document uploads
ALLOWED_EXTENSIONS: Final[tuple[str, ...]] = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
)

# Maximum file size (10MB)
MAX_FILE_SIZE_BYTES: Final[int] = 10 * 1024 * 1024


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_uk_postcode(postcode: str) -> bool:
    """Validate UK postcode format."""
    if not postcode:
        return False
    normalised = " ".join(postcode.upper().split())
    return bool(UK_POSTCODE_REGEX.match(normalised))


def normalise_uk_postcode(postcode: str) -> str:
    """Normalise UK postcode to standard format."""
    if not postcode:
        return ""
    clean = postcode.upper().replace(" ", "")
    if len(clean) >= 4:
        return f"{clean[:-3]} {clean[-3:]}"
    return clean


def generate_property_id() -> str:
    """Generate a unique property ID."""
    return f"PROP-{uuid.uuid4().hex[:12].upper()}"


def generate_submission_id() -> str:
    """Generate a unique submission ID."""
    return f"SUB-{uuid.uuid4().hex[:12].upper()}"


# =============================================================================
# Document Record
# =============================================================================


@dataclass(frozen=True)
class DocumentRecord:
    """
    Immutable record of an uploaded document.

    Documents are stored separately and referenced by ID.
    This record contains metadata only - not the file contents.
    """

    document_id: str
    document_type: DocumentType
    filename: str
    file_extension: str
    file_size_bytes: int
    content_hash: str  # SHA-256 hash for integrity
    uploaded_at: datetime
    storage_path: str  # Internal path to stored file

    @classmethod
    def create(
        cls,
        document_type: DocumentType,
        filename: str,
        file_size_bytes: int,
        content_hash: str,
        storage_path: str,
    ) -> "DocumentRecord":
        """Create a new document record."""
        # Extract extension
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        return cls(
            document_id=f"DOC-{uuid.uuid4().hex[:12].upper()}",
            document_type=document_type,
            filename=filename,
            file_extension=ext,
            file_size_bytes=file_size_bytes,
            content_hash=content_hash,
            uploaded_at=datetime.utcnow(),
            storage_path=storage_path,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialisation."""
        return {
            "document_id": self.document_id,
            "document_type": self.document_type.value,
            "filename": self.filename,
            "file_extension": self.file_extension,
            "file_size_bytes": self.file_size_bytes,
            "content_hash": self.content_hash,
            "uploaded_at": self.uploaded_at.isoformat(),
            "storage_path": self.storage_path,
        }


# =============================================================================
# Agent Submission
# =============================================================================


@dataclass
class AgentSubmission:
    """
    Agent property submission schema.

    All required fields must be provided. No free-text marketing descriptions.
    Documents are stored separately and referenced by DocumentRecord.

    This is the entry point for all agent-submitted properties.
    """

    # === REQUIRED PROPERTY FIELDS ===
    full_address: str
    postcode: str
    property_type: PropertyType
    tenure: Tenure
    floor_area_sqm: int  # Floor area in square metres
    guide_price: int  # Guide price in GBP
    sale_route: SaleRoute

    # === REQUIRED AGENT FIELDS ===
    agent_firm: str
    agent_name: str
    agent_email: str

    # === OPTIONAL PROPERTY FIELDS (facts only, no marketing) ===
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    year_built: Optional[int] = None
    council_tax_band: Optional[str] = None  # A-H
    epc_rating: Optional[str] = None  # A-G (from EPC document)

    # === LEASEHOLD-SPECIFIC FIELDS ===
    lease_years_remaining: Optional[int] = None
    ground_rent_annual: Optional[int] = None
    service_charge_annual: Optional[int] = None

    # === DOCUMENTS (required documents must be uploaded) ===
    documents: list[DocumentRecord] = field(default_factory=list)

    # === METADATA (set by system) ===
    property_id: Optional[str] = None
    submission_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    status: SubmissionStatus = field(default=SubmissionStatus.DRAFT)

    def __post_init__(self) -> None:
        """Validate required fields at construction."""
        # Validate required string fields
        if not self.full_address or not self.full_address.strip():
            raise ValueError("full_address is required and cannot be empty")

        if not self.postcode or not self.postcode.strip():
            raise ValueError("postcode is required and cannot be empty")

        if not validate_uk_postcode(self.postcode):
            raise ValueError(f"Invalid UK postcode format: {self.postcode}")

        # Normalise postcode
        object.__setattr__(self, "postcode", normalise_uk_postcode(self.postcode))

        # Validate agent fields
        if not self.agent_firm or not self.agent_firm.strip():
            raise ValueError("agent_firm is required and cannot be empty")
        if not self.agent_name or not self.agent_name.strip():
            raise ValueError("agent_name is required and cannot be empty")
        if not self.agent_email or not self.agent_email.strip():
            raise ValueError("agent_email is required and cannot be empty")

        # Validate numeric fields
        if self.floor_area_sqm is None or self.floor_area_sqm <= 0:
            raise ValueError("floor_area_sqm must be positive")
        if self.guide_price is None or self.guide_price <= 0:
            raise ValueError("guide_price must be positive")

        # Validate optional numeric fields if provided
        if self.bedrooms is not None and self.bedrooms < 0:
            raise ValueError("bedrooms cannot be negative")
        if self.bathrooms is not None and self.bathrooms < 0:
            raise ValueError("bathrooms cannot be negative")
        if self.lease_years_remaining is not None and self.lease_years_remaining < 0:
            raise ValueError("lease_years_remaining cannot be negative")

        # Generate IDs if not provided
        if not self.property_id:
            object.__setattr__(self, "property_id", generate_property_id())
        if not self.submission_id:
            object.__setattr__(self, "submission_id", generate_submission_id())

    @property
    def is_leasehold(self) -> bool:
        """Check if property is leasehold."""
        return self.tenure == Tenure.LEASEHOLD

    @property
    def required_document_types(self) -> tuple[DocumentType, ...]:
        """Get required document types for this submission."""
        required = list(REQUIRED_DOCUMENTS)
        if self.is_leasehold:
            required.extend(LEASEHOLD_REQUIRED_DOCUMENTS)
        return tuple(required)

    @property
    def uploaded_document_types(self) -> set[DocumentType]:
        """Get set of document types that have been uploaded."""
        return {doc.document_type for doc in self.documents}

    @property
    def missing_documents(self) -> list[DocumentType]:
        """Get list of required documents that are missing."""
        uploaded = self.uploaded_document_types
        return [dt for dt in self.required_document_types if dt not in uploaded]

    @property
    def has_all_required_documents(self) -> bool:
        """Check if all required documents have been uploaded."""
        return len(self.missing_documents) == 0

    @property
    def is_complete(self) -> bool:
        """Check if submission is complete (all fields and documents)."""
        return self.has_all_required_documents

    def get_document(self, document_type: DocumentType) -> Optional[DocumentRecord]:
        """Get document by type."""
        for doc in self.documents:
            if doc.document_type == document_type:
                return doc
        return None

    def add_document(self, document: DocumentRecord) -> None:
        """Add a document to the submission."""
        # Replace if same type already exists
        self.documents = [d for d in self.documents if d.document_type != document.document_type]
        self.documents.append(document)
        self._update_status()

    def _update_status(self) -> None:
        """Update submission status based on completeness."""
        if self.has_all_required_documents:
            if self.status == SubmissionStatus.DRAFT:
                object.__setattr__(self, "status", SubmissionStatus.SUBMITTED)
        else:
            if self.status in (SubmissionStatus.DRAFT, SubmissionStatus.SUBMITTED):
                object.__setattr__(self, "status", SubmissionStatus.INCOMPLETE)

    def to_dict(self) -> dict:
        """Convert submission to dictionary for serialisation."""
        return {
            "property_id": self.property_id,
            "submission_id": self.submission_id,
            "full_address": self.full_address,
            "postcode": self.postcode,
            "property_type": self.property_type.value,
            "tenure": self.tenure.value,
            "floor_area_sqm": self.floor_area_sqm,
            "guide_price": self.guide_price,
            "sale_route": self.sale_route.value,
            "agent_firm": self.agent_firm,
            "agent_name": self.agent_name,
            "agent_email": self.agent_email,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "year_built": self.year_built,
            "council_tax_band": self.council_tax_band,
            "epc_rating": self.epc_rating,
            "lease_years_remaining": self.lease_years_remaining,
            "ground_rent_annual": self.ground_rent_annual,
            "service_charge_annual": self.service_charge_annual,
            "documents": [doc.to_dict() for doc in self.documents],
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "status": self.status.value,
            "is_complete": self.is_complete,
            "missing_documents": [dt.value for dt in self.missing_documents],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentSubmission":
        """Create submission from dictionary."""
        # Parse enums
        property_type = data.get("property_type")
        if isinstance(property_type, str):
            property_type = PropertyType(property_type.replace("_", "-"))

        tenure = data.get("tenure")
        if isinstance(tenure, str):
            tenure = Tenure(tenure)

        sale_route = data.get("sale_route")
        if isinstance(sale_route, str):
            sale_route = SaleRoute(sale_route)

        # Parse documents
        documents = []
        for doc_data in data.get("documents", []):
            doc_type = doc_data.get("document_type")
            if isinstance(doc_type, str):
                doc_type = DocumentType(doc_type)
            documents.append(
                DocumentRecord(
                    document_id=doc_data["document_id"],
                    document_type=doc_type,
                    filename=doc_data["filename"],
                    file_extension=doc_data["file_extension"],
                    file_size_bytes=doc_data["file_size_bytes"],
                    content_hash=doc_data["content_hash"],
                    uploaded_at=datetime.fromisoformat(doc_data["uploaded_at"]),
                    storage_path=doc_data["storage_path"],
                )
            )

        submission = cls(
            full_address=data["full_address"],
            postcode=data["postcode"],
            property_type=property_type,
            tenure=tenure,
            floor_area_sqm=data["floor_area_sqm"],
            guide_price=data["guide_price"],
            sale_route=sale_route,
            agent_firm=data["agent_firm"],
            agent_name=data["agent_name"],
            agent_email=data["agent_email"],
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            year_built=data.get("year_built"),
            council_tax_band=data.get("council_tax_band"),
            epc_rating=data.get("epc_rating"),
            lease_years_remaining=data.get("lease_years_remaining"),
            ground_rent_annual=data.get("ground_rent_annual"),
            service_charge_annual=data.get("service_charge_annual"),
            documents=documents,
            property_id=data.get("property_id"),
            submission_id=data.get("submission_id"),
        )

        # Restore status
        if data.get("status"):
            object.__setattr__(submission, "status", SubmissionStatus(data["status"]))

        # Restore timestamp
        if data.get("submitted_at"):
            object.__setattr__(
                submission, "submitted_at", datetime.fromisoformat(data["submitted_at"])
            )

        return submission
