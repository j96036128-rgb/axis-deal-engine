"""
Agent Submission Routes - Web API for Property Submissions

Private, invite-only submission portal for agents.
No public marketplace, no buyer browsing.

Access Control:
- All submission routes require a valid invite token
- Invite tokens are issued by Axis to approved agents
- Agent firm and email are locked to token (cannot be edited)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.comp_engine.models import PropertyType, Tenure
from core.submission import (
    AgentSubmission,
    SaleRoute,
    DocumentType,
    SubmissionStatus,
    DocumentStorage,
    get_document_storage,
    SubmissionLogbook,
    SubmissionRepository,
    get_submission_repository,
    create_submission,
    VersionAction,
    create_verification_summary_from_submission,
    # Invite token system
    InviteToken,
    InviteStatus,
    InviteValidationSuccess,
    InviteValidationFailure,
    validate_invite_token,
    get_invite_repository,
)
from core.submission.validation import validate_submission_data


# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/submit", tags=["submission"])
templates = Jinja2Templates(directory="web/templates")


# =============================================================================
# Invite Token Validation Helper
# =============================================================================


def require_valid_invite(
    invite: Optional[str],
    request: Request,
) -> InviteValidationSuccess:
    """
    Validate invite token from query params.

    Args:
        invite: Token value from query params
        request: FastAPI request object

    Returns:
        InviteValidationSuccess with token and agent data

    Raises:
        HTTPException(403) if token is invalid
    """
    repo = get_invite_repository()
    result = validate_invite_token(invite, repo)

    if isinstance(result, InviteValidationFailure):
        raise HTTPException(
            status_code=403,
            detail=result.reason,
        )

    return result


# =============================================================================
# Submission Form
# =============================================================================


@router.get("/", response_class=HTMLResponse)
async def submission_form(
    request: Request,
    invite: Optional[str] = Query(None, description="Invite token"),
):
    """
    Render the agent submission form.

    Requires a valid invite token. Agent firm and email are locked to the token.
    """
    # Validate invite token
    validation = require_valid_invite(invite, request)

    return templates.TemplateResponse(
        "submission_form.html",
        {
            "request": request,
            "property_types": [pt.value for pt in PropertyType],
            "tenures": [t.value for t in Tenure],
            "sale_routes": [sr.value for sr in SaleRoute],
            "document_types": [
                {"value": dt.value, "label": dt.value.replace("_", " ").title()}
                for dt in DocumentType
            ],
            # Pre-fill and lock agent fields from invite token
            "agent_firm": validation.agent_firm,
            "agent_email": validation.agent_email,
            "invite_token": invite,  # Pass through for form submission
        },
    )


@router.post("/", response_class=HTMLResponse)
async def submit_property(
    request: Request,
    # Invite token (required)
    invite: str = Form(...),
    # Required property fields
    full_address: str = Form(...),
    postcode: str = Form(...),
    property_type: str = Form(...),
    tenure: str = Form(...),
    floor_area_sqm: int = Form(...),
    guide_price: int = Form(...),
    sale_route: str = Form(...),
    # Agent name (only field agent can edit - firm/email locked to token)
    agent_name: str = Form(...),
    # Optional fields
    bedrooms: Optional[int] = Form(None),
    bathrooms: Optional[int] = Form(None),
    year_built: Optional[int] = Form(None),
    council_tax_band: Optional[str] = Form(None),
    epc_rating: Optional[str] = Form(None),
    # Leasehold fields
    lease_years_remaining: Optional[int] = Form(None),
    ground_rent_annual: Optional[int] = Form(None),
    service_charge_annual: Optional[int] = Form(None),
    # Documents
    title_register: UploadFile = File(None),
    epc_document: UploadFile = File(None),
    floor_plan: UploadFile = File(None),
    lease_document: UploadFile = File(None),
    planning_approval: UploadFile = File(None),
):
    """
    Process property submission.

    Requires valid invite token. Agent firm and email are locked to the token.
    Creates submission, stores documents, and creates logbook.
    """
    # Validate invite token
    invite_validation = require_valid_invite(invite, request)

    # Use agent_firm and agent_email from token (LOCKED - cannot be overridden)
    agent_firm = invite_validation.agent_firm
    agent_email = invite_validation.agent_email

    # Build submission data
    data = {
        "full_address": full_address,
        "postcode": postcode,
        "property_type": property_type,
        "tenure": tenure,
        "floor_area_sqm": floor_area_sqm,
        "guide_price": guide_price,
        "sale_route": sale_route,
        "agent_firm": agent_firm,  # From token (locked)
        "agent_name": agent_name,
        "agent_email": agent_email,  # From token (locked)
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "year_built": year_built,
        "council_tax_band": council_tax_band,
        "epc_rating": epc_rating,
        "lease_years_remaining": lease_years_remaining,
        "ground_rent_annual": ground_rent_annual,
        "service_charge_annual": service_charge_annual,
        "documents": [],
    }

    # Validate submission
    validation = validate_submission_data(data)

    if validation.is_blocked:
        return templates.TemplateResponse(
            "submission_form.html",
            {
                "request": request,
                "error": "Validation failed",
                "errors": validation.errors,
                "missing_fields": validation.missing_fields,
                "property_types": [pt.value for pt in PropertyType],
                "tenures": [t.value for t in Tenure],
                "sale_routes": [sr.value for sr in SaleRoute],
                "document_types": [
                    {"value": dt.value, "label": dt.value.replace("_", " ").title()}
                    for dt in DocumentType
                ],
                "form_data": data,
                # Keep invite token and locked fields
                "agent_firm": agent_firm,
                "agent_email": agent_email,
                "invite_token": invite,
            },
            status_code=400,
        )

    # Create submission
    submission, _ = create_submission(data)
    if not submission:
        raise HTTPException(status_code=400, detail="Failed to create submission")

    # Store documents
    storage = get_document_storage()
    document_uploads = [
        (title_register, DocumentType.TITLE_REGISTER),
        (epc_document, DocumentType.EPC),
        (floor_plan, DocumentType.FLOOR_PLAN),
        (lease_document, DocumentType.LEASE),
        (planning_approval, DocumentType.PLANNING_APPROVAL),
    ]

    for upload, doc_type in document_uploads:
        if upload and upload.filename:
            try:
                content = await upload.read()
                if content:
                    doc_record = storage.store_document(
                        property_id=submission.property_id,
                        document_type=doc_type,
                        filename=upload.filename,
                        content=content,
                    )
                    submission.add_document(doc_record)
            except ValueError as e:
                # Log error but continue with other documents
                print(f"Document upload error for {doc_type}: {e}")

    # Create logbook
    repo = get_submission_repository()
    logbook = repo.create(submission)

    # Increment invite token usage
    invite_repo = get_invite_repository()
    invite_repo.increment_use(invite_validation.token.token_id)

    # Redirect to confirmation page
    return RedirectResponse(
        url=f"/submit/confirmation/{submission.property_id}",
        status_code=303,
    )


@router.get("/confirmation/{property_id}", response_class=HTMLResponse)
async def submission_confirmation(request: Request, property_id: str):
    """Show submission confirmation page."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission = logbook.current_submission
    completeness = logbook.get_completeness_check()

    return templates.TemplateResponse(
        "submission_confirmation.html",
        {
            "request": request,
            "submission": submission.to_dict() if submission else None,
            "logbook": logbook.to_dict(),
            "completeness": completeness,
        },
    )


