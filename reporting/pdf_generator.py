"""
Axis Allocation – Capital Opportunity Memorandum (v1.2 – Locked)

IMPORTANT: This layout is client-approved and intentionally fixed for delivery.
Spacing, typography, and structure must not be modified without explicit versioning (v1.3+).
Future changes should be additive (content only), not structural.

Generates professional, client-ready PDF reports from mandate and deal analysis data.
Uses ReportLab for deterministic PDF generation.

Library Choice: ReportLab
- Pure Python, no external dependencies
- Deterministic output (same input = same PDF)
- Fine-grained control over layout
- Well-suited for structured financial documents
- No browser/rendering engine required (unlike WeasyPrint)

Output Structure (Hybrid Format – Locked):
1. Cover Page
2. Service Scope & Important Notice
3. Executive Summary
4. Your Mandate
5. How Opportunities Were Identified
6. Opportunity Detail (per deal)
7. Comparative Opportunity Summary
8. Risks & Considerations
9. Suggested Next Steps
10. Disclaimer & Contact

Version History:
- v1.0: Initial structure
- v1.1: Spacing refinements
- v1.2: Premium spacing, client-approved (LOCKED)
"""

from pathlib import Path
from typing import List, Optional, Union
from io import BytesIO
from datetime import datetime
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
    ListFlowable,
    ListItem,
)
from reportlab.pdfgen import canvas

from .schemas import Mandate, OpportunityMemo, ConvictionRating, PriorityLevel


# =============================================================================
# Report Generation Result Types
# =============================================================================

@dataclass
class ReportSuccess:
    """Returned when PDF generation succeeds."""
    path: Path
    opportunities_included: int


@dataclass
class ReportNoQualifyingOpportunities:
    """Returned when no opportunities meet the eligibility criteria."""
    message: str = "No qualifying opportunities for memorandum generation."


# Type alias for generate_report return value
ReportResult = Union[ReportSuccess, ReportNoQualifyingOpportunities]

# Eligibility constants
ELIGIBLE_RECOMMENDATIONS = {"strong", "moderate"}
MAX_OPPORTUNITIES_PER_PDF = 3


# =============================================================================
# Color Palette - Clean, print-friendly institutional style
# =============================================================================

class Palette:
    """
    Professional color palette optimised for print.
    White/light background with charcoal text for readability.
    """
    # Primary text colors
    BLACK = colors.Color(0.1, 0.1, 0.1)
    CHARCOAL = colors.Color(0.2, 0.2, 0.22)
    SLATE = colors.Color(0.35, 0.38, 0.42)
    GRAY = colors.Color(0.5, 0.5, 0.5)
    LIGHT_GRAY = colors.Color(0.85, 0.85, 0.85)
    PALE_GRAY = colors.Color(0.95, 0.95, 0.95)
    WHITE = colors.white

    # Accent - subtle navy blue
    ACCENT = colors.Color(0.15, 0.25, 0.4)
    ACCENT_LIGHT = colors.Color(0.92, 0.94, 0.97)

    # Status indicators (muted for print)
    SUCCESS = colors.Color(0.15, 0.4, 0.25)
    SUCCESS_LIGHT = colors.Color(0.9, 0.95, 0.9)
    WARNING = colors.Color(0.5, 0.4, 0.15)
    WARNING_LIGHT = colors.Color(0.98, 0.96, 0.9)


# =============================================================================
# Style Configuration
# =============================================================================

