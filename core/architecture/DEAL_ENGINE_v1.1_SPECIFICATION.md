# Axis Allocation Deal Engine v1.1
## Canonical Architecture Specification

**Document Classification:** Proprietary — Axis Allocation IP
**Version:** 1.1.0
**Effective Date:** 2026-01-17
**Supersedes:** All prior heuristic-based BMV logic

---

## 1. Overview

The Axis Deal Engine is the core computational system for identifying, validating, and ranking property-linked investment opportunities. It operates as an internal tool for institutional and qualified capital deployment.

### 1.1 Design Principles

1. **No Fabrication** — The engine never fabricates, infers, or backfills data
2. **Comp-Based Only** — All market value estimates derive from UK Land Registry completed sales
3. **Deterministic** — Identical inputs always produce identical outputs
4. **Fail-Safe** — Zero-result outputs are valid and handled gracefully
5. **Audit-Ready** — Every decision is traceable to explicit rules

### 1.2 Pipeline Stages (Immutable)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DEAL ENGINE v1.1 PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [1] INGESTION ──► [2] STRUCTURAL ──► [3] MARKET ──► [4] CONFIDENCE    │
│      (Raw Only)       VALIDATION       REALITY       GATING            │
│                       (Hard Rules)     (EMV Calc)    (Caps)            │
│                                                                         │
│                                    ──► [5] SCORING ──► [6] OUTPUT      │
│                                        & RANKING       CLASSIFICATION  │
│                                        (Deterministic) (Final Rating)  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage 1: Ingestion

### 2.1 Purpose

Accept raw property listings from any configured source. No inference, enrichment, or value estimation occurs at this stage.

### 2.2 Input Requirements

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `source_id` | string | Yes | Unique within source |
| `source_name` | string | Yes | Registered source identifier |
| `address` | string | Yes | Non-empty |
| `postcode` | string | Yes | Valid UK postcode format |
| `property_type` | string | Yes | Raw source value (normalised later) |
| `tenure` | string | Yes | Raw source value (normalised later) |
| `asking_price` | integer | Yes | > 0, in GBP |
| `bedrooms` | integer | No | >= 0 if provided |
| `bathrooms` | integer | No | >= 0 if provided |
| `listing_date` | date | Yes | ISO 8601 format |
| `listing_url` | string | Yes | Valid URL |

### 2.3 Ingestion Rules

```
RULE I-001: No field shall be inferred from other fields
RULE I-002: No default values shall be assigned to missing required fields
RULE I-003: Missing required fields result in immediate rejection
RULE I-004: Source-provided estimated values are IGNORED — never ingested
RULE I-005: All monetary values must be integers in GBP (no pence)
```

### 2.4 Output

`RawListing` objects passed to Stage 2, or rejected with explicit error codes.

---

## 3. Stage 2: Structural Validation

### 3.1 Purpose

Apply hard rejection rules to eliminate invalid or unsuitable listings before any market analysis.

### 3.2 Validation Schema

```python
@dataclass
class StructuralValidation:
    """Hard rejection rules — no exceptions."""

    # Field presence
    REQUIRED_FIELDS: Final = [
        'source_id', 'source_name', 'address', 'postcode',
        'property_type', 'tenure', 'asking_price', 'listing_date', 'listing_url'
    ]

    # Type constraints
    VALID_PROPERTY_TYPES: Final = [
        'flat', 'maisonette', 'terraced', 'semi-detached', 'detached'
    ]

    VALID_TENURES: Final = ['freehold', 'leasehold']

    # Value constraints
    MIN_ASKING_PRICE: Final = 10_000   # Below this is likely data error
    MAX_ASKING_PRICE: Final = 50_000_000  # Commercial threshold
```

### 3.3 Rejection Rules

```
RULE V-001: Missing required field → REJECT (code: MISSING_REQUIRED_FIELD)
RULE V-002: Invalid postcode format → REJECT (code: INVALID_POSTCODE)
RULE V-003: Property type not in VALID_PROPERTY_TYPES → REJECT (code: UNMAPPED_PROPERTY_TYPE)
RULE V-004: Tenure not in VALID_TENURES → REJECT (code: UNMAPPED_TENURE)
RULE V-005: Asking price < MIN_ASKING_PRICE → REJECT (code: PRICE_BELOW_THRESHOLD)
RULE V-006: Asking price > MAX_ASKING_PRICE → REJECT (code: PRICE_ABOVE_THRESHOLD)
RULE V-007: Listing date in future → REJECT (code: FUTURE_LISTING_DATE)
RULE V-008: Listing date > 365 days old → REJECT (code: STALE_LISTING)
```

### 3.4 Property Type Normalisation