# =============================================================================
# Document Upload (Additional)
# =============================================================================


@router.post("/upload/{property_id}")
async def upload_document(
    property_id: str,
    document_type: str = Form(...),
    document: UploadFile = File(...),
):
    """Upload additional document to existing submission."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission = logbook.current_submission
    if not submission:
        raise HTTPException(status_code=400, detail="No submission data")

    # Parse document type
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid document type: {document_type}")

    # Store document
    storage = get_document_storage()
    try:
        content = await document.read()
        doc_record = storage.store_document(
            property_id=property_id,
            document_type=doc_type,
            filename=document.filename,
            content=content,
        )
        submission.add_document(doc_record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Update logbook
    repo.update(
        property_id=property_id,
        submission=submission,
        action=VersionAction.DOCUMENT_ADDED,
        action_by=submission.agent_email,
        action_note=f"Added {doc_type.value}",
    )

    return JSONResponse({
        "success": True,
        "document_id": doc_record.document_id,
        "is_complete": submission.is_complete,
    })


# =============================================================================
# Read-Only API for Deal Engine
# =============================================================================


@router.get("/api/property/{property_id}")
async def get_property(property_id: str):
    """Get property submission data (read-only API for Deal Engine)."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Property not found")

    return JSONResponse(logbook.export_for_deal_engine())


@router.get("/api/property/{property_id}/history")
async def get_property_history(property_id: str):
    """Get property version history."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Property not found")

    return JSONResponse({
        "property_id": property_id,
        "version_count": logbook.version_count,
        "history": logbook.get_history(),
    })


@router.get("/api/property/{property_id}/version/{version_number}")
async def get_property_version(property_id: str, version_number: int):
    """Get specific version of property submission."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Property not found")

    version = logbook.get_version(version_number)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")

    return JSONResponse(version.to_dict())


