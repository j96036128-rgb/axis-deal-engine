"""
Admin Routes - Secure Admin Dashboard for Property Submission Approval

All routes under /admin/* require authentication.
Non-authenticated users receive 403 Forbidden.

Routes:
- GET  /admin/login          - Login page
- POST /admin/login          - Process login
- POST /admin/logout         - Logout
- GET  /admin/submissions    - List all submissions
- GET  /admin/submissions/{id} - View submission detail
- POST /admin/submissions/{id}/approve - Approve submission
- POST /admin/submissions/{id}/reject  - Reject submission
- GET  /admin/documents/{property_id}/{document_id} - Download document
- POST /admin/submissions/{id}/status - Update status
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.submission import (
    SubmissionStatus,
    get_submission_repository,
    VersionAction,
    create_verification_summary_from_submission,
)
from web.admin_auth import (
    AdminSession,
    authenticate_admin,
    get_current_admin,
    set_session_cookie,
    clear_session_cookie,
    is_admin_configured,
)


# =============================================================================
# Router Setup
# =============================================================================

# Use absolute path for templates to ensure it works in any working directory
TEMPLATES_DIR = Path(__file__).parent / "templates"

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# =============================================================================
# Authentication Dependency
# =============================================================================


def require_admin(request: Request) -> AdminSession:
    """
    Dependency that requires a valid admin session.

    Raises HTTPException(403) if not authenticated.
    """
    session = get_current_admin(request)
    if not session:
        raise HTTPException(
            status_code=403,
            detail="Admin authentication required",
        )
    return session


# =============================================================================
# Login/Logout Routes
# =============================================================================


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Render the admin login page."""
    # If already logged in, redirect to submissions
    session = get_current_admin(request)
    if session:
        return RedirectResponse(url="/admin/submissions", status_code=303)

    return templates.TemplateResponse(
        "admin_login.html",
        {
            "request": request,
            "error": error,
            "is_configured": is_admin_configured(),
        },
    )


@router.post("/login")
async def process_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Process admin login form submission."""
    session = authenticate_admin(email, password)

    if not session:
        return templates.TemplateResponse(
            "admin_login.html",
            {
                "request": request,
                "error": "Invalid email or password",
                "email": email,
                "is_configured": is_admin_configured(),
            },
            status_code=401,
        )

    # Create response with redirect
    response = RedirectResponse(url="/admin/submissions", status_code=303)

    # Set session cookie
    set_session_cookie(response, session)

    return response


@router.post("/logout")
async def logout(request: Request):
    """Log out the current admin user."""
    response = RedirectResponse(url="/admin/login", status_code=303)
    clear_session_cookie(response)
    return response


# =============================================================================
# Submissions List
# =============================================================================


@router.get("/submissions", response_class=HTMLResponse)
async def submissions_list(
    request: Request,
    admin: AdminSession = Depends(require_admin),
    status_filter: Optional[str] = None,
):
    """List all submissions for admin review."""
    repo = get_submission_repository()

    # Get all submissions
    submissions = repo.get_admin_list()

    # Filter by status if requested
    if status_filter:
        submissions = [s for s in submissions if s["status"] == status_filter]

    # Get summary stats
    summary = repo.get_summary()

    return templates.TemplateResponse(
        "admin_submissions.html",
        {
            "request": request,
            "admin": admin,
            "submissions": submissions,
            "summary": summary,
            "status_filter": status_filter,
            "statuses": [s.value for s in SubmissionStatus],
        },
    )


# =============================================================================
# Submission Detail
# =============================================================================


@router.get("/submissions/{property_id}", response_class=HTMLResponse)
async def submission_detail(
    request: Request,
    property_id: str,
    admin: AdminSession = Depends(require_admin),
):
    """View detailed submission information."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission = logbook.current_submission
    if not submission:
        raise HTTPException(status_code=404, detail="No submission data")

    completeness = logbook.get_completeness_check()
    history = logbook.get_history()

    # Get integrity information
    chain_integrity = logbook.verify_chain_integrity()
    current_version = logbook.current_version
    integrity = {
        "chain_valid": chain_integrity["valid"],
        "verification_error": chain_integrity.get("error"),
        "current_version_hash": current_version.version_hash if current_version else None,
    }

    # Create verification summary
    verification_summary = None
    snapshot = logbook.current_snapshot
    if snapshot:
        verification_obj = create_verification_summary_from_submission(
            property_id=property_id,
            submission_data=snapshot,
            agent_email=submission.agent_email,
        )
        verification_summary = verification_obj.to_summary_dict()

    # Get document download paths
    documents_with_urls = []
    for doc in submission.documents:
        doc_dict = doc.to_dict()
        # Generate download URL
        doc_dict["download_url"] = f"/admin/documents/{property_id}/{doc.document_id}"
        documents_with_urls.append(doc_dict)

    return templates.TemplateResponse(
        "admin_submission_detail.html",
        {
            "request": request,
            "admin": admin,
            "submission": submission.to_dict(),
            "submission_obj": submission,
            "logbook": logbook.to_dict(),
            "completeness": completeness,
            "history": history,
            "statuses": [s.value for s in SubmissionStatus],
            "integrity": integrity,
            "verification_summary": verification_summary,
            "documents": documents_with_urls,
        },
    )


