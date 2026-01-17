# Agent Property Submission Portal

## Overview

Private, invite-only property submission system for authorised agents. This system provides a standardised, facts-first approach to property intake with mandatory upfront information and immutable audit trails.

**Not included:**
- Public marketplace
- Buyer browsing
- Payments
- Binding agreements
- Blockchain

## Principles

1. **Facts before marketing** — No free-text marketing descriptions
2. **Mandatory upfront information** — All required fields must be provided
3. **Immutable submissions** — Versioned, not edited
4. **Standardised schema** — Every property follows the same structure
5. **No opinions at submission** — Scoring/evaluation happens separately

---

## Step 1: Agent Submission Portal

### Access

```
URL: /submit/
Method: GET (form), POST (submit)
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `full_address` | string | Complete property address |
| `postcode` | string | UK postcode (validated) |
| `property_type` | enum | flat, maisonette, terraced, semi-detached, detached |
| `tenure` | enum | freehold, leasehold |
| `floor_area_sqm` | integer | Floor area in square metres |
| `guide_price` | integer | Guide price in GBP |
| `sale_route` | enum | auction, private_treaty, off_market |
| `agent_firm` | string | Agent's company name |
| `agent_name` | string | Agent's name |
| `agent_email` | string | Agent's email address |

### Optional Fields (Facts Only)

| Field | Type | Description |
|-------|------|-------------|
| `bedrooms` | integer | Number of bedrooms |
| `bathrooms` | integer | Number of bathrooms |
| `year_built` | integer | Year of construction |
| `council_tax_band` | string | A-H |
| `epc_rating` | string | A-G (from EPC document) |

### Leasehold-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `lease_years_remaining` | integer | Years left on lease |
| `ground_rent_annual` | integer | Annual ground rent (£) |
| `service_charge_annual` | integer | Annual service charge (£) |

### Mandatory Documents

| Document | Required For | Description |
|----------|--------------|-------------|
| Title Register | All | Official Land Registry document |
| EPC | All | Energy Performance Certificate |
| Floor Plan | All | Measured floor plan |
| Lease | Leasehold only | Current lease document |
| Planning Approval | If applicable | Planning permission documents |

**Document Constraints:**
- Accepted formats: PDF, JPG, JPEG, PNG, TIFF
- Maximum size: 10MB per file
- All documents verified with SHA-256 hash

### Submission Rules

1. **Cannot proceed** if any mandatory field is missing
2. **Cannot proceed** if any mandatory document is missing
3. **No free-text marketing** descriptions allowed
4. On successful submit:
   - Property ID generated: `PROP-{12-char-hex}`
   - Submission ID generated: `SUB-{12-char-hex}`
   - Timestamp recorded
   - Logbook created with version 1

---

## Step 2: Digital Property Logbook

### Structure

Each submission creates a `SubmissionLogbook` containing:

```
SubmissionLogbook
├── property_id (UUID)
├── created_at (datetime)
├── current_status (enum)
└── versions[] (append-only)
    └── SubmissionVersion
        ├── version_id
        ├── version_number
        ├── timestamp
        ├── action (what changed)
        ├── action_by (who changed it)
        ├── submission_snapshot (immutable copy)
        └── status_at_version
```

### Version Actions

| Action | Description |
|--------|-------------|
| `initial_submission` | First submission |
| `document_added` | New document uploaded |
| `document_replaced` | Document replaced |
| `field_updated` | Field value changed |
| `status_changed` | Status updated |
| `axis_review` | Axis analysis added |
| `resubmission` | Full resubmission |

### Status Lifecycle

```
DRAFT → INCOMPLETE → SUBMITTED → UNDER_REVIEW → EVALUATED
                                            ↓
                               APPROVED / REJECTED / ARCHIVED
