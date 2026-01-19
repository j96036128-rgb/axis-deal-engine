"""
FastAPI application for the deal engine web interface.
Phase 7: Planning Context Input + UI Surfacing

Production deployment configuration via environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import re
import sys

from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core import SearchCriteria, BMVScorer, DealAnalyzer, Confidence, Recommendation

# =============================================================================
# Environment Configuration
# =============================================================================

# Production mode detection
IS_PRODUCTION = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("PRODUCTION", "").lower() == "true"

# CORS configuration - locked down for production
# In production, only allow the Railway-assigned domain
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
if not ALLOWED_ORIGINS and not IS_PRODUCTION:
    # Development fallback only
    ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

# Debug mode - NEVER enabled in production
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true" and not IS_PRODUCTION

# Import submission routes
from web.submission_routes import router as submission_router
from scraper import AuctionHouseLondonScraper

# Add reporting module to path
REPORTING_DIR = Path(__file__).parent.parent / "reporting"
if str(REPORTING_DIR.parent) not in sys.path:
    sys.path.insert(0, str(REPORTING_DIR.parent))


@dataclass
class PlanningPrecedent:
    """A nearby planning precedent."""
    reference: str
    precedent_type: str
    approved: bool
    distance_meters: Optional[float] = None


@dataclass
class PlanningContext:
    """Planning context for development potential assessment."""
    property_type: str = ""
    tenure: str = ""
    current_sqft: Optional[int] = None
    plot_size_sqft: Optional[int] = None
    listed_building: bool = False
    listed_grade: str = ""
    conservation_area: bool = False
    article_4: bool = False
    green_belt: bool = False
    tpo: bool = False
    flood_zone: int = 1
    proposed_type: str = ""
    precedents: list = field(default_factory=list)

    def has_data(self) -> bool:
        """Check if any planning data was provided."""
        return bool(self.property_type or self.proposed_type)


@dataclass
class PlanningAssessment:
    """Result of planning potential assessment."""
    score: int  # 0-100
    label: str  # exceptional, strong, medium, low
    uplift_percent_low: float
    uplift_percent_high: float
    positive_factors: list
    negative_factors: list
    rationale: str

    @property
    def has_upside(self) -> bool:
        return self.score >= 60


def assess_planning(context: PlanningContext) -> Optional[PlanningAssessment]:
    """Assess planning potential based on context."""
    if not context.has_data():
        return None

    score = 50  # Base score
    positive = []
    negative = []

    # Property type scoring
    if context.property_type in ("house_detached", "house_semi"):
        score += 15
        positive.append("Suitable property type for extensions")
    elif context.property_type == "flat":
        score -= 10
        negative.append("Flats have limited extension potential")

    # Tenure
    if context.tenure == "freehold":
        score += 10
        positive.append("Freehold ownership allows full control")
    elif context.tenure == "leasehold":
        score -= 5
        negative.append("Leasehold may require freeholder consent")

    # Plot size potential
    if context.plot_size_sqft and context.current_sqft:
        ratio = context.plot_size_sqft / context.current_sqft
        if ratio > 3:
            score += 15
            positive.append("Large plot relative to building - extension potential")
        elif ratio > 2:
            score += 8
            positive.append("Adequate plot size for development")

    # Constraints
    if context.listed_building:
        score -= 25
        negative.append(f"Listed building ({context.listed_grade or 'grade unknown'}) - strict controls")
    if context.conservation_area:
        score -= 15
        negative.append("Conservation area - design restrictions apply")
    if context.green_belt:
        score -= 30
        negative.append("Green belt - very limited development permitted")
    if context.article_4:
        score -= 10
        negative.append("Article 4 direction - PD rights removed")
    if context.tpo:
        score -= 5
        negative.append("TPO may affect site layout")
    if context.flood_zone >= 3:
        score -= 15
        negative.append("High flood risk - sequential test required")
    elif context.flood_zone == 2:
        score -= 5
        negative.append("Medium flood risk")

    # Proposed development type scoring
    dev_scores = {
        "extension_loft": 10,
        "extension_rear": 8,
        "extension_side": 8,
        "permitted_development": 15,
        "conversion_hmo": 5,
        "conversion_flats": 12,
        "change_of_use": 0,
    }
    if context.proposed_type in dev_scores:
        score += dev_scores[context.proposed_type]
        if context.proposed_type == "permitted_development":
            positive.append("PD rights may allow without planning application")

    # Precedent analysis
    if context.precedents:
        approved = sum(1 for p in context.precedents if p.approved)
        total = len(context.precedents)
        approval_rate = approved / total if total > 0 else 0

        if approval_rate >= 0.8:
            score += 15
            positive.append(f"Strong local precedent ({approved}/{total} approved)")
        elif approval_rate >= 0.5:
            score += 5
            positive.append(f"Mixed local precedent ({approved}/{total} approved)")
        else:
            score -= 10
            negative.append(f"Poor local precedent ({approved}/{total} approved)")

    # Clamp score
    score = max(0, min(100, score))

    # Determine label
    if score >= 80:
        label = "exceptional"
    elif score >= 60:
        label = "strong"
    elif score >= 40:
        label = "medium"
    else:
        label = "low"

    # Estimate uplift based on proposed type
    uplift_ranges = {
        "extension_loft": (8, 15),
        "extension_rear": (5, 12),
        "extension_side": (5, 10),
        "extension_basement": (10, 20),
        "conversion_flats": (15, 30),
        "conversion_hmo": (10, 25),
        "change_of_use": (5, 15),
        "permitted_development": (5, 12),
    }
    base_low, base_high = uplift_ranges.get(context.proposed_type, (3, 8))

    # Adjust for constraints
    constraint_factor = 1.0
    if context.listed_building:
        constraint_factor *= 0.5
    if context.green_belt:
        constraint_factor *= 0.3
    if context.conservation_area:
        constraint_factor *= 0.7

    uplift_low = base_low * constraint_factor
    uplift_high = base_high * constraint_factor

    rationale = f"Based on {context.property_type or 'property'}"
    if context.proposed_type:
        rationale += f" with {context.proposed_type.replace('_', ' ')} potential"
    if negative:
        rationale += f". Key constraint: {negative[0].lower()}"

    return PlanningAssessment(
        score=score,
        label=label,
        uplift_percent_low=round(uplift_low, 1),
        uplift_percent_high=round(uplift_high, 1),
        positive_factors=positive,
        negative_factors=negative,
        rationale=rationale,
    )


def parse_planning_context(form_data: dict) -> PlanningContext:
    """Parse planning context from form data."""
    # Parse precedents from dynamic form fields
    precedents = []
    i = 0
    while f"precedent_ref_{i}" in form_data or f"precedent_type_{i}" in form_data:
        ref = form_data.get(f"precedent_ref_{i}", "")
        ptype = form_data.get(f"precedent_type_{i}", "other")
        approved = form_data.get(f"precedent_approved_{i}", "true") == "true"
        distance_str = form_data.get(f"precedent_distance_{i}", "")
        distance = float(distance_str) if distance_str else None

        if ref or ptype:
            precedents.append(PlanningPrecedent(
                reference=ref or f"PREC-{i+1}",
                precedent_type=ptype,
                approved=approved,
                distance_meters=distance,
            ))
        i += 1

    return PlanningContext(
        property_type=form_data.get("property_type", ""),
        tenure=form_data.get("planning_tenure", ""),
        current_sqft=int(form_data["current_sqft"]) if form_data.get("current_sqft") else None,
        plot_size_sqft=int(form_data["plot_size_sqft"]) if form_data.get("plot_size_sqft") else None,
        listed_building=form_data.get("listed_building") == "true",
        listed_grade=form_data.get("listed_grade", ""),
        conservation_area=form_data.get("conservation_area") == "true",
        article_4=form_data.get("article_4") == "true",
        green_belt=form_data.get("green_belt") == "true",
        tpo=form_data.get("tpo") == "true",
        flood_zone=int(form_data.get("flood_zone", 1)),
        proposed_type=form_data.get("proposed_type", ""),
        precedents=precedents,
    )

# Paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
REPORTS_DIR = BASE_DIR.parent / "reports"

# UK Postcode validation pattern
UK_POSTCODE_PATTERN = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$",
    re.IGNORECASE
)

# Data source URL validation
VALID_SOURCE_DOMAINS = ["auctionhouselondon.co.uk"]


def validate_listing(listing) -> bool:
    """
    Validate that a listing contains real, verifiable data.

    Returns True if listing passes all validation checks.
    Returns False if listing appears to be dummy/placeholder data.
    """
    # Check for non-empty address
    if not listing.address or len(listing.address.strip()) < 5:
        return False

    # Check for valid UK postcode
    postcode = getattr(listing, 'postcode', '')
    if not postcode or not UK_POSTCODE_PATTERN.match(postcode.strip()):
        return False

    # Check for valid source URL
    url = getattr(listing, 'url', '')
    if not url:
        return False

    # Must point to a valid source domain
    is_valid_source = any(domain in url for domain in VALID_SOURCE_DOMAINS)
    if not is_valid_source:
        return False

    # Check source field
    source = getattr(listing, 'source', '')
    if source.lower() in ('mock', 'sample', 'test', 'dummy'):
        return False

    return True


def filter_validated_listings(listings: list) -> list:
    """
    Filter listings to only include validated real data.

    No silent fallbacks - returns empty list if no valid listings.
    """
    return [l for l in listings if validate_listing(l)]


# =============================================================================
# API Request/Response Models
# =============================================================================

class OpportunityInput(BaseModel):
    """Opportunity data for PDF generation."""
    opportunity_id: str
    address: str
    area: str
    city: str
    postcode: str
    property_type: str
    asking_price: int
    estimated_value: int
    bmv_percent: float
    potential_profit: int
    roi_percent: float
    bedrooms: int
    bathrooms: int
    days_on_market: int
    overall_score: float
    recommendation: str  # strong, moderate, weak, avoid, overpriced
    conviction: str  # high, medium, low
    key_risks: List[str] = []
    key_strengths: List[str] = []
    # Comp Engine evidence (v1.0)
    comps_used: int = 0
    comp_radius_miles: float = 0.0
    comp_date_range_months: int = 0
    valuation_statement: str = ""
    # Planning context
    planning_score: Optional[int] = None
    planning_label: Optional[str] = None
    planning_uplift_low: Optional[float] = None
    planning_uplift_high: Optional[float] = None
    planning_positive_factors: List[str] = []
    planning_negative_factors: List[str] = []


class GenerateReportRequest(BaseModel):
    """Request body for PDF generation."""
    reference_id: str
    client_name: str
    location: str
    capital_range_low: int
    capital_range_high: int
    target_bmv_percent: float = 15.0
    opportunities: List[OpportunityInput]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Axis Deal Engine",
        description="Internal deal sourcing engine for property opportunities",
        version="0.1.0",
        # Production settings: disable docs/redoc for private deployment
        docs_url=None if IS_PRODUCTION else "/docs",
        redoc_url=None if IS_PRODUCTION else "/redoc",
        openapi_url=None if IS_PRODUCTION else "/openapi.json",
        debug=DEBUG_MODE,
    )

    # ==========================================================================
    # CRITICAL: Healthcheck endpoints must be registered FIRST, before any
    # middleware or static mounts that could fail. Railway healthcheck probes "/".
    # These endpoints are synchronous, perform NO IO, and return immediately.
    # ==========================================================================
    @app.get("/", include_in_schema=False)
    def root():
        """Root healthcheck for Railway. No dependencies, no IO."""
        return {"status": "ok"}

    @app.get("/health", include_in_schema=False)
    def health():
        """Secondary health endpoint. No dependencies, no IO."""
        return {"status": "healthy"}

    # CORS middleware - locked down for production
    if ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    # ==========================================================================
    # Startup event: Deferred initialization (filesystem, heavy imports)
    # This runs AFTER healthcheck is available, so Railway won't timeout.
    # ==========================================================================
    @app.on_event("startup")
    def on_startup():
        """Deferred startup tasks. Runs after healthcheck is ready."""
        # Create reports directory (safe with exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        print("Axis Deal Engine started successfully")

    # Mount static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Mount reports directory for PDF serving (directory created in startup event)
    # Note: StaticFiles handles missing directory gracefully
    app.mount("/reports", StaticFiles(directory=REPORTS_DIR, check_dir=False), name="reports")

    # Include submission routes
    app.include_router(submission_router)

    # Templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Initialize components — REAL DATA ONLY
    # No mock/dummy data allowed
    scraper = AuctionHouseLondonScraper()

    # Use new DealAnalyzer with Comp Engine integration
    # (Legacy BMVScorer is still available but deprecated)
    deal_analyzer = DealAnalyzer()
    scorer = BMVScorer()  # Keep for backward compatibility

    @app.get("/app", response_class=HTMLResponse)
    async def index(request: Request):
        """Render the main search form."""
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "Axis Deal Engine",
            },
        )

    @app.post("/search", response_class=HTMLResponse)
    async def search(request: Request):
        """Process search and return results with optional planning assessment."""
        # Get all form data
        form_data = await request.form()
        form_dict = {k: v for k, v in form_data.items()}

        # Extract search criteria
        location = form_dict.get("location", "")
        min_beds = int(form_dict.get("min_beds", 1))
        max_beds_str = form_dict.get("max_beds", "")
        max_beds = int(max_beds_str) if max_beds_str else None
        min_baths = int(form_dict.get("min_baths", 1))
        max_price_str = form_dict.get("max_price", "")
        max_price = int(max_price_str) if max_price_str else None
        target_bmv = float(form_dict.get("target_bmv", 15.0))

        # Build search criteria
        criteria = SearchCriteria(
            location=location,
            min_beds=min_beds,
            max_beds=max_beds if max_beds and max_beds > 0 else None,
            min_baths=min_baths,
            max_price=max_price if max_price and max_price > 0 else None,
            target_bmv_percent=target_bmv,
        )

        # Parse planning context from form
        planning_context = parse_planning_context(form_dict)
        planning_assessment = assess_planning(planning_context) if planning_context.has_data() else None

        # Fetch REAL listings from Auction House London
        # No dummy data fallback - empty results are valid
        try:
            listings = await scraper.search(criteria)
        except Exception as e:
            # Network/scraping error - show clear message
            return templates.TemplateResponse(
                "results.html",
                {
                    "request": request,
                    "title": "Search Results",
                    "criteria": criteria,
                    "analyses": [],
                    "total_count": 0,
                    "planning_context": None,
                    "planning_assessment": None,
                    "has_eligible_opportunities": False,
                    "error_message": "Unable to fetch live auction listings. Please try again later.",
                },
            )

        # Validate all listings - reject any that don't meet data integrity requirements
        listings = filter_validated_listings(listings)

        # Filter by max price if specified
        if criteria.max_price:
            listings = [l for l in listings if l.asking_price <= criteria.max_price]

        # Handle zero listings gracefully - NO silent fallback to dummy data
        if not listings:
            return templates.TemplateResponse(
                "results.html",
                {
                    "request": request,
                    "title": "Search Results",
                    "criteria": criteria,
                    "analyses": [],
                    "total_count": 0,
                    "planning_context": planning_context if planning_context.has_data() else None,
                    "planning_assessment": planning_assessment,
                    "has_eligible_opportunities": False,
                    "no_listings_message": "No live auction listings match this criteria.",
                },
            )

        # Analyze listings using Comp Engine-backed DealAnalyzer
        # This replaces the heuristic BMVScorer with factual Land Registry data
        analyses = deal_analyzer.analyze_batch(listings, criteria)

        # Add planning assessment to each analysis for combined opportunity check
        for analysis in analyses:
            analysis.planning = planning_assessment
            # Check for combined opportunity (BMV + planning upside)
            if planning_assessment and planning_assessment.has_upside:
                rec = getattr(analysis, 'recommendation', '')
                if rec in ('Strong', 'Moderate'):
                    analysis.combined_opportunity = True
                else:
                    analysis.combined_opportunity = False
            else:
                analysis.combined_opportunity = False

        # Compute eligibility flag for PDF generation button
        # Phase B: Enforce confidence & recommendation gating
        # Only Strong/Moderate recommendations with High/Medium confidence are eligible
        def is_eligible(analysis) -> bool:
            rec = getattr(analysis, 'recommendation', '').lower()
            conf = getattr(analysis, 'confidence', '').lower()
            # Strong/Moderate recommendations only
            if rec not in {'strong', 'moderate'}:
                return False
            # For PDF generation, require at least Medium confidence
            # Low confidence deals should not be presented to clients
            if conf == 'low':
                return False
            return True

        has_eligible_opportunities = any(is_eligible(a) for a in analyses)

        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "title": "Search Results",
                "criteria": criteria,
                "analyses": analyses,
                "total_count": len(analyses),
                "planning_context": planning_context if planning_context.has_data() else None,
                "planning_assessment": planning_assessment,
                "has_eligible_opportunities": has_eligible_opportunities,
            },
        )

    @app.post("/api/generate-report")
    async def generate_report_endpoint(request_data: GenerateReportRequest):
        """
        Generate a Capital Opportunity Memorandum PDF.

        Accepts evaluated search results and generates a branded PDF.
        Respects eligibility gating (Strong/Moderate only, max 3).

        Returns:
            - success: true with pdf_url and filename if generated
            - success: false with message if no qualifying opportunities
        """
        from datetime import datetime
        from reporting.pdf_generator import (
            generate_report,
            ReportSuccess,
            ReportNoQualifyingOpportunities,
        )
        from reporting.schemas import (
            Mandate,
            MandateParameters,
            OpportunityMemo,
            ScoreBreakdown,
            PlanningContext,
            ConvictionRating,
            CompEvidence,
        )

        # Map conviction strings to enum
        conviction_map = {
            "high": ConvictionRating.HIGH,
            "medium": ConvictionRating.MEDIUM,
            "low": ConvictionRating.LOW,
        }

        # Convert input opportunities to schema format
        opportunities = []
        for opp in request_data.opportunities:
            # Build planning context if provided
            planning = None
            if opp.planning_score is not None:
                planning = PlanningContext(
                    score=opp.planning_score,
                    label=opp.planning_label or "medium",
                    uplift_percent_low=opp.planning_uplift_low or 0,
                    uplift_percent_high=opp.planning_uplift_high or 0,
                    positive_factors=opp.planning_positive_factors,
                    negative_factors=opp.planning_negative_factors,
                )

            # Build comp evidence if available
            comp_evidence = None
            if opp.comps_used > 0:
                comp_evidence = CompEvidence(
                    comps_used=opp.comps_used,
                    comp_radius_miles=opp.comp_radius_miles,
                    comp_date_range_months=opp.comp_date_range_months,
                    valuation_statement=opp.valuation_statement,
                )

            opportunities.append(OpportunityMemo(
                opportunity_id=opp.opportunity_id,
                address=opp.address,
                area=opp.area,
                city=opp.city,
                postcode=opp.postcode,
                property_type=opp.property_type,
                asking_price=opp.asking_price,
                estimated_value=opp.estimated_value,
                bmv_percent=opp.bmv_percent,
                potential_profit=opp.potential_profit,
                roi_percent=opp.roi_percent,
                bedrooms=opp.bedrooms,
                bathrooms=opp.bathrooms,
                days_on_market=opp.days_on_market,
                scores=ScoreBreakdown(
                    bmv_score=opp.overall_score * 0.4,
                    urgency_score=opp.overall_score * 0.2,
                    location_score=50.0,
                    value_score=opp.overall_score * 0.4,
                    overall_score=opp.overall_score,
                ),
                recommendation=opp.recommendation.lower(),
                conviction=conviction_map.get(opp.conviction.lower(), ConvictionRating.MEDIUM),
                key_risks=opp.key_risks,
                key_strengths=opp.key_strengths,
                comp_evidence=comp_evidence,
                planning=planning,
            ))

        # Build mandate
        mandate = Mandate(
            reference_id=request_data.reference_id,
            client_name=request_data.client_name,
            report_date=datetime.now().strftime("%Y-%m-%d"),
            generated_at=datetime.now().isoformat(),
            parameters=MandateParameters(
                location=request_data.location,
                min_beds=1,
                max_beds=None,
                min_baths=1,
                max_price=request_data.capital_range_high,
                target_bmv_percent=request_data.target_bmv_percent,
            ),
            capital_range_low=request_data.capital_range_low,
            capital_range_high=request_data.capital_range_high,
            opportunities=opportunities,
        )

        # Generate report (eligibility gate is applied inside)
        result = generate_report(mandate)

        if isinstance(result, ReportSuccess):
            filename = result.path.name
            return JSONResponse({
                "success": True,
                "pdf_url": f"/reports/{filename}",
                "filename": filename,
                "opportunities_included": result.opportunities_included,
            })
        else:
            return JSONResponse({
                "success": False,
                "message": result.message,
            })

    @app.get("/api/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "0.1.0",
            "environment": "production" if IS_PRODUCTION else "development",
        }

    return app


# Create app instance for uvicorn
app = create_app()