def get_report_styles() -> dict:
    """
    Create paragraph styles for the Capital Opportunity Memorandum.
    Returns a StyleSheet with custom styles for each document element.
    """
    styles = getSampleStyleSheet()

    # Cover page styles - wordmark top-left, no centering, no decoration
    styles.add(ParagraphStyle(
        name='CoverBrand',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        textColor=Palette.BLACK,
        alignment=TA_LEFT,
        fontName='Helvetica',
        spaceAfter=0,
        letterSpacing=1.5,
    ))

    styles.add(ParagraphStyle(
        name='CoverTitle',
        parent=styles['Normal'],
        fontSize=22,
        leading=28,
        textColor=Palette.CHARCOAL,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=10*mm,
    ))

    styles.add(ParagraphStyle(
        name='CoverSubtitle',
        parent=styles['Normal'],
        fontSize=11,
        leading=15,
        textColor=Palette.SLATE,
        alignment=TA_LEFT,
        fontName='Helvetica',
        spaceAfter=3*mm,
    ))

    styles.add(ParagraphStyle(
        name='CoverDisclaimer',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        textColor=Palette.GRAY,
        alignment=TA_LEFT,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        name='CoverFooter',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=Palette.GRAY,
        alignment=TA_LEFT,
        fontName='Helvetica',
    ))

    # Section headers - increased breathing room
    styles.add(ParagraphStyle(
        name='SectionTitle',
        parent=styles['Normal'],
        fontSize=14,
        leading=18,
        textColor=Palette.CHARCOAL,
        fontName='Helvetica-Bold',
        spaceBefore=22,  # Generous top margin
        spaceAfter=14,   # +12-16pt to first content
        borderWidth=0,
        borderPadding=(0, 0, 2*mm, 0),
        borderColor=Palette.ACCENT,
    ))

    # Subsection titles - clear separation
    styles.add(ParagraphStyle(
        name='SubsectionTitle',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        textColor=Palette.SLATE,
        fontName='Helvetica-Bold',
        spaceBefore=14,  # Never back-to-back without separation
        spaceAfter=8,    # +8-10pt to content
    ))

    # Opportunity title - visually isolated
    styles.add(ParagraphStyle(
        name='OpportunityTitle',
        parent=styles['Normal'],
        fontSize=13,
        leading=16,
        textColor=Palette.CHARCOAL,
        fontName='Helvetica-Bold',
        spaceBefore=22,  # +18-22pt above
        spaceAfter=12,   # +10-12pt below
    ))

    # Body text - 1.5x line height for premium feel, +6pt after paragraph
    styles['BodyText'].fontSize = 9.5
    styles['BodyText'].leading = 14.25  # 9.5 * 1.5 = 14.25pt
    styles['BodyText'].textColor = Palette.CHARCOAL
    styles['BodyText'].spaceAfter = 6  # +6pt after every paragraph
    styles['BodyText'].alignment = TA_JUSTIFY
    styles['BodyText'].fontName = 'Helvetica'

    # Additional body styles
    styles.add(ParagraphStyle(
        name='BodyTextCompact',
        parent=styles['BodyText'],
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name='SmallText',
        parent=styles['Normal'],
        fontSize=8,
        leading=12,  # 1.5x line spacing
        textColor=Palette.GRAY,
        fontName='Helvetica',
        spaceAfter=4,
    ))

    # Disclaimer - 1.5x line spacing, +14pt above
    styles.add(ParagraphStyle(
        name='Disclaimer',
        parent=styles['Normal'],
        fontSize=7.5,
        leading=11.25,  # 7.5 * 1.5 = 11.25pt
        textColor=Palette.GRAY,
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
        spaceBefore=14,  # +14pt above disclaimers
        spaceAfter=6,
        leftIndent=5*mm,   # Reduce line width slightly
        rightIndent=5*mm,
    ))

    # Bullet points - +4pt between items
    styles.add(ParagraphStyle(
        name='BulletText',
        parent=styles['BodyText'],
        fontSize=9,
        leading=13,  # 9 * 1.45 ≈ 13pt
        leftIndent=6*mm,
        bulletIndent=2*mm,
        spaceAfter=4,  # +4pt between bullet items
    ))

    styles.add(ParagraphStyle(
        name='BulletTextCheck',
        parent=styles['BodyText'],
        fontSize=9,
        leading=13,
        leftIndent=6*mm,
        bulletIndent=2*mm,
        spaceAfter=4,  # +4pt between bullet items
        textColor=Palette.SUCCESS,
    ))

    styles.add(ParagraphStyle(
        name='BulletTextCross',
        parent=styles['BodyText'],
        fontSize=9,
        leading=13,
        leftIndent=6*mm,
        bulletIndent=2*mm,
        spaceAfter=4,  # +4pt between bullet items
        textColor=Palette.SLATE,
    ))

    # Table styles
    styles.add(ParagraphStyle(
        name='TableHeader',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=Palette.WHITE,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=11,
        textColor=Palette.CHARCOAL,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        name='TableCellBold',
        parent=styles['TableCell'],
        fontName='Helvetica-Bold',
    ))

    # Metric display
    styles.add(ParagraphStyle(
        name='MetricValue',
        parent=styles['Normal'],
        fontSize=18,
        leading=22,
        textColor=Palette.ACCENT,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        name='MetricLabel',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=Palette.SLATE,
        alignment=TA_CENTER,
        fontName='Helvetica',
    ))

    # Tag/badge styles
    styles.add(ParagraphStyle(
        name='CombinedTag',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=Palette.SUCCESS,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
    ))

    return styles