# =============================================================================
# Approve/Reject Actions
# =============================================================================


@router.post("/submissions/{property_id}/approve")
async def approve_submission(
    request: Request,
    property_id: str,
    note: str = Form(""),
    admin: AdminSession = Depends(require_admin),
):
    """
    Approve a property submission.

    Creates an immutable entry in the Property Logbook.
    """
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Update status to approved
    action_note = f"Approved by {admin.email}"
    if note:
        action_note += f": {note}"

    repo.update_status(
        property_id=property_id,
        new_status=SubmissionStatus.APPROVED,
        action_by=admin.email,
        action_note=action_note,
    )

    return RedirectResponse(
        url=f"/admin/submissions/{property_id}?action=approved",
        status_code=303,
    )


@router.post("/submissions/{property_id}/reject")
async def reject_submission(
    request: Request,
    property_id: str,
    note: str = Form(...),  # Note is required for rejection
    admin: AdminSession = Depends(require_admin),
):
    """
    Reject a property submission.

    Creates an immutable entry in the Property Logbook.
    Note is required for rejection to explain the reason.
    """
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    if not note or not note.strip():
        raise HTTPException(
            status_code=400,
            detail="A rejection reason is required",
        )

    # Update status to rejected
    action_note = f"Rejected by {admin.email}: {note}"

    repo.update_status(
        property_id=property_id,
        new_status=SubmissionStatus.REJECTED,
        action_by=admin.email,
        action_note=action_note,
    )

    return RedirectResponse(
        url=f"/admin/submissions/{property_id}?action=rejected",
        status_code=303,
    )


# =============================================================================
# Document Download
# =============================================================================


@router.get("/documents/{property_id}/{document_id}")
async def download_document(
    property_id: str,
    document_id: str,
    admin: AdminSession = Depends(require_admin),
):
    """Download a document from a submission."""
    from fastapi.responses import FileResponse

    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission = logbook.current_submission
    if not submission:
        raise HTTPException(status_code=404, detail="No submission data")

    # Find the document
    doc = None
    for d in submission.documents:
        if d.document_id == document_id:
            doc = d
            break

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if file exists
    file_path = Path(doc.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/octet-stream",
    )


# =============================================================================
# Status Update (General)
# =============================================================================


@router.post("/submissions/{property_id}/status")
async def update_status(
    request: Request,
    property_id: str,
    new_status: str = Form(...),
    note: str = Form(""),
    admin: AdminSession = Depends(require_admin),
):
    """Update submission status (general status change)."""
    repo = get_submission_repository()
    logbook = repo.get(property_id)

    if not logbook:
        raise HTTPException(status_code=404, detail="Submission not found")

    try:
        status = SubmissionStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    action_note = f"Status changed by {admin.email}"
    if note:
        action_note += f": {note}"

    repo.update_status(
        property_id=property_id,
        new_status=status,
        action_by=admin.email,
        action_note=action_note,
    )

    return RedirectResponse(
        url=f"/admin/submissions/{property_id}",
        status_code=303,
    )
