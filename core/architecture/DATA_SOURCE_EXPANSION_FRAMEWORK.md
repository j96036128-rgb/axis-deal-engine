# Data Source Expansion Framework (DSXF)
## Version 1.0

**Document Classification:** Proprietary — Axis Allocation IP
**Version:** 1.0.0
**Effective Date:** 2026-01-17
**Related:** Deal Engine v1.1 Specification

---

## 1. Overview

The Data Source Expansion Framework (DSXF) defines the canonical approach for integrating new property listing sources into the Axis Deal Engine. It enforces strict normalisation, prevents source-specific scoring contamination, and guarantees data integrity.

### 1.1 Design Principles

1. **Source Agnostic** — The Deal Engine treats all sources identically after normalisation
2. **Single Schema** — All sources normalise to one `ValidatedAsset` schema
3. **Metadata Only** — Source identity is metadata; it never affects scoring
4. **No Fabrication** — Missing data is missing; never fabricated or inferred
5. **Explicit Failure** — Sources that cannot conform are rejected, not adapted

### 1.2 Supported Source Categories

| Category | Description | Examples |
|----------|-------------|----------|
| Auction | UK auction house catalogues | Auction House London, Allsop, SDL |
| Receivership | Insolvency and receiver sales | LPA Receivers, Administrators |
| Distressed | Off-market distressed assets | Direct vendor, introducer networks |
| Future | Reserved for expansion | REO, repossession, probate |

---

## 2. Source Registration

### 2.1 Source Registry

Every data source must be formally registered before integration:

```python
@dataclass(frozen=True)
class SourceRegistration:
    """Immutable source registration record."""

    # Identity
    source_id: str                    # Unique identifier (e.g., "auction_house_london")
    source_name: str                  # Display name (e.g., "Auction House London")
    source_category: SourceCategory   # AUCTION | RECEIVERSHIP | DISTRESSED | OTHER

    # Classification
    is_auction: bool                  # True if auction-based pricing
    is_distressed: bool               # True if insolvency/receivership
    is_off_market: bool               # True if not publicly listed

    # Data quality
    provides_tenure: bool             # Source includes tenure data
    provides_property_type: bool      # Source includes property type
    provides_bedrooms: bool           # Source includes bedroom count
    provides_coordinates: bool        # Source includes lat/lng

    # Operational
    rate_limit_seconds: float         # Minimum delay between requests
    requires_authentication: bool     # API key or login required
    active: bool                      # Currently enabled

    # Audit
    registered_date: date
    last_verified_date: date
```

### 2.2 Registration Rules

```
RULE REG-001: Source ID must be unique across all registered sources
RULE REG-002: Source ID must be lowercase alphanumeric with underscores only
RULE REG-003: Source must declare which fields it provides accurately
RULE REG-004: Source must be re-verified quarterly for data quality
RULE REG-005: Inactive sources are retained in registry but not queried
```

### 2.3 Example Registrations

```python
SOURCE_REGISTRY = {
    "auction_house_london": SourceRegistration(
        source_id="auction_house_london",
        source_name="Auction House London",
        source_category=SourceCategory.AUCTION,
        is_auction=True,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=False,
        provides_coordinates=False,
        rate_limit_seconds=1.5,
        requires_authentication=False,
        active=True,
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    ),

    "allsop_auctions": SourceRegistration(
        source_id="allsop_auctions",
        source_name="Allsop Auctions",
        source_category=SourceCategory.AUCTION,
        is_auction=True,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_coordinates=False,
        rate_limit_seconds=2.0,
        requires_authentication=False,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    ),

    "lpa_receivers_direct": SourceRegistration(
        source_id="lpa_receivers_direct",
        source_name="LPA Receivers Direct Feed",
        source_category=SourceCategory.RECEIVERSHIP,
        is_auction=False,
        is_distressed=True,
        is_off_market=True,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_coordinates=True,
        rate_limit_seconds=0,  # Push-based
        requires_authentication=True,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    ),
}
```