```

| Status | Description |
|--------|-------------|
| `draft` | Initial state |
| `incomplete` | Missing required documents |
| `submitted` | Complete submission |
| `under_review` | Axis reviewing |
| `unevaluated` | Not yet processed by Deal Engine |
| `evaluated` | Deal Engine analysis complete |
| `approved` | Approved for next steps |
| `rejected` | Rejected |
| `archived` | Archived |
| `withdrawn` | Withdrawn by agent |

### Immutability Rules

- Logbook entries are **append-only**
- No silent edits
- Previous versions **always accessible**
- All changes create new versions
- Axis analysis references specific version

---

## API Endpoints

### Public (Agent)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/submit/` | GET | Submission form |
| `/submit/` | POST | Submit property |
| `/submit/confirmation/{property_id}` | GET | Confirmation page |
| `/submit/upload/{property_id}` | POST | Upload additional document |

### Read-Only (Deal Engine)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/submit/api/property/{property_id}` | GET | Full submission data |
| `/submit/api/property/{property_id}/history` | GET | Version history |
| `/submit/api/property/{property_id}/version/{n}` | GET | Specific version |

### Admin

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/submit/admin` | GET | List all submissions |
| `/submit/admin/{property_id}` | GET | Detail view with history |
| `/submit/admin/{property_id}/status` | POST | Update status |

---

## Admin View

### List View (`/submit/admin`)

Displays all submitted properties with:
- Property ID
- Address & postcode
- Property type & tenure
- Guide price
- Agent details
- Status badge
- Completeness indicator
- Version count
- Quick actions

### Detail View (`/submit/admin/{property_id}`)

Displays single property with:
- All property information
- Agent information
- Completeness check
- Document list
- Status management
- Full version history (timeline)
- API endpoint references

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT SUBMISSION FLOW                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Agent Form ──► Validation ──► Document Storage ──► Logbook v1         │
│       │              │               │                   │              │
│       │              │               │                   ▼              │
│       │              │               │         ┌─────────────────┐      │
│       │              │               └────────►│ SubmissionRepo  │      │
│       │              │                         │   (Persisted)   │      │
│       │              │                         └────────┬────────┘      │
│       │              │                                  │               │
│       │              ▼                                  ▼               │
│       │        ┌──────────┐                    ┌─────────────────┐      │
│       │        │ REJECTED │                    │   Admin View    │      │
│       │        │ (errors) │                    │   Deal Engine   │      │
│       │        └──────────┘                    │   (read-only)   │      │
│       │                                        └─────────────────┘      │
│       │                                                                 │
│       ▼                                                                 │
│  Confirmation ──► Upload Additional Docs ──► Logbook v2, v3...         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
core/submission/
├── __init__.py          # Module exports
├── schema.py            # AgentSubmission, DocumentRecord, enums
├── storage.py           # DocumentStorage (file handling)
├── logbook.py           # SubmissionLogbook, SubmissionVersion
├── validation.py        # Validation logic
└── repository.py        # In-memory storage with JSON persistence

web/
├── submission_routes.py # FastAPI routes
└── templates/
    ├── submission_form.html         # Agent form
    ├── submission_confirmation.html # Confirmation page
    ├── submission_admin.html        # Admin list view
    └── submission_detail.html       # Admin detail view

data/
├── documents/           # Stored documents by property_id
│   └── {property_id}/
│       └── {document_type}/
│           └── {filename}
└── submissions.json     # Persisted submission data
```

---

## Technical Notes

### Validation

- UK postcode format validated with regex
- All required fields checked before submission
- Documents validated for:
  - File extension (PDF, JPG, JPEG, PNG, TIFF)
  - File size (max 10MB)
  - Non-empty content
- Integrity verified with SHA-256 hash

### Storage

- Documents stored in `data/documents/{property_id}/`
- Submission data persisted to `data/submissions.json`
- Deep copies used for immutability
- Frozen dataclasses for version records

### No Fallbacks

- Missing required fields → **REJECT**
- Missing required documents → **INCOMPLETE**
- No dummy data ever inserted
- No inference of missing values
- Empty results are valid results

---

## Running the Application

```bash
# Start the web server
uvicorn web.app:app --reload

# Access submission portal
http://localhost:8000/submit/

# Access admin view
http://localhost:8000/submit/admin
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-17 | Initial implementation |

---

**Document Classification:** Proprietary — Axis Allocation Internal