| Source Input | Normalised Type |
|--------------|-----------------|
| `flat`, `apartment`, `studio` | `FLAT` |
| `maisonette` | `MAISONETTE` |
| `terraced`, `terrace`, `end terrace`, `mid terrace`, `townhouse` | `TERRACED` |
| `semi-detached`, `semi detached`, `semi` | `SEMI_DETACHED` |
| `detached`, `bungalow`, `cottage` | `DETACHED` |

**Note:** Normalisation is case-insensitive. Unmapped types are rejected.

### 3.5 Output

`ValidatedAsset` objects passed to Stage 3, or rejection records logged with codes.

---

## 4. Stage 3: Market Reality Layer

### 4.1 Purpose

Calculate Estimated Market Value (EMV) using exclusively UK Land Registry completed sales data. This stage replaces all prior heuristic-based BMV logic.

### 4.2 Data Source Constraint

```
NON-NEGOTIABLE: EMV calculations use ONLY UK Land Registry Price Paid Data
               from COMPLETED SALES. No estimates, AVMs, or third-party
               valuations are permitted.
```

### 4.3 Comparable Selection Criteria

#### 4.3.1 Hard Filters (Non-Negotiable)

| Filter | Rule | Rationale |
|--------|------|-----------|
| Property Type | EXACT MATCH | Flats ≠ houses ≠ maisonettes |
| Tenure | EXACT MATCH | Freehold ≠ leasehold |
| Maximum Age | 24 months | Older data may not reflect current market |

#### 4.3.2 Progressive Radius Expansion

The system attempts to find comparables in order of preference:

```
Level 1: 0.5 miles, 12 months — PREFERRED (High confidence eligible)
Level 2: 1.0 miles, 12 months — ACCEPTABLE (Medium confidence)
Level 3: 0.5 miles, 18 months — ACCEPTABLE (Medium confidence)
Level 4: 1.0 miles, 18 months — ACCEPTABLE (Medium confidence)
Level 5: 1.0 miles, 24 months — FALLBACK (Low confidence)
Level 6: 1.5 miles, 24 months — MAXIMUM FALLBACK (Low confidence)
```

#### 4.3.3 Minimum Comparable Thresholds

```
TARGET:    5 comps (enables outlier removal, High confidence eligible)
ACCEPTABLE: 3 comps (minimum for meaningful EMV)
FALLBACK:  1-2 comps (proceed with Low confidence)
ZERO:      0 comps (valid output — see Section 4.6)
```

### 4.4 EMV Calculation

```
EMV = MEDIAN(comparable_prices)
```

**Why Median, Not Mean:**
- Resistant to outliers
- More representative of typical market value
- Standard practice in professional valuations

#### 4.4.1 Outlier Removal

Applied ONLY when >= 5 comparables available:

```
1. Sort comparables by price ascending
2. Remove bottom 10th percentile
3. Remove top 90th percentile
4. Calculate median of remaining
```

**If < 5 comparables:** No outlier removal — use all available.

### 4.5 BMV Percentage Calculation

```
BMV% = ((EMV - Asking_Price) / EMV) * 100
```

- Positive BMV% = Below market value (discount)
- Negative BMV% = Overpriced (premium)
- Zero EMV = No calculation possible (see Section 4.6)

### 4.6 Zero-Comp Handling

When no valid comparables exist:

```
EMV = 0 (explicit null equivalent)
BMV% = 0
Confidence = LOW
Recommendation = INSUFFICIENT_DATA
```

This is a VALID output state, not an error.

### 4.7 Output

`MarketAnalysis` containing:
- `emv`: integer (0 if no comps)
- `bmv_percent`: float
- `comps_used`: integer
- `comp_prices`: list[int] (audit trail)
- `comp_radius_miles`: float
- `comp_date_range_months`: integer
- `fallback_level`: integer (1-6)

---

## 5. Stage 4: Confidence Gating

### 5.1 Purpose

Assign confidence levels based on comparable evidence quality. Apply caps to prevent overstating confidence.

### 5.2 Confidence Levels

| Level | Criteria | Recommendation Cap |
|-------|----------|-------------------|
| HIGH | >= 5 comps AND <= 12 months AND <= 0.5 miles | None |
| MEDIUM | 3-4 comps OR <= 18 months OR <= 1.0 miles | STRONG max |
| LOW | < 3 comps OR fallback criteria used | MODERATE max |

### 5.3 Confidence Assignment Rules

```python
def assign_confidence(market_analysis: MarketAnalysis) -> Confidence:
    comps = market_analysis.comps_used
    radius = market_analysis.comp_radius_miles
    months = market_analysis.comp_date_range_months

    if comps >= 5 and months <= 12 and radius <= 0.5:
        return Confidence.HIGH
    elif comps >= 3 and months <= 18 and radius <= 1.0:
        return Confidence.MEDIUM
    else:
        return Confidence.LOW
```