# =============================================================================
# Admin Routes
# =============================================================================


@router.get("/admin", response_class=HTMLResponse)
async def admin_list(request: Request):
    """Admin view listing all submitted properties."""
    repo = get_submission_repository()
    submissions = repo.get_admin_list()
    summary = repo.get_summary()

    return templates.TemplateResponse(
        "submission_admin.html",
        {
            "request": request,
            "submissions": submissions,
            "summary": summary,
            "statuses": [s.value for s in SubmissionStatus],
        },
    )


@router.get("/admin/{property_id}", response_class=HTMLResponse)
async def admin_detail(request: Request, property_id: str):
    """Admin view for single property with version history and trust indicators."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Property not found")

    submission = logbook.current_submission
    completeness = logbook.get_completeness_check()
    history = logbook.get_history()

    # Get integrity information from the logbook
    chain_integrity = logbook.verify_chain_integrity()
    current_version = logbook.current_version
    integrity = {
        "chain_valid": chain_integrity["valid"],
        "verification_error": chain_integrity.get("error"),
        "current_version_hash": current_version.version_hash if current_version else None,
    }

    # Create verification summary from submission data
    # Note: In a full implementation, this would be stored and tracked separately
    verification_summary = None
    if submission:
        snapshot = logbook.current_snapshot
        if snapshot:
            verification_obj = create_verification_summary_from_submission(
                property_id=property_id,
                submission_data=snapshot,
                agent_email=submission.agent_email,
            )
            verification_summary = verification_obj.to_summary_dict()

    return templates.TemplateResponse(
        "submission_detail.html",
        {
            "request": request,
            "submission": submission.to_dict() if submission else None,
            "logbook": logbook.to_dict(),
            "completeness": completeness,
            "history": history,
            "statuses": [s.value for s in SubmissionStatus],
            "integrity": integrity,
            "verification_summary": verification_summary,
        },
    )


@router.post("/admin/{property_id}/status")
async def update_property_status(
    property_id: str,
    new_status: str = Form(...),
    note: str = Form(""),
):
    """Update property status (admin action)."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        status = SubmissionStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    repo.update_status(
        property_id=property_id,
        new_status=status,
        action_by="axis_admin",
        action_note=note or f"Status updated to {status.value}",
    )

    return RedirectResponse(
        url=f"/submit/admin/{property_id}",
        status_code=303,
    )


# =============================================================================
# Invite Token Admin Routes
# =============================================================================


@router.get("/admin/invites", response_class=HTMLResponse)
async def admin_invite_list(request: Request):
    """Admin view listing all invite tokens."""
    repo = get_invite_repository()
    tokens = repo.get_admin_list()

    return templates.TemplateResponse(
        "invite_admin.html",
        {
            "request": request,
            "tokens": tokens,
            "total_count": repo.count(),
            "active_count": len(repo.list_active()),
        },
    )


@router.get("/api/admin/invites")
async def api_list_invites():
    """API endpoint to list all invite tokens (admin only)."""
    repo = get_invite_repository()
    return JSONResponse({
        "tokens": repo.get_admin_list(),
        "total_count": repo.count(),
        "active_count": len(repo.list_active()),
    })


@router.post("/api/admin/invites")
async def api_create_invite(
    agent_firm: str = Form(...),
    agent_email: str = Form(...),
    max_uses: Optional[int] = Form(None),
    expires_days: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    Create a new invite token (admin only).

    Returns the full token including the token_value for sharing.
    """
    from datetime import timedelta

    repo = get_invite_repository()

    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

    token = repo.create_token(
        agent_firm=agent_firm,
        agent_email=agent_email,
        expires_at=expires_at,
        max_uses=max_uses,
        notes=notes,
    )

    return JSONResponse({
        "success": True,
        "token": token.to_dict(),
        "invite_url": f"/submit/?invite={token.token_value}",
    })


@router.post("/api/admin/invites/{token_id}/revoke")
async def api_revoke_invite(
    token_id: str,
    note: Optional[str] = Form(None),
):
    """Revoke an invite token (admin only)."""
    repo = get_invite_repository()

    if not repo.revoke(token_id, note):
        raise HTTPException(status_code=404, detail="Token not found")

    return JSONResponse({
        "success": True,
        "token_id": token_id,
        "status": "revoked",
    })


@router.get("/api/admin/invites/{token_id}")
async def api_get_invite(token_id: str):
    """Get invite token details (admin only)."""
    repo = get_invite_repository()
    token = repo.get_by_id(token_id)

    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    return JSONResponse(token.to_dict())