# =============================================================================
# Report Generator Class
# =============================================================================

class ReportGenerator:
    """
    Generates Capital Opportunity Memorandum PDFs.

    Usage:
        generator = ReportGenerator()
        filepath = generator.generate_report(mandate, deals)

    The generator produces deterministic output - the same input will
    always produce the same PDF.
    """

    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN_LEFT = 18*mm
    MARGIN_RIGHT = 18*mm
    MARGIN_TOP = 18*mm
    MARGIN_BOTTOM = 22*mm

    # Output directory
    OUTPUT_DIR = Path("reports")

    def __init__(self):
        """Initialize the report generator with styles."""
        self.styles = get_report_styles()

    def generate_report(self, mandate: Mandate) -> ReportResult:
        """
        Generate a Capital Opportunity Memorandum PDF.

        Applies eligibility gate:
        - Only includes opportunities with STRONG or MODERATE recommendation
        - Maximum 3 opportunities per PDF
        - Returns validation message if zero opportunities qualify

        Args:
            mandate: Complete mandate data including opportunities (raw, unfiltered)

        Returns:
            ReportSuccess with path if PDF generated successfully
            ReportNoQualifyingOpportunities if no opportunities meet criteria
        """
        # Apply eligibility gate: filter to STRONG/MODERATE only
        eligible_opportunities = [
            opp for opp in mandate.opportunities
            if opp.recommendation.lower() in ELIGIBLE_RECOMMENDATIONS
        ]

        # Validation: check for zero qualifying opportunities
        if not eligible_opportunities:
            return ReportNoQualifyingOpportunities()

        # Limit to maximum 3 opportunities (take highest priority first)
        # Opportunities should already be sorted by priority/score from deal engine
        filtered_opportunities = eligible_opportunities[:MAX_OPPORTUNITIES_PER_PDF]

        # Create filtered mandate for PDF generation
        filtered_mandate = Mandate(
            reference_id=mandate.reference_id,
            client_name=mandate.client_name,
            client_entity=mandate.client_entity,
            report_date=mandate.report_date,
            generated_at=mandate.generated_at,
            parameters=mandate.parameters,
            total_properties_screened=mandate.total_properties_screened,
            opportunities_identified=len(filtered_opportunities),
            average_bmv_percent=mandate.average_bmv_percent,
            total_potential_value=mandate.total_potential_value,
            capital_range_low=mandate.capital_range_low,
            capital_range_high=mandate.capital_range_high,
            executive_summary=mandate.executive_summary,
            opportunities=filtered_opportunities,
            disclaimer_version=mandate.disclaimer_version,
            report_version=mandate.report_version,
        )

        # Ensure output directory exists
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Generate filename (v1.2 locked - client-approved format)
        filename = f"AXA-{mandate.reference_id}.pdf"
        output_path = self.OUTPUT_DIR / filename

        # Generate PDF with filtered mandate
        buffer = BytesIO()
        self._build_document(filtered_mandate, buffer)

        # Write to file
        output_path.write_bytes(buffer.getvalue())

        return ReportSuccess(
            path=output_path,
            opportunities_included=len(filtered_opportunities)
        )

    def generate_to_buffer(self, mandate: Mandate) -> bytes:
        """Generate PDF and return as bytes (for testing or streaming)."""
        buffer = BytesIO()
        self._build_document(mandate, buffer)
        return buffer.getvalue()

    def _build_document(self, mandate: Mandate, buffer: BytesIO):
        """Build the complete PDF document."""
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.MARGIN_LEFT,
            rightMargin=self.MARGIN_RIGHT,
            topMargin=self.MARGIN_TOP,
            bottomMargin=self.MARGIN_BOTTOM,
            title=f"Capital Opportunity Memorandum - {mandate.reference_id}",
            author="Axis Allocation",
            subject="Property Investment Opportunities",
        )

        # Store mandate reference for page drawing
        self._current_mandate = mandate

        story = []

        # Build each section per the Hybrid structure
        story.extend(self._build_cover_page(mandate))
        story.append(PageBreak())

        story.extend(self._build_service_scope(mandate))
        story.append(PageBreak())

        story.extend(self._build_executive_summary(mandate))
        story.append(PageBreak())

        story.extend(self._build_your_mandate(mandate))
        story.append(PageBreak())

        story.extend(self._build_methodology(mandate))
        story.append(PageBreak())

        # Opportunity details (2 pages per opportunity)
        for i, opp in enumerate(mandate.opportunities):
            story.extend(self._build_opportunity_overview(opp, i + 1))
            story.append(PageBreak())

        story.extend(self._build_comparative_table(mandate))
        story.append(PageBreak())

        story.extend(self._build_risks(mandate))
        story.append(PageBreak())

        story.extend(self._build_next_steps(mandate))
        story.append(PageBreak())

        story.extend(self._build_contact_disclaimer(mandate))

        # Build document with page handler
        doc.build(
            story,
            onFirstPage=self._draw_cover_page,
            onLaterPages=self._draw_page_frame,
        )

    # =========================================================================
    # Page Drawing Functions
    # =========================================================================

    def _draw_cover_page(self, canvas_obj: canvas.Canvas, doc):
        """Draw cover page frame (minimal - no header/footer)."""
        pass  # Cover page has no header/footer

    def _draw_page_frame(self, canvas_obj: canvas.Canvas, doc):
        """Draw footer on content pages - wordmark left, page number right, quiet."""
        canvas_obj.saveState()

        # Footer text - small, quiet
        canvas_obj.setFont('Helvetica', 7)
        canvas_obj.setFillColor(Palette.GRAY)

        # Left: wordmark only (small, quiet)
        canvas_obj.drawString(
            self.MARGIN_LEFT,
            self.MARGIN_BOTTOM - 10*mm,
            "AXIS ALLOCATION"
        )

        # Right: page number
        canvas_obj.drawRightString(
            self.PAGE_WIDTH - self.MARGIN_RIGHT,
            self.MARGIN_BOTTOM - 10*mm,
            f"{doc.page}"
        )

        canvas_obj.restoreState()

    # =========================================================================
    # Section 1: Cover Page
    # =========================================================================

    def _build_cover_page(self, mandate: Mandate) -> list:
        """Build the cover page with wordmark top-left, no centering, no decoration."""
        elements = []

        # Wordmark - top-left, restrained
        elements.append(Paragraph(
            "AXIS ALLOCATION",
            self.styles['CoverBrand']
        ))

        elements.append(Spacer(1, 50*mm))

        # Document title - left-aligned
        elements.append(Paragraph(
            "Capital Opportunity Memorandum",
            self.styles['CoverTitle']
        ))

        elements.append(Spacer(1, 15*mm))

        # Client details - left-aligned
        client_display = mandate.client_entity or mandate.client_name
        elements.append(Paragraph(
            f"Prepared for: {client_display}",
            self.styles['CoverSubtitle']
        ))

        elements.append(Paragraph(
            f"Reference: {mandate.reference_id}",
            self.styles['CoverSubtitle']
        ))

        # Format date as "DD Month YYYY"
        formatted_date = self._format_date_display(mandate.report_date)
        elements.append(Paragraph(
            f"Date: {formatted_date}",
            self.styles['CoverSubtitle']
        ))

        elements.append(Spacer(1, 45*mm))

        # Confidentiality notice - left-aligned
        elements.append(Paragraph(
            "Confidential – For the sole use of the recipient",
            self.styles['CoverFooter']
        ))

        elements.append(Spacer(1, 8*mm))

        # Cover disclaimer block - left-aligned, no decoration
        disclaimer_text = (
            "This document has been prepared by Axis Allocation for discussion purposes only. "
            "It does not constitute investment advice, a recommendation, or an offer to buy or sell any asset."
        )
        elements.append(Paragraph(
            disclaimer_text,
            self.styles['CoverDisclaimer']
        ))

        return elements

    def _format_date_display(self, date_str: str) -> str:
        """Format date as 'DD Month YYYY'."""
        if not date_str:
            return datetime.now().strftime("%d %B %Y")
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%d %B %Y")
        except (ValueError, TypeError):
            return date_str

    # =========================================================================
    # Section 2: Service Scope & Important Notice
    # =========================================================================

    def _build_service_scope(self, mandate: Mandate) -> list:
        """Build the Service Scope & Important Notice section with exact wording."""
        elements = []

        elements.append(Paragraph(
            "Service Scope & Important Notice",
            self.styles['SectionTitle']
        ))

        # Purpose of This Document
        elements.append(Paragraph(
            "<b>Purpose of This Document</b>",
            self.styles['SubsectionTitle']
        ))

        elements.append(Paragraph(
            "This memorandum summarises a set of property opportunities identified in response "
            "to a specific mandate submitted by the capital provider.",
            self.styles['BodyText']
        ))

        elements.append(Paragraph(
            "The analysis presented is indicative and based on available information, assumptions, "
            "and heuristic evaluation models.",
            self.styles['BodyText']
        ))

        # Important Clarifications
        elements.append(Paragraph(
            "<b>Important Clarifications</b>",
            self.styles['SubsectionTitle']
        ))

        clarifications = [
            "This document does not constitute financial advice, investment advice, or planning advice",
            "Axis Allocation is not acting as an investment advisor, broker, or planning consultant",
            "No representation is made as to the availability, suitability, or outcome of any opportunity",
            "Any planning-related commentary is indicative only and not a substitute for professional advice",
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for item in clarifications:
            elements.append(Paragraph(f"• {item}", self.styles['BulletText']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(
            "Capital providers are responsible for conducting their own due diligence prior to "
            "proceeding with any transaction.",
            self.styles['BodyText']
        ))

        return elements

    # =========================================================================
    # Section 3: Executive Summary
    # =========================================================================

    def _build_executive_summary(self, mandate: Mandate) -> list:
        """Build the Executive Summary section with exact wording."""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['SectionTitle']))

        # Mandate Overview
        elements.append(Paragraph("<b>Mandate Overview</b>", self.styles['SubsectionTitle']))

        params = mandate.parameters
        location = params.location if params else "Not specified"

        mandate_items = [
            ("Asset Focus", "Residential Property"),
            ("Target Strategy", "Below-Market Acquisition with Value Creation Potential"),
            ("Geographic Focus", location),
            ("Target Capital Deployment", f"£{mandate.capital_range_low:,} – £{mandate.capital_range_high:,}"),
            ("Target Return Profile", "Indicative"),
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for label, value in mandate_items:
            elements.append(Paragraph(f"• {label}: {value}", self.styles['BulletText']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        # Opportunity Summary
        elements.append(Paragraph("<b>Opportunity Summary</b>", self.styles['SubsectionTitle']))

        opp_count = len(mandate.opportunities)
        elements.append(Paragraph(
            f"Following an internal review, {opp_count} opportunities were identified that meet "
            "the core mandate parameters.",
            self.styles['BodyText']
        ))

        elements.append(Paragraph("Key themes observed:", self.styles['BodyTextCompact']))

        themes = [
            "Acquisition pricing materially below estimated market value",
            "Additional upside potential through planning-led value creation",
            "Risk characteristics consistent with the stated mandate profile",
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for theme in themes:
            elements.append(Paragraph(f"• {theme}", self.styles['BulletText']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(
            "These opportunities are presented for consideration only.",
            self.styles['BodyText']
        ))

        return elements

    # =========================================================================
    # Section 4: Your Mandate
    # =========================================================================

    def _build_your_mandate(self, mandate: Mandate) -> list:
        """Build the Your Mandate section with exact wording."""
        elements = []

        elements.append(Paragraph("Your Mandate", self.styles['SectionTitle']))

        params = mandate.parameters
        if not params:
            elements.append(Paragraph(
                "No specific parameters recorded.",
                self.styles['BodyText']
            ))
            return elements

        # Mandate snapshot table with exact labels
        snapshot_data = [
            ["Parameter", "Value"],
            ["Asset Type", "Residential Property"],
            ["Location", params.location],
            ["Minimum BMV", f"{params.target_bmv_percent}%"],
            ["Development Angle", params.strategy],
            ["Risk Profile", "As specified in mandate"],
            ["Investment Horizon", "As specified in mandate"],
        ]

        # +12pt vertical padding above table
        elements.append(Spacer(1, 12))

        snapshot_table = Table(snapshot_data, colWidths=[50*mm, 120*mm])
        snapshot_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), Palette.CHARCOAL),
            ('TEXTCOLOR', (0, 0), (-1, 0), Palette.WHITE),
            ('TEXTCOLOR', (0, 1), (-1, -1), Palette.CHARCOAL),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, Palette.LIGHT_GRAY),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5*mm),  # Calm row height
            ('TOPPADDING', (0, 0), (-1, -1), 4.5*mm),     # Calm row height
            ('LEFTPADDING', (0, 0), (-1, -1), 3*mm),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5.5*mm),   # Header row taller
        ]))
        elements.append(snapshot_table)

        # +12pt vertical padding below table
        elements.append(Spacer(1, 12))

        # Footer sentence
        elements.append(Paragraph(
            "This mandate was used as the sole basis for opportunity identification.",
            self.styles['BodyText']
        ))

        return elements

    # =========================================================================
    # Section 5: How Opportunities Were Identified
    # =========================================================================

    def _build_methodology(self, mandate: Mandate) -> list:
        """Build the methodology section with exact wording."""
        elements = []

        elements.append(Paragraph(
            "How Opportunities Were Identified",
            self.styles['SectionTitle']
        ))

        # Methodology Overview
        elements.append(Paragraph("<b>Methodology Overview</b>", self.styles['SubsectionTitle']))

        elements.append(Paragraph(
            "Opportunities were evaluated using Axis Allocation's internal deal engine, which "
            "assesses listings across multiple dimensions, including:",
            self.styles['BodyText']
        ))

        dimensions = [
            "Indicative pricing relative to estimated market value",
            "Asset fundamentals (size, configuration, tenure)",
            "Localised market dynamics",
            "Planning precedent indicators",
            "Feasibility constraints and risk factors",
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for dim in dimensions:
            elements.append(Paragraph(f"• {dim}", self.styles['BulletText']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(
            "Each opportunity was scored and reviewed independently.",
            self.styles['BodyText']
        ))

        # What This Process Is — and Is Not
        elements.append(Paragraph(
            "<b>What This Process Is — and Is Not</b>",
            self.styles['SubsectionTitle']
        ))

        # Checkmarks
        check_items = [
            "A structured filtering and prioritisation process",
            "Designed to surface asymmetric opportunities",
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for item in check_items:
            elements.append(Paragraph(f"✔ {item}", self.styles['BulletTextCheck']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        # Crosses
        cross_items = [
            "Not a guarantee of execution success",
            "Not a substitute for formal valuation or planning advice",
        ]

        for item in cross_items:
            elements.append(Paragraph(f"✖ {item}", self.styles['BulletTextCross']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        return elements

    # =========================================================================
    # Section 6: Opportunity Overview & Value Drivers
    # =========================================================================

    def _build_opportunity_overview(self, opp: OpportunityMemo, number: int) -> list:
        """Build opportunity overview page with exact wording."""
        elements = []

        # Title
        elements.append(Paragraph(
            f"Opportunity {number}",
            self.styles['OpportunityTitle']
        ))

        # Property Summary
        elements.append(Paragraph("<b>Property Summary</b>", self.styles['SubsectionTitle']))

        property_items = [
            ("Location", f"{opp.address}, {opp.area}"),
            ("Asking Price", f"£{opp.asking_price:,}"),
            ("Estimated Market Value", f"£{opp.estimated_value:,}"),
            ("Indicative BMV", f"{opp.bmv_percent:.1f}%"),
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for label, value in property_items:
            elements.append(Paragraph(f"• {label}: {value}", self.styles['BulletText']))

        # +10pt spacing below bullet list, +10pt between sub-sections
        elements.append(Spacer(1, 10))

        # Decision Snapshot
        elements.append(Paragraph("<b>Decision Snapshot</b>", self.styles['SubsectionTitle']))

        # Map recommendation to PURSUE/CONSIDER/WATCH
        rec_map = {
            "strong": "PURSUE",
            "moderate": "CONSIDER",
            "weak": "WATCH",
            "avoid": "WATCH",
        }
        recommendation_display = rec_map.get(opp.recommendation.lower(), "CONSIDER")

        # Map conviction to display format
        conviction_map = {
            ConvictionRating.HIGH: "High",
            ConvictionRating.MEDIUM: "Medium",
            ConvictionRating.LOW: "Exploratory",
        }
        conviction_display = conviction_map.get(opp.conviction, "Medium")

        # Key constraint from risks
        key_constraint = opp.key_risks[0] if opp.key_risks else "To be assessed"

        decision_items = [
            ("Recommendation", recommendation_display),
            ("Overall Score", f"{opp.scores.overall_score:.0f}/100"),
            ("Conviction Level", conviction_display),
            ("Key Constraint", key_constraint),
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for label, value in decision_items:
            elements.append(Paragraph(f"• {label}: {value}", self.styles['BulletText']))

        # +10pt spacing below bullet list, +10pt between sub-sections
        elements.append(Spacer(1, 10))

        # Value Creation Analysis
        elements.append(Paragraph("<b>Value Creation Analysis</b>", self.styles['SubsectionTitle']))

        # 1. Pricing Inefficiency
        elements.append(Paragraph("<b>1. Pricing Inefficiency</b>", self.styles['BodyTextCompact']))
        elements.append(Paragraph(
            "The property appears to be offered below estimated market value based on "
            "comparable evidence and internal valuation heuristics.",
            self.styles['BodyText']
        ))

        # 2. Planning-Led Upside (if applicable)
        if opp.planning and opp.planning.has_upside:
            # +10pt between sub-sections
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("<b>2. Planning-Led Upside (Indicative)</b>", self.styles['BodyTextCompact']))
            elements.append(Paragraph(
                "Subject to constraints, the asset may support additional value creation through:",
                self.styles['BodyText']
            ))

            # +8pt spacing above bullet list
            elements.append(Spacer(1, 8))

            # List planning positive factors as uplift opportunities
            for factor in opp.planning.positive_factors[:2]:
                elements.append(Paragraph(f"• {factor}", self.styles['BulletText']))

            # +10pt spacing below bullet list
            elements.append(Spacer(1, 10))

            uplift_range = f"{opp.planning.uplift_percent_low:.0f}% – {opp.planning.uplift_percent_high:.0f}%"
            elements.append(Paragraph(
                f"Indicative uplift range: {uplift_range}",
                self.styles['BodyTextCompact']
            ))
            elements.append(Paragraph(
                "(Not guaranteed; subject to professional advice and approval)",
                self.styles['SmallText']
            ))

            # Planning Context Summary - +10pt between sub-sections
            elements.append(Paragraph("<b>Planning Context Summary</b>", self.styles['SubsectionTitle']))

            # +8pt spacing above bullet list
            elements.append(Spacer(1, 8))

            elements.append(Paragraph(
                f"• Planning Score: {opp.planning.score}/100 – {opp.planning.label.title()}",
                self.styles['BulletText']
            ))

            if opp.planning.positive_factors:
                elements.append(Paragraph("• Key Positives:", self.styles['BulletText']))
                for factor in opp.planning.positive_factors[:2]:
                    elements.append(Paragraph(f"  • {factor}", self.styles['BulletText']))

            if opp.planning.negative_factors:
                elements.append(Paragraph("• Key Considerations:", self.styles['BulletText']))
                for factor in opp.planning.negative_factors[:2]:
                    elements.append(Paragraph(f"  • {factor}", self.styles['BulletText']))

            # +10pt spacing below bullet list
            elements.append(Spacer(1, 10))

        return elements

    # =========================================================================
    # Section 7: Comparative Opportunity Summary
    # =========================================================================

    def _build_comparative_table(self, mandate: Mandate) -> list:
        """Build the comparative summary table with exact wording."""
        elements = []

        elements.append(Paragraph("Comparative Opportunity Summary", self.styles['SectionTitle']))

        # Build comparison table with exact headers
        headers = ["Opportunity", "BMV %", "Planning Upside", "Score", "Recommendation"]
        rows = [headers]

        for i, opp in enumerate(mandate.opportunities, 1):
            # Planning upside display
            if opp.planning and opp.planning.has_upside:
                planning_val = f"{opp.planning.uplift_percent_low:.0f}–{opp.planning.uplift_percent_high:.0f}%"
            else:
                planning_val = "—"

            # Recommendation mapping
            rec_map = {
                "strong": "PURSUE",
                "moderate": "CONSIDER",
                "weak": "WATCH",
                "avoid": "WATCH",
            }
            rec_display = rec_map.get(opp.recommendation.lower(), "CONSIDER")

            rows.append([
                f"Opportunity {i}\n{opp.address[:20]}...",
                f"{opp.bmv_percent:.1f}%",
                planning_val,
                f"{opp.scores.overall_score:.0f}",
                rec_display,
            ])

        # +14pt vertical padding above table
        elements.append(Spacer(1, 14))

        col_widths = [55*mm, 25*mm, 35*mm, 25*mm, 34*mm]
        comp_table = Table(rows, colWidths=col_widths)
        comp_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('BACKGROUND', (0, 0), (-1, 0), Palette.CHARCOAL),
            ('TEXTCOLOR', (0, 0), (-1, 0), Palette.WHITE),
            ('TEXTCOLOR', (0, 1), (-1, -1), Palette.CHARCOAL),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, Palette.LIGHT_GRAY),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5*mm),  # Calm row height
            ('TOPPADDING', (0, 0), (-1, -1), 4.5*mm),     # Calm row height
            ('LEFTPADDING', (0, 0), (-1, -1), 2*mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2*mm),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5.5*mm),   # Header row taller
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [Palette.WHITE, Palette.PALE_GRAY]),
        ]))
        elements.append(comp_table)

        # +14pt vertical padding below table
        elements.append(Spacer(1, 14))

        # Footer sentence
        elements.append(Paragraph(
            "This comparison is intended to support prioritisation rather than selection.",
            self.styles['BodyText']
        ))

        return elements

    # =========================================================================
    # Section 8: Risks & Considerations
    # =========================================================================

    def _build_risks(self, mandate: Mandate) -> list:
        """Build the Risks & Considerations section with exact wording."""
        elements = []

        elements.append(Paragraph("Risks & Considerations", self.styles['SectionTitle']))

        # Exact bullet list as specified
        risks = [
            "Planning risk and approval uncertainty",
            "Cost overruns during development",
            "Market movement during execution period",
            "Liquidity and exit timing",
            "Regulatory or title-related constraints",
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for risk in risks:
            elements.append(Paragraph(f"• {risk}", self.styles['BulletText']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(
            "These risks should be independently assessed.",
            self.styles['BodyText']
        ))

        return elements

    # =========================================================================
    # Section 9: Suggested Next Steps
    # =========================================================================

    def _build_next_steps(self, mandate: Mandate) -> list:
        """Build the Next Steps section with exact wording."""
        elements = []

        elements.append(Paragraph("Suggested Next Steps", self.styles['SectionTitle']))

        elements.append(Paragraph(
            "Capital providers may wish to consider:",
            self.styles['BodyText']
        ))

        steps = [
            "Independent valuation and survey",
            "Planning feasibility review with a qualified advisor",
            "Legal and title due diligence",
            "Refinement of development assumptions",
        ]

        # +8pt spacing above bullet list
        elements.append(Spacer(1, 8))

        for i, step in enumerate(steps, 1):
            elements.append(Paragraph(f"{i}. {step}", self.styles['BulletText']))

        # +10pt spacing below bullet list
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(
            "Axis Allocation can assist with further sourcing or refinement if instructed.",
            self.styles['BodyText']
        ))

        return elements

    # =========================================================================
    # Section 10: Disclaimer & Contact
    # =========================================================================

    def _build_contact_disclaimer(self, mandate: Mandate) -> list:
        """Build the final contact and disclaimer page with exact wording."""
        elements = []

        elements.append(Paragraph("Disclaimer & Contact", self.styles['SectionTitle']))

        # Disclaimer section
        elements.append(Paragraph("<b>Disclaimer</b>", self.styles['SubsectionTitle']))

        elements.append(Paragraph(
            "This memorandum is provided for informational purposes only and does not constitute "
            "investment advice, a recommendation, or an offer.",
            self.styles['BodyText']
        ))

        elements.append(Paragraph(
            "All figures are indicative and subject to change.",
            self.styles['BodyText']
        ))

        elements.append(Spacer(1, 6*mm))

        # Contact section
        elements.append(Paragraph("<b>Contact</b>", self.styles['SubsectionTitle']))

        elements.append(Paragraph(
            "Axis Allocation",
            self.styles['BodyText']
        ))

        elements.append(Paragraph(
            "Enquiries: info@axisallocation.com",
            self.styles['BodyText']
        ))

        return elements


# =============================================================================
# Convenience Function
# =============================================================================

def generate_report(mandate: Mandate) -> ReportResult:
    """
    Generate a Capital Opportunity Memorandum PDF.

    This is the primary entry point for report generation.

    Applies eligibility gate:
    - Only includes opportunities with STRONG or MODERATE recommendation
    - Maximum 3 opportunities per PDF
    - Returns validation message if zero opportunities qualify

    Args:
        mandate: Complete mandate data including opportunities (raw, unfiltered)

    Returns:
        ReportSuccess: If PDF generated successfully (contains path and count)
        ReportNoQualifyingOpportunities: If no opportunities meet criteria

    Example:
        from reporting import generate_report
        from reporting.schemas import create_sample_mandate

        mandate = create_sample_mandate()
        result = generate_report(mandate)

        if isinstance(result, ReportSuccess):
            print(f"Report generated: {result.path}")
            print(f"Opportunities included: {result.opportunities_included}")
        else:
            print(result.message)
    """
    generator = ReportGenerator()
    return generator.generate_report(mandate)