### 5.4 Recommendation Caps

```
RULE C-001: LOW confidence → Maximum recommendation is MODERATE
RULE C-002: < 3 comps → Maximum recommendation is WEAK
RULE C-003: 0 comps → Fixed recommendation is INSUFFICIENT_DATA
RULE C-004: Caps can only DOWNGRADE, never UPGRADE
```

### 5.5 Output

`ConfidenceGatedAnalysis` containing:
- All fields from `MarketAnalysis`
- `confidence`: HIGH | MEDIUM | LOW
- `recommendation_cap`: Optional[Recommendation]

---

## 6. Stage 5: Scoring & Ranking

### 6.1 Purpose

Calculate deterministic scores for each validated asset and rank opportunities.

### 6.2 Score Components

| Component | Weight | Range | Source |
|-----------|--------|-------|--------|
| BMV Score | 50% | 0-100 | Market Reality Layer |
| Urgency Score | 20% | 0-100 | Days on market |
| Location Score | 15% | 0-100 | Reserved (default: 50) |
| Value Score | 15% | 0-100 | Price tier alignment |

### 6.3 BMV Score Calculation

```python
def calculate_bmv_score(bmv_percent: float, confidence: Confidence) -> float:
    if bmv_percent <= 0:
        return 0.0

    # Base score from BMV percentage
    if bmv_percent >= 20:
        base = 80 + min((bmv_percent - 20) * 2, 20)  # 80-100
    elif bmv_percent >= 10:
        base = 50 + (bmv_percent - 10) * 3  # 50-80
    elif bmv_percent >= 5:
        base = 25 + (bmv_percent - 5) * 5  # 25-50
    else:
        base = bmv_percent * 5  # 0-25

    # Apply confidence modifier
    modifiers = {
        Confidence.HIGH: 1.0,
        Confidence.MEDIUM: 0.85,
        Confidence.LOW: 0.70
    }

    return base * modifiers[confidence]
```

### 6.4 Urgency Score Calculation

```python
def calculate_urgency_score(days_on_market: int) -> float:
    if days_on_market >= 90:
        return 70 + min((days_on_market - 90) / 3, 30)  # 70-100
    elif days_on_market >= 60:
        return 40 + (days_on_market - 60)  # 40-70
    elif days_on_market >= 30:
        return 20 + (days_on_market - 30) * (20/30)  # 20-40
    else:
        return days_on_market * (20/30)  # 0-20
```

### 6.5 Overall Score Calculation

```python
def calculate_overall_score(
    bmv_score: float,
    urgency_score: float,
    location_score: float,
    value_score: float
) -> float:
    return (
        bmv_score * 0.50 +
        urgency_score * 0.20 +
        location_score * 0.15 +
        value_score * 0.15
    )
```

### 6.6 Ranking Rules

```
RULE R-001: Primary sort by overall_score DESC
RULE R-002: Secondary sort by bmv_percent DESC (tiebreaker)
RULE R-003: Tertiary sort by asking_price ASC (tiebreaker)
RULE R-004: Sorting is stable and deterministic
```

### 6.7 Output

`ScoredAsset` containing:
- All fields from `ConfidenceGatedAnalysis`
- `bmv_score`: float
- `urgency_score`: float
- `location_score`: float
- `value_score`: float
- `overall_score`: float
- `rank`: integer (1-indexed)

---

## 7. Stage 6: Output Classification

### 7.1 Purpose

Assign final investment recommendations based on scores and confidence gates.

### 7.2 Recommendation Bands

| Classification | Criteria | Action Guidance |
|---------------|----------|-----------------|
| **STRONG** | BMV% >= 15 AND overall_score >= 70 AND confidence != LOW | Priority review |
| **MODERATE** | BMV% >= 8 AND overall_score >= 50 | Standard review |
| **WEAK** | BMV% >= 3 AND overall_score >= 30 | Low priority |
| **AVOID** | BMV% < 3 OR overall_score < 30 | Do not pursue |
| **OVERPRICED** | BMV% < 0 | Reject — above market |
| **INSUFFICIENT_DATA** | comps_used == 0 | Cannot assess |

### 7.3 Classification Logic

```python
def classify(
    bmv_percent: float,
    overall_score: float,
    confidence: Confidence,
    comps_used: int,
    recommendation_cap: Optional[Recommendation]
) -> Recommendation:

    # Handle zero-comp case
    if comps_used == 0:
        return Recommendation.INSUFFICIENT_DATA

    # Handle overpriced
    if bmv_percent < 0:
        return Recommendation.OVERPRICED

    # Calculate base recommendation
    if bmv_percent >= 15 and overall_score >= 70:
        base = Recommendation.STRONG
    elif bmv_percent >= 8 and overall_score >= 50:
        base = Recommendation.MODERATE
    elif bmv_percent >= 3 and overall_score >= 30:
        base = Recommendation.WEAK
    else:
        base = Recommendation.AVOID

    # Apply confidence cap
    if recommendation_cap and base.value > recommendation_cap.value:
        return recommendation_cap

    return base
```

