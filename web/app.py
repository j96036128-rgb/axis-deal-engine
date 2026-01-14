"""
FastAPI application for the deal engine web interface.
Phase 7: Planning Context Input + UI Surfacing
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import SearchCriteria, BMVScorer
from scraper import MockScraper


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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Axis Deal Engine",
        description="Internal deal sourcing engine for property opportunities",
        version="0.1.0",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Initialize components
    scraper = MockScraper()
    scorer = BMVScorer()

    @app.get("/", response_class=HTMLResponse)
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

        # Fetch listings
        listings = await scraper.search(criteria)

        # Filter by max price if specified
        if criteria.max_price:
            listings = [l for l in listings if l.asking_price <= criteria.max_price]

        # Analyze listings
        analyses = scorer.analyze_batch(listings, criteria)

        # Add planning assessment to each analysis for combined opportunity check
        for analysis in analyses:
            analysis.planning = planning_assessment
            # Check for combined opportunity (BMV + planning upside)
            if planning_assessment and planning_assessment.has_upside:
                if hasattr(analysis, 'recommendation') and analysis.recommendation in ('Strong', 'Moderate'):
                    analysis.combined_opportunity = True
                else:
                    analysis.combined_opportunity = False
            else:
                analysis.combined_opportunity = False

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
            },
        )

    @app.get("/api/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "version": "0.1.0"}

    return app


# Create app instance for uvicorn
app = create_app()
