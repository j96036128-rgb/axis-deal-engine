#!/usr/bin/env python3
"""
CLI for generating Capital Opportunity Memorandum PDFs.

Usage:
    python -m reporting.cli sample
    python -m reporting.cli generate <mandate_json>

Examples:
    # Generate sample report for testing
    python -m reporting.cli sample

    # Generate from JSON mandate file
    python -m reporting.cli generate mandates/client_mandate.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

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


def parse_mandate_from_json(data: dict) -> Mandate:
    """
    Parse a JSON dictionary into a Mandate object.

    Args:
        data: Dictionary containing mandate data

    Returns:
        Mandate object ready for report generation
    """
    # Parse parameters
    params_data = data.get("parameters", {})
    parameters = MandateParameters(
        location=params_data.get("location", ""),
        min_beds=params_data.get("min_beds", 1),
        max_beds=params_data.get("max_beds"),
        min_baths=params_data.get("min_baths", 1),
        min_price=params_data.get("min_price"),
        max_price=params_data.get("max_price"),
        target_bmv_percent=params_data.get("target_bmv_percent", 15.0),
        strategy=params_data.get("strategy", "BMV + Planning"),
        property_types=params_data.get("property_types", []),
        additional_filters=params_data.get("additional_filters", []),
    )

    # Parse opportunities
    opportunities = []
    for opp_data in data.get("opportunities", []):
        # Parse scores
        scores_data = opp_data.get("scores", {})
        scores = ScoreBreakdown(
            bmv_score=scores_data.get("bmv_score", 0),
            urgency_score=scores_data.get("urgency_score", 0),
            location_score=scores_data.get("location_score", 50),
            value_score=scores_data.get("value_score", 0),
            overall_score=scores_data.get("overall_score", 0),
        )

        # Parse planning context if present
        planning = None
        if opp_data.get("planning"):
            p = opp_data["planning"]
            planning = PlanningContext(
                score=p.get("score", 0),
                label=p.get("label", "low"),
                uplift_percent_low=p.get("uplift_percent_low", 0),
                uplift_percent_high=p.get("uplift_percent_high", 0),
                positive_factors=p.get("positive_factors", []),
                negative_factors=p.get("negative_factors", []),
                rationale=p.get("rationale", ""),
            )

        # Parse uplift scenarios if present
        uplift = None
        if opp_data.get("uplift_scenarios"):
            u = opp_data["uplift_scenarios"]
            uplift = UpliftScenario(
                conservative_percent=u.get("conservative_percent", 0),
                conservative_value=u.get("conservative_value", 0),
                base_percent=u.get("base_percent", 0),
                base_value=u.get("base_value", 0),
                upside_percent=u.get("upside_percent", 0),
                upside_value=u.get("upside_value", 0),
            )

        # Parse enums
        conviction_str = opp_data.get("conviction", "medium").lower()
        conviction = ConvictionRating(conviction_str)

        priority_str = opp_data.get("priority", "secondary").lower()
        priority = PriorityLevel(priority_str)

        opp = OpportunityMemo(
            opportunity_id=opp_data.get("opportunity_id", ""),
            address=opp_data.get("address", ""),
            area=opp_data.get("area", ""),
            city=opp_data.get("city", ""),
            postcode=opp_data.get("postcode", ""),
            property_type=opp_data.get("property_type", ""),
            asking_price=opp_data.get("asking_price", 0),
            estimated_value=opp_data.get("estimated_value", 0),
            bmv_percent=opp_data.get("bmv_percent", 0),
            potential_profit=opp_data.get("potential_profit", 0),
            roi_percent=opp_data.get("roi_percent", 0),
            bedrooms=opp_data.get("bedrooms", 0),
            bathrooms=opp_data.get("bathrooms", 0),
            days_on_market=opp_data.get("days_on_market", 0),
            scores=scores,
            recommendation=opp_data.get("recommendation", ""),
            conviction=conviction,
            priority=priority,
            investment_thesis=opp_data.get("investment_thesis", ""),
            pricing_insight=opp_data.get("pricing_insight", ""),
            key_risks=opp_data.get("key_risks", []),
            key_strengths=opp_data.get("key_strengths", []),
            notes=opp_data.get("notes", []),
            planning=planning,
            uplift_scenarios=uplift,
        )
        opportunities.append(opp)

    return Mandate(
        reference_id=data.get("reference_id", ""),
        client_name=data.get("client_name", ""),
        client_entity=data.get("client_entity"),
        report_date=data.get("report_date", ""),
        generated_at=data.get("generated_at", datetime.now().isoformat()),
        parameters=parameters,
        total_properties_screened=data.get("total_properties_screened", 0),
        opportunities_identified=data.get("opportunities_identified", 0),
        average_bmv_percent=data.get("average_bmv_percent", 0),
        total_potential_value=data.get("total_potential_value", 0),
        capital_range_low=data.get("capital_range_low", 0),
        capital_range_high=data.get("capital_range_high", 0),
        executive_summary=data.get("executive_summary", ""),
        opportunities=opportunities,
        disclaimer_version=data.get("disclaimer_version", "1.0"),
        report_version=data.get("report_version", "1.0"),
    )


def cmd_sample(args):
    """Generate a sample Capital Opportunity Memorandum for testing."""
    print("Generating sample Capital Opportunity Memorandum...")

    mandate = create_sample_mandate()
    filepath = generate_report(mandate)

    print(f"Report generated: {filepath}")
    return 0


def cmd_generate(args):
    """Generate a report from a JSON mandate file."""
    input_path = Path(args.mandate_file)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Loading mandate from: {input_path}")

    try:
        with open(input_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1

    try:
        mandate = parse_mandate_from_json(data)
    except (KeyError, ValueError) as e:
        print(f"Error: Invalid mandate data: {e}", file=sys.stderr)
        return 1

    print(f"Generating report for: {mandate.client_name}")
    filepath = generate_report(mandate)

    print(f"Report generated: {filepath}")
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Axis Allocation - Capital Opportunity Memorandum Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m reporting.cli sample
    python -m reporting.cli generate mandates/client_mandate.json

Output:
    Reports are saved to: reports/AXA-<reference_id>.pdf
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sample command
    sample_parser = subparsers.add_parser(
        "sample",
        help="Generate a sample report with mock data",
    )
    sample_parser.set_defaults(func=cmd_sample)

    # Generate command
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate a report from a JSON mandate file",
    )
    gen_parser.add_argument(
        "mandate_file",
        help="Path to JSON mandate file",
    )
    gen_parser.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