### 7.4 Output

`ClassifiedOpportunity` — the final output record containing:
- All prior stage data
- `recommendation`: STRONG | MODERATE | WEAK | AVOID | OVERPRICED | INSUFFICIENT_DATA
- `classification_reason`: string explaining the decision

---

## 8. Failure Modes

### 8.1 Defined Failure States

| Failure Mode | Cause | System Response |
|--------------|-------|-----------------|
| `INGESTION_REJECTED` | Invalid raw data | Log rejection, continue |
| `VALIDATION_FAILED` | Structural rule violation | Log rejection code, continue |
| `NO_COMPARABLES` | Zero valid comps found | Output INSUFFICIENT_DATA |
| `LOW_COMPARABLES` | < 3 comps found | Apply LOW confidence cap |
| `STALE_COMPS_ONLY` | All comps > 18 months | Apply LOW confidence cap |
| `WIDE_RADIUS_ONLY` | All comps > 1.0 miles | Apply LOW confidence cap |

### 8.2 Non-Recoverable Failures

```
- Land Registry API unavailable → Halt processing, alert
- Database connection lost → Halt processing, alert
- Invalid configuration → Refuse to start
```

### 8.3 Graceful Degradation

The system MUST produce valid output (including INSUFFICIENT_DATA) for any valid input. Partial failures do not cascade.

---

## 9. Non-Negotiable Constraints

### 9.1 Data Integrity

```
CONSTRAINT D-001: No fabricated or inferred property values
CONSTRAINT D-002: No dummy data in production
CONSTRAINT D-003: No fallback to heuristic BMV when comps unavailable
CONSTRAINT D-004: Source-provided "estimated values" are never used
```

### 9.2 Calculation Integrity

```
CONSTRAINT C-001: Median ONLY for EMV — never mean
CONSTRAINT C-002: Exact property type matching — no substitution
CONSTRAINT C-003: Exact tenure matching — no substitution
CONSTRAINT C-004: UK Land Registry data ONLY for comparables
```

### 9.3 Output Integrity

```
CONSTRAINT O-001: Every output is traceable to explicit rules
CONSTRAINT O-002: Confidence caps are never bypassed
CONSTRAINT O-003: Zero-comp outputs are valid, not errors
CONSTRAINT O-004: Deterministic — same input = same output
```

---

## 10. Audit Trail Requirements

Every `ClassifiedOpportunity` must include:

```python
@dataclass
class AuditTrail:
    # Input provenance
    source_id: str
    source_name: str
    ingestion_timestamp: datetime

    # Validation outcome
    validation_passed: bool
    validation_errors: list[str]

    # Market analysis evidence
    comps_used: int
    comp_ids: list[str]  # Land Registry transaction IDs
    comp_prices: list[int]
    comp_radius_miles: float
    comp_date_range_months: int
    emv: int

    # Confidence determination
    confidence: Confidence
    confidence_reason: str
    recommendation_cap_applied: bool

    # Scoring breakdown
    bmv_score: float
    urgency_score: float
    location_score: float
    value_score: float
    overall_score: float

    # Classification
    recommendation: Recommendation
    classification_reason: str

    # Engine metadata
    engine_version: str = "1.1.0"
    processing_timestamp: datetime
```

---

## 11. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-xx-xx | Initial heuristic-based BMV engine |
| 1.1.0 | 2026-01-17 | Complete replacement with comp-based EMV |

### Key Changes in v1.1

1. Replaced heuristic BMV scoring with UK Land Registry comp-based EMV
2. Added mandatory exact property type and tenure matching
3. Implemented confidence gating with recommendation caps
4. Added INSUFFICIENT_DATA classification for zero-comp scenarios
5. Enforced median-only EMV calculation
6. Defined explicit failure modes
7. Added comprehensive audit trail requirements

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| BMV | Below Market Value — percentage discount from EMV |
| EMV | Estimated Market Value — median of comparable sales |
| Comp | Comparable sale from UK Land Registry |
| Hard Filter | Non-negotiable matching criterion |
| Confidence Gate | Mechanism to cap recommendations based on evidence quality |
| Fallback Level | Progressive expansion of search criteria |

---

## Appendix B: Related Documents

- Data Source Expansion Framework (DSXF v1.0)
- ValidatedAsset Schema Specification
- UK Land Registry Integration Guide
- Axis Allocation Investment Policy

---

**Document Control**

This specification is proprietary to Axis Allocation. Modifications require approval from the Deal Engine Architecture Board. The immutable six-stage pipeline may not be altered without formal version increment.
