"""
Reporting module for Axis Deal Engine.

Generates professional Capital Opportunity Memorandum PDFs
from mandate and deal analysis data.

Usage:
    from reporting import generate_report
    from reporting.schemas import create_sample_mandate

    mandate = create_sample_mandate()
    filepath = generate_report(mandate)
"""

from .pdf_generator import ReportGenerator, generate_report
from .schemas import (
    Mandate,
    MandateParameters,
    OpportunityMemo,
    ScoreBreakdown,
    PlanningContext,
    UpliftScenario,
    ConvictionRating,
    PriorityLevel,
    create_sample_mandate,
)

__all__ = [
    # Generator
    "ReportGenerator",
    "generate_report",
    # Schemas
    "Mandate",
    "MandateParameters",
    "OpportunityMemo",
    "ScoreBreakdown",
    "PlanningContext",
    "UpliftScenario",
    "ConvictionRating",
    "PriorityLevel",
    "create_sample_mandate",
]