---

## 3. ValidatedAsset Schema

### 3.1 Canonical Schema Definition

All sources MUST normalise to this exact schema. No source-specific fields are permitted in the core schema.

```python
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional


class PropertyType(Enum):
    """Normalised property types — no source-specific variants."""
    FLAT = "flat"
    MAISONETTE = "maisonette"
    TERRACED = "terraced"
    SEMI_DETACHED = "semi_detached"
    DETACHED = "detached"


class Tenure(Enum):
    """Normalised tenure types."""
    FREEHOLD = "freehold"
    LEASEHOLD = "leasehold"


class ListingStatus(Enum):
    """Current listing status."""
    ACTIVE = "active"
    UNDER_OFFER = "under_offer"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class SourceMetadata:
    """
    Source-specific information that does NOT affect scoring.
    Retained for audit trail and provenance only.
    """
    source_id: str                      # Registered source identifier
    source_name: str                    # Human-readable source name
    source_listing_id: str              # Original ID from source
    source_url: str                     # Original listing URL
    source_category: SourceCategory     # AUCTION | RECEIVERSHIP | etc.

    # Auction-specific (metadata only)
    auction_date: Optional[date] = None
    lot_number: Optional[str] = None

    # Receivership-specific (metadata only)
    receiver_name: Optional[str] = None
    insolvency_type: Optional[str] = None

    # Timestamps
    source_scraped_at: Optional[datetime] = None
    source_last_modified: Optional[datetime] = None


@dataclass(frozen=True)
class ValidatedAsset:
    """
    Canonical normalised property record.

    This is the ONLY schema that enters the Deal Engine pipeline.
    All source-specific data is either normalised into these fields
    or retained as metadata (which never affects scoring).
    """

    # === IDENTITY (Required) ===
    asset_id: str                       # Globally unique ID (generated)
    address: str                        # Full street address
    postcode: str                       # UK postcode (validated format)
    city: str                           # City or town
    area: Optional[str]                 # Local area or neighbourhood

    # === PROPERTY ATTRIBUTES (Required) ===
    property_type: PropertyType         # Normalised type (exact match for comps)
    tenure: Tenure                      # Normalised tenure (exact match for comps)

    # === PROPERTY ATTRIBUTES (Optional) ===
    bedrooms: Optional[int] = None      # Bedroom count (if available)
    bathrooms: Optional[int] = None     # Bathroom count (if available)
    square_feet: Optional[int] = None   # Internal floor area
    plot_acres: Optional[float] = None  # Plot size for houses

    # === PRICING (Required) ===
    asking_price: int                   # Current asking/guide price in GBP
    price_qualifier: Optional[str] = None  # "guide", "reserve", "offers over"

    # === LISTING STATUS (Required) ===
    listing_status: ListingStatus       # Current status
    listing_date: date                  # Date first listed
    days_on_market: int                 # Calculated from listing_date

    # === LOCATION (Optional - for comp radius) ===
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # === SOURCE METADATA (Required - does NOT affect scoring) ===
    source: SourceMetadata

    # === AUDIT (Required) ===
    validated_at: datetime              # When this record was created
    schema_version: str = "1.0"         # Schema version for migrations

    def __post_init__(self):
        """Validation rules enforced at construction."""
        if self.asking_price <= 0:
            raise ValueError("asking_price must be positive")
        if self.bedrooms is not None and self.bedrooms < 0:
            raise ValueError("bedrooms cannot be negative")
        if self.bathrooms is not None and self.bathrooms < 0:
            raise ValueError("bathrooms cannot be negative")
```

### 3.2 Schema Invariants

```
INVARIANT S-001: asset_id is globally unique and immutable
INVARIANT S-002: property_type is one of exactly five normalised values
INVARIANT S-003: tenure is one of exactly two normalised values
INVARIANT S-004: asking_price is always a positive integer in GBP
INVARIANT S-005: source metadata NEVER influences scoring
INVARIANT S-006: ValidatedAsset is immutable (frozen dataclass)
```

