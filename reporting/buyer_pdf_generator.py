"""
Axis Allocation - Buyer Capital Opportunity Memorandum PDF Generator (v1.0 - Locked)

IMPORTANT: This layout is locked for delivery.
Spacing, typography, and structure must not be modified without explicit versioning (v1.1+).

Generates client-facing PDF reports from VerifiedPropertyExport ONLY.
No other data source is permitted.

Principles:
- Conservative: No superlatives, no guarantees
- Transparent: All confidence levels visible
- Verification-aware: Explicit unverified flags with colour coding
- Non-advisory: No investment advice
- Deterministic: Same input = same PDF

Library Choice: ReportLab
- Pure Python, no external dependencies
- Deterministic output (same input = same PDF)
- Fine-grained control over layout

Output Structure (LOCKED):
1. Cover Page
2. Executive Summary (max 1 page)
3. Verified Facts Snapshot
4. Valuation Evidence (Comps)
5. Value Creation Scenarios
6. Risks & Unknowns (MANDATORY)
7. Next Steps (Non-Advisory)
8. Integrity & Provenance
9. Legal Footer (FIXED)

Version: 1.0
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, Union

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.submission.export import TrustLevel, VerifiedPropertyExport

from .buyer_schemas import (
    SCHEMA_VERSION,
    BuyerMemorandum,
    BuyerMemorandumValidationError,
    ConfidenceLevel,
    DealClassification,
    FactVerificationStatus,
    create_buyer_memorandum_from_export,
)


# =============================================================================
# Constants
# =============================================================================

GENERATOR_VERSION: Final[str] = "1.0"


# =============================================================================
# Color Palette - Professional, print-friendly
# =============================================================================


class BuyerPalette:
    """
    Professional color palette for buyer memorandum.
    Conservative, print-friendly colours.
    """

    # Primary text
    BLACK = colors.Color(0.1, 0.1, 0.1)
    CHARCOAL = colors.Color(0.2, 0.2, 0.22)
    SLATE = colors.Color(0.35, 0.38, 0.42)
    GRAY = colors.Color(0.5, 0.5, 0.5)
    LIGHT_GRAY = colors.Color(0.85, 0.85, 0.85)
    PALE_GRAY = colors.Color(0.95, 0.95, 0.95)
    WHITE = colors.white

    # Accent (navy blue)
    ACCENT = colors.Color(0.15, 0.25, 0.4)

    # Verification status colours (muted for print)
    VERIFIED = colors.Color(0.15, 0.4, 0.25)  # Dark green
    VERIFIED_BG = colors.Color(0.9, 0.95, 0.9)  # Light green
    UNVERIFIED = colors.Color(0.6, 0.4, 0.1)  # Dark amber
    UNVERIFIED_BG = colors.Color(0.98, 0.96, 0.9)  # Light amber
    NOT_AVAILABLE = colors.Color(0.5, 0.5, 0.5)  # Gray
    NOT_AVAILABLE_BG = colors.Color(0.95, 0.95, 0.95)  # Light gray

    # Confidence level colours
    HIGH_CONFIDENCE = colors.Color(0.15, 0.4, 0.25)
    MEDIUM_CONFIDENCE = colors.Color(0.5, 0.4, 0.15)
    LOW_CONFIDENCE = colors.Color(0.5, 0.25, 0.15)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class BuyerReportSuccess:
    """Returned when PDF generation succeeds."""

    path: Path
    memorandum_version: str


@dataclass
class BuyerReportValidationError:
    """Returned when memorandum validation fails."""

    errors: list[str]


@dataclass
class BuyerReportLowConfidenceWarning:
    """Returned when confidence is LOW and strong language would be inappropriate."""

    path: Path
    warning: str


BuyerReportResult = Union[BuyerReportSuccess, BuyerReportValidationError, BuyerReportLowConfidenceWarning]


# =============================================================================
# Style Configuration
# =============================================================================


def get_buyer_styles() -> dict:
    """
    Create paragraph styles for the Buyer Capital Opportunity Memorandum.
    """
    styles = getSampleStyleSheet()

    # Cover page - wordmark top-left, no centering
    styles.add(ParagraphStyle(
        name="BuyerCoverBrand",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=BuyerPalette.BLACK,
        alignment=TA_LEFT,
        fontName="Helvetica",
        letterSpacing=1.5,
    ))

    styles.add(ParagraphStyle(
        name="BuyerCoverTitle",
        parent=styles["Normal"],
        fontSize=20,
        leading=26,
        textColor=BuyerPalette.CHARCOAL,
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        spaceAfter=8 * mm,
    ))

    styles.add(ParagraphStyle(
        name="BuyerCoverSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=BuyerPalette.SLATE,
        alignment=TA_LEFT,
        fontName="Helvetica",
        spaceAfter=3 * mm,
    ))

    styles.add(ParagraphStyle(
        name="BuyerCoverDisclaimer",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=BuyerPalette.GRAY,
        alignment=TA_LEFT,
        fontName="Helvetica",
    ))

    # Section headers
    styles.add(ParagraphStyle(
        name="BuyerSectionTitle",
        parent=styles["Normal"],
        fontSize=14,
        leading=18,
        textColor=BuyerPalette.CHARCOAL,
        fontName="Helvetica-Bold",
        spaceBefore=18,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="BuyerSubsectionTitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=BuyerPalette.SLATE,
        fontName="Helvetica-Bold",
        spaceBefore=12,
        spaceAfter=6,
    ))

    # Body text - 1.5x line height
    styles.add(ParagraphStyle(
        name="BuyerBodyText",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14.25,  # 9.5 * 1.5
        textColor=BuyerPalette.CHARCOAL,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
    ))

    styles.add(ParagraphStyle(
        name="BuyerBodyTextCompact",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=BuyerPalette.CHARCOAL,
        spaceAfter=4,
        fontName="Helvetica",
    ))

    # Bullet points
    styles.add(ParagraphStyle(
        name="BuyerBulletText",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        leftIndent=6 * mm,
        bulletIndent=2 * mm,
        spaceAfter=4,
        textColor=BuyerPalette.CHARCOAL,
        fontName="Helvetica",
    ))

    # Table styles
    styles.add(ParagraphStyle(
        name="BuyerTableHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=BuyerPalette.WHITE,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name="BuyerTableCell",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=BuyerPalette.CHARCOAL,
        fontName="Helvetica",
    ))

    styles.add(ParagraphStyle(
        name="BuyerTableCellBold",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=BuyerPalette.CHARCOAL,
        fontName="Helvetica-Bold",
    ))

    # Metric display
    styles.add(ParagraphStyle(
        name="BuyerMetricValue",
        parent=styles["Normal"],
        fontSize=16,
        leading=20,
        textColor=BuyerPalette.ACCENT,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        name="BuyerMetricLabel",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=BuyerPalette.SLATE,
        alignment=TA_CENTER,
        fontName="Helvetica",
    ))

    # Confidence indicators
    styles.add(ParagraphStyle(
        name="BuyerConfidenceHigh",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=BuyerPalette.HIGH_CONFIDENCE,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        name="BuyerConfidenceMedium",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=BuyerPalette.MEDIUM_CONFIDENCE,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        name="BuyerConfidenceLow",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=BuyerPalette.LOW_CONFIDENCE,
        fontName="Helvetica-Bold",
    ))

    # Disclaimer
    styles.add(ParagraphStyle(
        name="BuyerDisclaimer",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=11,
        textColor=BuyerPalette.GRAY,
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
        spaceBefore=12,
        spaceAfter=6,
        leftIndent=5 * mm,
        rightIndent=5 * mm,
    ))

    # Footer
    styles.add(ParagraphStyle(
        name="BuyerFooter",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=BuyerPalette.GRAY,
        fontName="Helvetica",
    ))

    return styles


# =============================================================================
# Buyer PDF Generator
# =============================================================================


class BuyerPDFGenerator:
    """
    Generates Buyer Capital Opportunity Memorandum PDFs.

    CRITICAL: Only accepts VerifiedPropertyExport as input.
    No other data source is permitted.

    Usage:
        generator = BuyerPDFGenerator()
        result = generator.generate_from_export(export, deal_classification, emv, bmv, confidence)
    """

    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN_LEFT = 18 * mm
    MARGIN_RIGHT = 18 * mm
    MARGIN_TOP = 18 * mm
    MARGIN_BOTTOM = 22 * mm

    OUTPUT_DIR = Path("reports/buyer")

    def __init__(self):
        """Initialize the generator with styles."""
        self.styles = get_buyer_styles()

    def generate_from_export(
        self,
        export: VerifiedPropertyExport,
        deal_classification: DealClassification,
        estimated_market_value: int,
        bmv_percent: float,
        confidence_level: ConfidenceLevel,
        comp_count: int = 0,
        comp_radius_miles: float = 0.0,
        comp_date_range_months: int = 0,
        client_name: str | None = None,
        bmv_range_low: float | None = None,
        bmv_range_high: float | None = None,
    ) -> BuyerReportResult:
        """
        Generate a Buyer Capital Opportunity Memorandum from VerifiedPropertyExport.

        Args:
            export: The ONLY permitted data source
            deal_classification: From Deal Engine
            estimated_market_value: Comps-based EMV
            bmv_percent: Below market value percentage
            confidence_level: Valuation confidence
            comp_count: Number of comps used
            comp_radius_miles: Comp search radius
            comp_date_range_months: Comp date range
            client_name: Optional client name
            bmv_range_low: Low BMV range (if confidence < HIGH)
            bmv_range_high: High BMV range (if confidence < HIGH)

        Returns:
            BuyerReportSuccess, BuyerReportValidationError, or BuyerReportLowConfidenceWarning
        """
        # Create memorandum from export
        try:
            memorandum = create_buyer_memorandum_from_export(
                export=export,
                deal_classification=deal_classification,
                estimated_market_value=estimated_market_value,
                bmv_percent=bmv_percent,
                confidence_level=confidence_level,
                comp_count=comp_count,
                comp_radius_miles=comp_radius_miles,
                comp_date_range_months=comp_date_range_months,
                client_name=client_name,
                bmv_range_low=bmv_range_low,
                bmv_range_high=bmv_range_high,
            )
        except BuyerMemorandumValidationError as e:
            return BuyerReportValidationError(errors=e.errors)

        # Validate memorandum
        is_valid, errors = memorandum.validate()
        if not is_valid:
            return BuyerReportValidationError(errors=errors)

        # Ensure output directory exists
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"BUYER-{export.property_id}.pdf"
        output_path = self.OUTPUT_DIR / filename

        # Generate PDF
        buffer = BytesIO()
        self._build_document(memorandum, buffer)

        # Write to file
        output_path.write_bytes(buffer.getvalue())

        # Return with warning if low confidence
        if confidence_level == ConfidenceLevel.LOW:
            return BuyerReportLowConfidenceWarning(
                path=output_path,
                warning="Low confidence - no STRONG language used in assessment.",
            )

        return BuyerReportSuccess(
            path=output_path,
            memorandum_version=SCHEMA_VERSION,
        )

    def generate_to_buffer(self, memorandum: BuyerMemorandum) -> bytes:
        """Generate PDF and return as bytes."""
        # Validate first
        is_valid, errors = memorandum.validate()
        if not is_valid:
            raise BuyerMemorandumValidationError(errors)

        buffer = BytesIO()
        self._build_document(memorandum, buffer)
        return buffer.getvalue()

    def _build_document(self, memorandum: BuyerMemorandum, buffer: BytesIO):
        """Build the complete PDF document."""
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.MARGIN_LEFT,
            rightMargin=self.MARGIN_RIGHT,
            topMargin=self.MARGIN_TOP,
            bottomMargin=self.MARGIN_BOTTOM,
            title=f"Buyer Capital Opportunity Memorandum - {memorandum.source_property_id}",
            author="Axis Allocation",
            subject="Property Investment Opportunity",
        )

        self._current_memorandum = memorandum

        story = []

        # Build each section
        story.extend(self._build_cover_page(memorandum))
        story.append(PageBreak())

        story.extend(self._build_executive_summary(memorandum))
        story.append(PageBreak())

        story.extend(self._build_verified_facts(memorandum))
        story.append(PageBreak())

        story.extend(self._build_valuation_evidence(memorandum))
        story.append(PageBreak())

        story.extend(self._build_value_creation(memorandum))
        story.append(PageBreak())

        story.extend(self._build_risks_unknowns(memorandum))
        story.append(PageBreak())

        story.extend(self._build_next_steps(memorandum))
        story.append(PageBreak())

        story.extend(self._build_integrity_provenance(memorandum))
        story.append(PageBreak())

        story.extend(self._build_legal_footer(memorandum))

        # Build with page handlers
        doc.build(
            story,
            onFirstPage=self._draw_cover_page,
            onLaterPages=self._draw_page_frame,
        )

    def _draw_cover_page(self, canvas_obj: canvas.Canvas, doc):
        """Draw cover page frame (minimal)."""
        pass

    def _draw_page_frame(self, canvas_obj: canvas.Canvas, doc):
        """Draw footer on content pages."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(BuyerPalette.GRAY)

        # Left: wordmark
        canvas_obj.drawString(
            self.MARGIN_LEFT,
            self.MARGIN_BOTTOM - 10 * mm,
            "AXIS ALLOCATION",
        )

        # Right: page number
        canvas_obj.drawRightString(
            self.PAGE_WIDTH - self.MARGIN_RIGHT,
            self.MARGIN_BOTTOM - 10 * mm,
            f"{doc.page}",
        )

        canvas_obj.restoreState()

    # =========================================================================
    # Section 1: Cover Page
    # =========================================================================

    def _build_cover_page(self, memo: BuyerMemorandum) -> list:
        """Build cover page - wordmark top-left, no centering, no photos."""
        elements = []
        cover = memo.cover_page

        # Wordmark
        elements.append(Paragraph("AXIS ALLOCATION", self.styles["BuyerCoverBrand"]))
        elements.append(Spacer(1, 50 * mm))

        # Document title
        elements.append(Paragraph(
            "Capital Opportunity Memorandum",
            self.styles["BuyerCoverTitle"],
        ))
        elements.append(Spacer(1, 15 * mm))

        # Property reference
        elements.append(Paragraph(
            f"Property Reference: {cover.property_reference}",
            self.styles["BuyerCoverSubtitle"],
        ))

        # Client name (optional)
        if cover.client_name:
            elements.append(Paragraph(
                f"Prepared for: {cover.client_name}",
                self.styles["BuyerCoverSubtitle"],
            ))

        # Date
        elements.append(Paragraph(
            f"Date: {cover.document_date}",
            self.styles["BuyerCoverSubtitle"],
        ))

        # Version
        elements.append(Paragraph(
            f"Document Version: {cover.document_version}",
            self.styles["BuyerCoverSubtitle"],
        ))

        elements.append(Spacer(1, 40 * mm))

        # Fixed legal disclaimer
        elements.append(Paragraph(
            cover.legal_disclaimer,
            self.styles["BuyerCoverDisclaimer"],
        ))

        return elements

    # =========================================================================
    # Section 2: Executive Summary
    # =========================================================================

    def _build_executive_summary(self, memo: BuyerMemorandum) -> list:
        """Build executive summary - max 1 page, no guarantees."""
        elements = []
        summary = memo.executive_summary

        elements.append(Paragraph("Executive Summary", self.styles["BuyerSectionTitle"]))

        # Deal classification
        elements.append(Paragraph(
            f"<b>Deal Classification:</b> {summary.deal_classification.value.upper()}",
            self.styles["BuyerBodyText"],
        ))

        # Estimated Market Value
        elements.append(Paragraph(
            f"<b>Estimated Market Value:</b> £{summary.estimated_market_value:,}",
            self.styles["BuyerBodyText"],
        ))

        # BMV percentage (with range if not HIGH confidence)
        if summary.bmv_range_low is not None and summary.bmv_range_high is not None:
            elements.append(Paragraph(
                f"<b>Below Market Value:</b> {summary.bmv_percent:.1f}% (range: {summary.bmv_range_low:.1f}% - {summary.bmv_range_high:.1f}%)",
                self.styles["BuyerBodyText"],
            ))
        else:
            elements.append(Paragraph(
                f"<b>Below Market Value:</b> {summary.bmv_percent:.1f}%",
                self.styles["BuyerBodyText"],
            ))

        # Confidence level (MANDATORY - always visible)
        confidence_style = {
            ConfidenceLevel.HIGH: "BuyerConfidenceHigh",
            ConfidenceLevel.MEDIUM: "BuyerConfidenceMedium",
            ConfidenceLevel.LOW: "BuyerConfidenceLow",
        }.get(summary.confidence_level, "BuyerConfidenceLow")

        elements.append(Spacer(1, 6))
        elements.append(Paragraph(
            f"Confidence Level: {summary.confidence_level.value.upper()}",
            self.styles[confidence_style],
        ))
        elements.append(Spacer(1, 6))

        # Planning upside (only if verified)
        if summary.planning_upside_verified:
            elements.append(Paragraph(
                f"<b>Planning Upside:</b> {summary.planning_upside_description or 'Verified'}",
                self.styles["BuyerBodyText"],
            ))
        else:
            elements.append(Paragraph(
                "<b>Planning Upside:</b> Not verified",
                self.styles["BuyerBodyText"],
            ))

        # Overall assessment (controlled language)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            "<b>Assessment</b>",
            self.styles["BuyerSubsectionTitle"],
        ))
        elements.append(Paragraph(
            summary.overall_assessment,
            self.styles["BuyerBodyText"],
        ))

        return elements

    # =========================================================================
    # Section 3: Verified Facts Snapshot
    # =========================================================================

    def _build_verified_facts(self, memo: BuyerMemorandum) -> list:
        """Build verified facts table with colour-coded status."""
        elements = []
        facts = memo.verified_facts

        elements.append(Paragraph("Verified Facts Snapshot", self.styles["BuyerSectionTitle"]))

        # Trust level indicator
        trust_text = f"Trust Level: {facts.trust_level.value.upper()} ({facts.verified_count} verified, {facts.unverified_count} unverified)"
        elements.append(Paragraph(trust_text, self.styles["BuyerBodyTextCompact"]))
        elements.append(Spacer(1, 10))

        # Build table
        table_data = [["Category", "Fact", "Value", "Status"]]

        for fact in facts.facts:
            status_text = fact.status.value.upper()
            table_data.append([
                fact.category,
                fact.fact,
                fact.value,
                status_text,
            ])

        table = Table(table_data, colWidths=[35 * mm, 40 * mm, 55 * mm, 30 * mm])

        # Build style with row colouring based on verification status
        table_style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), BuyerPalette.CHARCOAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), BuyerPalette.WHITE),
            ("TEXTCOLOR", (0, 1), (-1, -1), BuyerPalette.CHARCOAL),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, BuyerPalette.LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ]

        # Add row colouring based on status
        for i, fact in enumerate(facts.facts, start=1):
            if fact.status == FactVerificationStatus.VERIFIED:
                table_style.append(("BACKGROUND", (3, i), (3, i), BuyerPalette.VERIFIED_BG))
                table_style.append(("TEXTCOLOR", (3, i), (3, i), BuyerPalette.VERIFIED))
            elif fact.status == FactVerificationStatus.UNVERIFIED:
                table_style.append(("BACKGROUND", (3, i), (3, i), BuyerPalette.UNVERIFIED_BG))
                table_style.append(("TEXTCOLOR", (3, i), (3, i), BuyerPalette.UNVERIFIED))
            else:
                table_style.append(("BACKGROUND", (3, i), (3, i), BuyerPalette.NOT_AVAILABLE_BG))
                table_style.append(("TEXTCOLOR", (3, i), (3, i), BuyerPalette.NOT_AVAILABLE))

        table.setStyle(TableStyle(table_style))
        elements.append(table)

        return elements

    # =========================================================================
    # Section 4: Valuation Evidence
    # =========================================================================

    def _build_valuation_evidence(self, memo: BuyerMemorandum) -> list:
        """Build valuation evidence section - comps only, median (never mean)."""
        elements = []
        evidence = memo.valuation_evidence

        elements.append(Paragraph("Valuation Evidence", self.styles["BuyerSectionTitle"]))

        # Locked language prefix
        elements.append(Paragraph(
            f"{evidence.evidence_statement}:",
            self.styles["BuyerBodyText"],
        ))

        elements.append(Spacer(1, 8))

        # Evidence details table
        table_data = [
            ["Metric", "Value"],
            ["Comparable Sales Used", str(evidence.comp_count)],
            ["Search Radius", f"{evidence.radius_miles} miles"],
            ["Date Range", f"{evidence.date_range_months} months"],
            ["Median Price", f"£{evidence.median_price:,}"],
            ["Confidence", evidence.confidence_level.value.upper()],
        ]

        table = Table(table_data, colWidths=[60 * mm, 60 * mm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), BuyerPalette.CHARCOAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), BuyerPalette.WHITE),
            ("TEXTCOLOR", (0, 1), (-1, -1), BuyerPalette.CHARCOAL),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, BuyerPalette.LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        elements.append(table)

        return elements

    # =========================================================================
    # Section 5: Value Creation Scenarios
    # =========================================================================

    def _build_value_creation(self, memo: BuyerMemorandum) -> list:
        """Build value creation section - no ROI projections, no guarantees."""
        elements = []
        value_creation = memo.value_creation

        elements.append(Paragraph("Value Creation Scenarios", self.styles["BuyerSectionTitle"]))

        if not value_creation or not value_creation.scenarios:
            elements.append(Paragraph(
                "No verified value creation scenarios available for this property.",
                self.styles["BuyerBodyText"],
            ))
            if value_creation and not value_creation.has_verified_planning:
                elements.append(Paragraph(
                    "Planning status has not been verified. Any planning-related value creation "
                    "would require professional assessment.",
                    self.styles["BuyerBodyText"],
                ))
            return elements

        for scenario in value_creation.scenarios:
            elements.append(Paragraph(
                f"<b>{scenario.scenario_type.value.replace('_', ' ').title()}</b>",
                self.styles["BuyerSubsectionTitle"],
            ))

            elements.append(Paragraph(
                f"<b>Description:</b> {scenario.description}",
                self.styles["BuyerBodyText"],
            ))

            if scenario.preconditions:
                elements.append(Paragraph("<b>Preconditions:</b>", self.styles["BuyerBodyTextCompact"]))
                for item in scenario.preconditions:
                    elements.append(Paragraph(f"• {item}", self.styles["BuyerBulletText"]))

            if scenario.risks:
                elements.append(Paragraph("<b>Risks:</b>", self.styles["BuyerBodyTextCompact"]))
                for item in scenario.risks:
                    elements.append(Paragraph(f"• {item}", self.styles["BuyerBulletText"]))

            if scenario.verification_dependencies:
                elements.append(Paragraph("<b>Verification Dependencies:</b>", self.styles["BuyerBodyTextCompact"]))
                for item in scenario.verification_dependencies:
                    elements.append(Paragraph(f"• {item}", self.styles["BuyerBulletText"]))

        return elements

    # =========================================================================
    # Section 6: Risks & Unknowns (MANDATORY)
    # =========================================================================

    def _build_risks_unknowns(self, memo: BuyerMemorandum) -> list:
        """Build risks & unknowns section - can NEVER be empty."""
        elements = []
        risks = memo.risks_and_unknowns

        elements.append(Paragraph("Risks & Unknowns", self.styles["BuyerSectionTitle"]))

        # Unverified facts
        elements.append(Paragraph("<b>Unverified Information</b>", self.styles["BuyerSubsectionTitle"]))
        for fact in risks.unverified_facts:
            elements.append(Paragraph(f"• {fact}", self.styles["BuyerBulletText"]))

        elements.append(Spacer(1, 8))

        # Planning uncertainty
        elements.append(Paragraph("<b>Planning Uncertainty</b>", self.styles["BuyerSubsectionTitle"]))
        elements.append(Paragraph(risks.planning_uncertainty, self.styles["BuyerBodyText"]))

        # Market sensitivity
        elements.append(Paragraph("<b>Market Sensitivity</b>", self.styles["BuyerSubsectionTitle"]))
        elements.append(Paragraph(risks.market_sensitivity, self.styles["BuyerBodyText"]))

        # Additional risks
        if risks.additional_risks:
            elements.append(Paragraph("<b>Additional Considerations</b>", self.styles["BuyerSubsectionTitle"]))
            for risk in risks.additional_risks:
                elements.append(Paragraph(f"• {risk}", self.styles["BuyerBulletText"]))

        return elements

    # =========================================================================
    # Section 7: Next Steps (Non-Advisory)
    # =========================================================================

    def _build_next_steps(self, memo: BuyerMemorandum) -> list:
        """Build next steps section - non-advisory only."""
        elements = []
        next_steps = memo.next_steps

        elements.append(Paragraph("Suggested Next Steps", self.styles["BuyerSectionTitle"]))

        elements.append(Paragraph(
            "The following actions are suggested for consideration. This does not constitute "
            "advice to proceed with any transaction.",
            self.styles["BuyerBodyText"],
        ))

        elements.append(Spacer(1, 8))

        for item in next_steps.items:
            elements.append(Paragraph(f"• {item}", self.styles["BuyerBulletText"]))

        return elements

    # =========================================================================
    # Section 8: Integrity & Provenance
    # =========================================================================

    def _build_integrity_provenance(self, memo: BuyerMemorandum) -> list:
        """Build integrity & provenance table."""
        elements = []
        integrity = memo.integrity_provenance

        elements.append(Paragraph("Integrity & Provenance", self.styles["BuyerSectionTitle"]))

        elements.append(Paragraph(
            "This section provides traceability for the data used in this memorandum.",
            self.styles["BuyerBodyText"],
        ))

        elements.append(Spacer(1, 8))

        # Integrity table
        table_data = [
            ["Item", "Value"],
            ["Logbook Hash Chain Status", "VALID" if integrity.chain_valid else "INVALID"],
            ["Logbook Version", str(integrity.logbook_version)],
            ["Logbook Hash", integrity.logbook_hash[:16] + "..."],
            ["Export Version", integrity.export_version],
            ["Evaluation Timestamp", integrity.evaluation_timestamp],
        ]

        if integrity.title_register_hash:
            table_data.append(["Title Register Hash", integrity.title_register_hash[:16] + "..."])
        if integrity.epc_hash:
            table_data.append(["EPC Hash", integrity.epc_hash[:16] + "..."])

        table = Table(table_data, colWidths=[60 * mm, 100 * mm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), BuyerPalette.CHARCOAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), BuyerPalette.WHITE),
            ("TEXTCOLOR", (0, 1), (-1, -1), BuyerPalette.CHARCOAL),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, BuyerPalette.LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        elements.append(table)

        return elements

    # =========================================================================
    # Section 9: Legal Footer (FIXED)
    # =========================================================================

    def _build_legal_footer(self, memo: BuyerMemorandum) -> list:
        """Build legal footer - FIXED content, never changes."""
        elements = []
        footer = memo.legal_footer

        elements.append(Paragraph("Disclaimer & Legal Notice", self.styles["BuyerSectionTitle"]))

        # Fixed disclaimer text
        elements.append(Paragraph(footer.disclaimer, self.styles["BuyerDisclaimer"]))

        elements.append(Spacer(1, 10))

        # Data sources
        elements.append(Paragraph(
            f"<b>Data Sources:</b> {footer.data_sources}",
            self.styles["BuyerFooter"],
        ))

        # Authorship
        elements.append(Paragraph(
            f"<b>Prepared by:</b> {footer.author}",
            self.styles["BuyerFooter"],
        ))

        # Jurisdiction
        elements.append(Paragraph(
            f"<b>Jurisdiction:</b> {footer.jurisdiction}",
            self.styles["BuyerFooter"],
        ))

        return elements
