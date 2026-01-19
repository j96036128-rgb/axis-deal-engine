"""
Axis Allocation - Agent Property Submission Guide PDF Generator

Generates a professional, agent-facing PDF guide explaining the submission process.
Designed for institutional/professional vendors.

Output: 2-3 page PDF with clean, print-ready design.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Final

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# =============================================================================
# Constants
# =============================================================================

GENERATOR_VERSION: Final[str] = "1.0"
OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "guides"


# =============================================================================
# Color Palette - Professional, print-friendly
# =============================================================================


class GuidePalette:
    """Professional color palette matching Axis Allocation branding."""

    BLACK = colors.Color(0.1, 0.1, 0.1)
    CHARCOAL = colors.Color(0.2, 0.2, 0.22)
    SLATE = colors.Color(0.35, 0.38, 0.42)
    GRAY = colors.Color(0.5, 0.5, 0.5)
    LIGHT_GRAY = colors.Color(0.85, 0.85, 0.85)
    PALE_GRAY = colors.Color(0.95, 0.95, 0.95)
    WHITE = colors.white
    ACCENT = colors.Color(0.15, 0.25, 0.4)  # Navy blue


# =============================================================================
# Typography
# =============================================================================


def get_guide_styles() -> dict[str, ParagraphStyle]:
    """Get typography styles for the guide."""
    return {
        "title": ParagraphStyle(
            "Title",
            fontName="Helvetica-Bold",
            fontSize=28,
            textColor=GuidePalette.CHARCOAL,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
            leading=34,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            fontName="Helvetica",
            fontSize=14,
            textColor=GuidePalette.SLATE,
            alignment=TA_CENTER,
            spaceAfter=20 * mm,
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=GuidePalette.CHARCOAL,
            spaceBefore=12 * mm,
            spaceAfter=6 * mm,
        ),
        "subsection": ParagraphStyle(
            "Subsection",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=GuidePalette.SLATE,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=11,
            textColor=GuidePalette.CHARCOAL,
            alignment=TA_JUSTIFY,
            spaceAfter=4 * mm,
            leading=16,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            fontName="Helvetica",
            fontSize=11,
            textColor=GuidePalette.CHARCOAL,
            leftIndent=8 * mm,
            spaceAfter=2 * mm,
            leading=15,
            bulletIndent=3 * mm,
        ),
        "footer": ParagraphStyle(
            "Footer",
            fontName="Helvetica",
            fontSize=9,
            textColor=GuidePalette.GRAY,
            alignment=TA_CENTER,
        ),
        "contact": ParagraphStyle(
            "Contact",
            fontName="Helvetica",
            fontSize=10,
            textColor=GuidePalette.SLATE,
            alignment=TA_CENTER,
            spaceBefore=8 * mm,
        ),
    }


# =============================================================================
# Content
# =============================================================================

INTRO_TEXT = """
Axis Allocation is a property acquisitions advisory focused on identifying
below-market-value opportunities for institutional and private investors.
We apply rigorous, evidence-based analysis to every property we evaluate.
"""

WHY_TEXT = """
This submission portal enables estate agents and property professionals to
present opportunities directly to our acquisitions team. We review every
submission against verifiable market data and comparable sales evidence
before presenting qualified opportunities to our buyer network.
"""

WHAT_YOU_GAIN_TEXT = """
Submitting through this portal gives your property access to serious,
qualified buyers with available capital. Our process is designed to be
efficient and transparent, with clear communication at every stage.
"""

PROCESS_STEPS = [
    ("Invite-Only Access", "Each submission link is unique to you and tracks your submissions securely."),
    ("Facts-First Submission", "We collect verified property details including title documents, EPC, and floor plans."),
    ("Digital Property Logbook", "Your submission creates a permanent, auditable record of the property's facts."),
    ("Independent Evaluation", "Our Deal Engine analyses the property against comparable sales data."),
    ("Confidential Presentation", "Qualified opportunities are presented to pre-approved buyers under NDA."),
]

REQUIRED_INFO = [
    "Full property address and postcode",
    "Property type (house, flat, etc.) and tenure",
    "Floor area in square metres",
    "Guide price and sale route (auction, private treaty, off-market)",
    "Your contact details",
]

REQUIRED_DOCS = [
    "Title Register (from Land Registry)",
    "Energy Performance Certificate (EPC)",
    "Floor Plan",
    "Lease document (if leasehold)",
]

TIME_EXPECTATIONS = [
    "Submission: 10-15 minutes if documents are ready",
    "Initial review: Within 48 hours",
    "Evaluation outcome: Within 5 working days",
]


# =============================================================================
# PDF Generator
# =============================================================================


class AgentGuideGenerator:
    """Generates the Agent Submission Guide PDF."""

    def __init__(self):
        self.styles = get_guide_styles()
        self.OUTPUT_DIR = OUTPUT_DIR

    def _add_header(self, canvas_obj: canvas.Canvas, doc) -> None:
        """Add page header."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.setFillColor(GuidePalette.GRAY)
        canvas_obj.drawString(20 * mm, A4[1] - 15 * mm, "Axis Allocation")
        canvas_obj.drawRightString(A4[0] - 20 * mm, A4[1] - 15 * mm, "Property Submission Guide")
        canvas_obj.restoreState()

    def _add_footer(self, canvas_obj: canvas.Canvas, doc) -> None:
        """Add page footer with page number."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.setFillColor(GuidePalette.GRAY)
        canvas_obj.drawCentredString(
            A4[0] / 2,
            15 * mm,
            f"Page {doc.page}"
        )
        canvas_obj.restoreState()

    def _on_page(self, canvas_obj: canvas.Canvas, doc) -> None:
        """Called for each page."""
        self._add_header(canvas_obj, doc)
        self._add_footer(canvas_obj, doc)

    def _on_first_page(self, canvas_obj: canvas.Canvas, doc) -> None:
        """Called for first page (no header on cover)."""
        self._add_footer(canvas_obj, doc)

    def _build_cover_page(self) -> list:
        """Build cover page elements."""
        elements = []

        # Spacer to push content down
        elements.append(Spacer(1, 40 * mm))

        # Title
        elements.append(Paragraph(
            "Axis Allocation",
            self.styles["title"]
        ))

        # Subtitle
        elements.append(Paragraph(
            "Property Submission Guide",
            self.styles["subtitle"]
        ))

        # Divider line
        elements.append(Spacer(1, 10 * mm))

        # Introduction section
        elements.append(Paragraph(
            "About Axis Allocation",
            self.styles["section_heading"]
        ))
        elements.append(Paragraph(INTRO_TEXT.strip(), self.styles["body"]))

        elements.append(Paragraph(
            "Why This Process Exists",
            self.styles["subsection"]
        ))
        elements.append(Paragraph(WHY_TEXT.strip(), self.styles["body"]))

        elements.append(Paragraph(
            "What You Gain",
            self.styles["subsection"]
        ))
        elements.append(Paragraph(WHAT_YOU_GAIN_TEXT.strip(), self.styles["body"]))

        elements.append(PageBreak())
        return elements

    def _build_process_page(self) -> list:
        """Build the 'How Submission Works' page."""
        elements = []

        elements.append(Paragraph(
            "How Submission Works",
            self.styles["section_heading"]
        ))

        # Process steps table
        table_data = []
        for i, (step_title, step_desc) in enumerate(PROCESS_STEPS, 1):
            table_data.append([
                Paragraph(f"<b>{i}.</b>", self.styles["body"]),
                Paragraph(f"<b>{step_title}</b><br/>{step_desc}", self.styles["body"]),
            ])

        table = Table(table_data, colWidths=[12 * mm, 150 * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ]))
        elements.append(table)

        elements.append(Spacer(1, 8 * mm))

        # Key points
        elements.append(Paragraph(
            "Key Points",
            self.styles["subsection"]
        ))

        key_points = [
            "Your submission creates a permanent, tamper-evident record",
            "All data is treated as confidential",
            "Evaluation is based solely on verified facts and market evidence",
            "You will be notified of the outcome within 5 working days",
        ]

        for point in key_points:
            elements.append(Paragraph(
                f"\u2022  {point}",
                self.styles["bullet"]
            ))

        elements.append(PageBreak())
        return elements

    def _build_preparation_page(self) -> list:
        """Build the 'What to Prepare' page."""
        elements = []

        elements.append(Paragraph(
            "What to Prepare Before You Start",
            self.styles["section_heading"]
        ))

        # Required Information
        elements.append(Paragraph(
            "Required Information",
            self.styles["subsection"]
        ))

        for item in REQUIRED_INFO:
            elements.append(Paragraph(
                f"\u2022  {item}",
                self.styles["bullet"]
            ))

        elements.append(Spacer(1, 6 * mm))

        # Required Documents
        elements.append(Paragraph(
            "Required Documents",
            self.styles["subsection"]
        ))

        for item in REQUIRED_DOCS:
            elements.append(Paragraph(
                f"\u2022  {item}",
                self.styles["bullet"]
            ))

        elements.append(Spacer(1, 6 * mm))

        # Time expectations
        elements.append(Paragraph(
            "Time Expectations",
            self.styles["subsection"]
        ))

        for item in TIME_EXPECTATIONS:
            elements.append(Paragraph(
                f"\u2022  {item}",
                self.styles["bullet"]
            ))

        elements.append(Spacer(1, 12 * mm))

        # Support contact
        elements.append(Paragraph(
            "Questions or Issues?",
            self.styles["subsection"]
        ))

        elements.append(Paragraph(
            "If you have any questions about the submission process or encounter any issues, "
            "please contact us. We are here to help.",
            self.styles["body"]
        ))

        elements.append(Paragraph(
            "<b>info@axisallocation.com</b>",
            self.styles["contact"]
        ))

        return elements

    def generate(self) -> Path:
        """Generate the Agent Submission Guide PDF."""
        # Ensure output directory exists
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = self.OUTPUT_DIR / "Axis_Allocation_Property_Submission_Guide.pdf"

        # Create PDF document
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=25 * mm,
            bottomMargin=25 * mm,
        )

        # Build content
        elements = []
        elements.extend(self._build_cover_page())
        elements.extend(self._build_process_page())
        elements.extend(self._build_preparation_page())

        # Build PDF
        doc.build(
            elements,
            onFirstPage=self._on_first_page,
            onLaterPages=self._on_page,
        )

        # Write to file
        output_path.write_bytes(buffer.getvalue())

        return output_path


def generate_agent_guide() -> Path:
    """Generate the Agent Submission Guide PDF."""
    generator = AgentGuideGenerator()
    return generator.generate()


if __name__ == "__main__":
    path = generate_agent_guide()
    print(f"Generated: {path}")