### 3.3 Fields That NEVER Exist

The following fields are explicitly prohibited:

```
PROHIBITED: estimated_value    — EMV is calculated by Deal Engine, not provided
PROHIBITED: bmv_percent        — Calculated by Deal Engine, not provided
PROHIBITED: score              — Calculated by Deal Engine, not provided
PROHIBITED: recommendation     — Calculated by Deal Engine, not provided
PROHIBITED: source_score_*     — No source-specific scoring fields
PROHIBITED: fallback_*         — No fallback or default values
```

---

## 4. Source Integration Rules

### 4.1 Adapter Interface

Every source must implement this interface:

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional


class SourceAdapter(ABC):
    """
    Abstract interface for all data source integrations.

    Adapters are responsible for:
    1. Fetching raw data from the source
    2. Normalising to ValidatedAsset schema
    3. Rejecting records that cannot be normalised
    """

    @property
    @abstractmethod
    def source_registration(self) -> SourceRegistration:
        """Return the source's registration record."""
        ...

    @abstractmethod
    async def fetch_listings(
        self,
        since: Optional[datetime] = None
    ) -> AsyncIterator[ValidatedAsset]:
        """
        Fetch and normalise listings from the source.

        Args:
            since: Only fetch listings modified after this time (if supported)

        Yields:
            ValidatedAsset records that pass normalisation

        Note:
            Records that cannot be normalised are logged and skipped.
            This method NEVER yields partially-populated records.
        """
        ...

    @abstractmethod
    async def fetch_single(
        self,
        source_listing_id: str
    ) -> Optional[ValidatedAsset]:
        """
        Fetch a single listing by its source-specific ID.

        Returns:
            ValidatedAsset if found and normalisable, None otherwise
        """
        ...

    def normalise_property_type(self, raw_type: str) -> Optional[PropertyType]:
        """
        Map source-specific property type to normalised enum.

        Returns None if unmappable (record will be rejected).
        """
        ...

    def normalise_tenure(self, raw_tenure: str) -> Optional[Tenure]:
        """
        Map source-specific tenure to normalised enum.

        Returns None if unmappable (record will be rejected).
        """
        ...
```

### 4.2 Normalisation Rules

```
RULE N-001: Every adapter must define explicit type mappings — no wildcards
RULE N-002: Unmappable property types result in record rejection
RULE N-003: Unmappable tenures result in record rejection
RULE N-004: Missing required fields result in record rejection
RULE N-005: Adapters NEVER infer missing required data
RULE N-006: Optional fields may be None but NEVER fabricated
```

### 4.3 Property Type Mapping Standard

Each adapter must document its mappings:

```python
# Example: Auction House London adapter mappings
PROPERTY_TYPE_MAP = {
    # Direct mappings
    "flat": PropertyType.FLAT,
    "apartment": PropertyType.FLAT,
    "studio": PropertyType.FLAT,
    "maisonette": PropertyType.MAISONETTE,
    "terraced": PropertyType.TERRACED,
    "terrace": PropertyType.TERRACED,
    "terraced house": PropertyType.TERRACED,
    "end of terrace": PropertyType.TERRACED,
    "mid terrace": PropertyType.TERRACED,
    "town house": PropertyType.TERRACED,
    "semi-detached": PropertyType.SEMI_DETACHED,
    "semi detached": PropertyType.SEMI_DETACHED,
    "detached": PropertyType.DETACHED,
    "detached house": PropertyType.DETACHED,
    "bungalow": PropertyType.DETACHED,
    "cottage": PropertyType.DETACHED,

    # Explicitly unmapped (will reject)
    # "land": None,
    # "commercial": None,
    # "mixed use": None,
    # "garage": None,
}
```

### 4.4 Tenure Mapping Standard

```python
TENURE_MAP = {
    # Direct mappings
    "freehold": Tenure.FREEHOLD,
    "share of freehold": Tenure.FREEHOLD,
    "leasehold": Tenure.LEASEHOLD,

    # Explicitly unmapped (will reject)
    # "unknown": None,
    # "tbc": None,
}
```

---

## 5. Guardrails

### 5.1 Scoring Contamination Prevention

The following rules MUST be enforced to prevent source-specific logic from affecting scores:

```
GUARDRAIL G-001: SourceMetadata fields are NEVER read by scoring functions
GUARDRAIL G-002: Source category (auction, receivership, etc.) does NOT affect scoring
GUARDRAIL G-003: Auction date does NOT affect urgency score
GUARDRAIL G-004: Source-specific price qualifiers do NOT affect BMV calculation
GUARDRAIL G-005: No conditional logic based on source_id in Deal Engine core
```

### 5.2 Implementation Enforcement

```python
# CORRECT: Scoring uses only ValidatedAsset core fields
def calculate_bmv_score(asset: ValidatedAsset, emv: int) -> float:
    bmv_percent = ((emv - asset.asking_price) / emv) * 100
    return _score_from_percent(bmv_percent)

# INCORRECT: Source-specific logic — PROHIBITED
def calculate_bmv_score_wrong(asset: ValidatedAsset, emv: int) -> float:
    bmv_percent = ((emv - asset.asking_price) / emv) * 100

    # THIS IS PROHIBITED — source should not affect scoring
    if asset.source.source_category == SourceCategory.AUCTION:
        bmv_percent += 5  # "Auction discount"

    return _score_from_percent(bmv_percent)
```

### 5.3 Code Review Checklist

Before merging any Deal Engine changes:

- [ ] No imports of SourceMetadata in scoring modules
- [ ] No conditional logic based on source_id
- [ ] No conditional logic based on source_category
- [ ] No source-specific score adjustments
- [ ] No source-specific recommendation logic
- [ ] ValidatedAsset is the only input to scoring functions

---

## 6. Data Quality Controls

### 6.1 Rejection Logging

All rejected records must be logged with explicit reasons:

```python
@dataclass
class RejectionRecord:
    """Record of a listing that failed normalisation."""

    source_id: str
    source_listing_id: str
    rejection_code: str
    rejection_reason: str
    raw_data_hash: str          # For debugging without storing PII
    rejected_at: datetime

# Rejection codes
REJECTION_CODES = {
    "MISSING_ADDRESS": "Required field 'address' not provided",
    "MISSING_POSTCODE": "Required field 'postcode' not provided",
    "INVALID_POSTCODE": "Postcode format validation failed",
    "MISSING_PROPERTY_TYPE": "Required field 'property_type' not provided",
    "UNMAPPED_PROPERTY_TYPE": "Property type could not be normalised",
    "MISSING_TENURE": "Required field 'tenure' not provided",
    "UNMAPPED_TENURE": "Tenure could not be normalised",
    "MISSING_PRICE": "Required field 'asking_price' not provided",
    "INVALID_PRICE": "Asking price is not a positive integer",
    "MISSING_LISTING_DATE": "Required field 'listing_date' not provided",
    "FUTURE_LISTING_DATE": "Listing date is in the future",
}
```

### 6.2 Quality Metrics

Track per-source quality metrics:

```python
@dataclass
class SourceQualityMetrics:
    """Quality metrics for a data source."""

    source_id: str
    period_start: datetime
    period_end: datetime

    # Volume
    total_fetched: int
    total_normalised: int
    total_rejected: int

    # Quality ratios
    normalisation_rate: float       # normalised / fetched
    rejection_rate: float           # rejected / fetched

    # Rejection breakdown
    rejections_by_code: dict[str, int]

    # Alerts
    requires_attention: bool        # True if rejection_rate > 20%
```

### 6.3 Quality Thresholds

```
THRESHOLD Q-001: Normalisation rate must be >= 80% (alert if lower)
THRESHOLD Q-002: Any single rejection code > 10% triggers investigation
THRESHOLD Q-003: Zero valid listings from active source triggers alert
THRESHOLD Q-004: Source with < 60% normalisation rate for 7 days is deactivated
```

---

## 7. Future Source Categories

### 7.1 Planned Integrations

| Category | Priority | Status | Target Date |
|----------|----------|--------|-------------|
| UK Auction Houses (top 10) | High | In Progress | Q1 2026 |
| LPA Receiver Networks | High | Specification | Q2 2026 |
| Probate/Estate Sales | Medium | Research | Q3 2026 |
| Bank REO Feeds | Medium | Research | Q3 2026 |
| Introducer Networks | Low | Planned | Q4 2026 |

### 7.2 Integration Checklist

For each new source:

1. [ ] Source registered in SOURCE_REGISTRY
2. [ ] Property type mappings documented and approved
3. [ ] Tenure mappings documented and approved
4. [ ] SourceAdapter implementation complete
5. [ ] Unit tests for normalisation logic
6. [ ] Integration tests with sample data
7. [ ] Rejection logging implemented
8. [ ] Quality metrics dashboard updated
9. [ ] Rate limiting configured
10. [ ] Documentation complete

---

## 8. Prohibited Practices

### 8.1 Never Do

```
PROHIBITED P-001: Never fabricate missing data
PROHIBITED P-002: Never use placeholder/dummy values in production
PROHIBITED P-003: Never infer property type from address
PROHIBITED P-004: Never infer tenure from property type alone
PROHIBITED P-005: Never assign default coordinates
PROHIBITED P-006: Never backfill data from third-party sources
PROHIBITED P-007: Never apply source-specific score bonuses/penalties
PROHIBITED P-008: Never skip validation for "trusted" sources
```

### 8.2 Enforcement

Violations of prohibited practices are treated as critical bugs requiring immediate remediation.

---

## 9. Appendix A: Source Category Definitions

### Auction Sources

Properties sold through regulated UK auction houses. Characteristics:
- Public marketing with fixed auction date
- Guide prices (not guaranteed sale prices)
- Legal pack available pre-auction
- Typical completion: 28 days post-auction

### Receivership Sources

Properties sold by LPA Receivers or Insolvency Practitioners. Characteristics:
- Motivated seller (lender enforcement)
- May be off-market initially
- Often requires speed of completion
- Legal complexity varies

### Distressed Sources

Properties sold under financial or personal distress. Characteristics:
- May include probate, divorce, or relocation
- Often off-market or quiet marketing
- Pricing may not reflect market value
- Due diligence critical

---

## 10. Appendix B: ValidatedAsset JSON Example

```json
{
  "asset_id": "va-20260117-ahl-12345",
  "address": "Flat 3, Victoria Mansions, 42 High Street",
  "postcode": "SW1A 1AA",
  "city": "London",
  "area": "Westminster",
  "property_type": "flat",
  "tenure": "leasehold",
  "bedrooms": 2,
  "bathrooms": 1,
  "square_feet": null,
  "plot_acres": null,
  "asking_price": 350000,
  "price_qualifier": "guide",
  "listing_status": "active",
  "listing_date": "2026-01-10",
  "days_on_market": 7,
  "latitude": 51.5014,
  "longitude": -0.1419,
  "source": {
    "source_id": "auction_house_london",
    "source_name": "Auction House London",
    "source_listing_id": "AHL-2026-12345",
    "source_url": "https://auctionhouselondon.co.uk/lot/12345",
    "source_category": "auction",
    "auction_date": "2026-02-15",
    "lot_number": "42",
    "receiver_name": null,
    "insolvency_type": null,
    "source_scraped_at": "2026-01-17T10:30:00Z",
    "source_last_modified": "2026-01-16T14:00:00Z"
  },
  "validated_at": "2026-01-17T10:30:15Z",
  "schema_version": "1.0"
}
```

---

**Document Control**

This framework is proprietary to Axis Allocation. All source integrations must comply with this specification. Modifications require approval from the Deal Engine Architecture Board.
