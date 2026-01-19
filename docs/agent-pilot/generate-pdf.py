#!/usr/bin/env python3
"""
Generate PDF from Agent Pilot Onboarding Pack HTML.

This script provides multiple methods for PDF generation:
1. WeasyPrint (requires pango/cairo libraries)
2. Playwright (headless Chrome)
3. Manual instructions for browser-based generation

Usage:
    python generate-pdf.py

Or use browser:
    1. Open agent-pilot-pack.html in Chrome/Safari
    2. Press Cmd+P (Mac) or Ctrl+P (Windows)
    3. Select "Save as PDF"
    4. Set margins to "None" or "Minimum"
    5. Enable "Background graphics"
"""

import subprocess
import sys
from pathlib import Path

HTML_FILE = Path(__file__).parent / "agent-pilot-pack.html"
PDF_FILE = Path(__file__).parent / "agent-pilot-pack.pdf"


def try_weasyprint():
    """Attempt PDF generation with WeasyPrint."""
    try:
        from weasyprint import HTML
        print("Generating PDF with WeasyPrint...")
        HTML(filename=str(HTML_FILE)).write_pdf(str(PDF_FILE))
        print(f"PDF generated: {PDF_FILE}")
        return True
    except ImportError:
        print("WeasyPrint not available.")
        return False
    except Exception as e:
        print(f"WeasyPrint error: {e}")
        return False


def try_playwright():
    """Attempt PDF generation with Playwright (headless Chrome)."""
    try:
        from playwright.sync_api import sync_playwright
        print("Generating PDF with Playwright...")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{HTML_FILE.absolute()}")
            page.pdf(
                path=str(PDF_FILE),
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
            )
            browser.close()
        print(f"PDF generated: {PDF_FILE}")
        return True
    except ImportError:
        print("Playwright not available. Install with: pip install playwright && playwright install chromium")
        return False
    except Exception as e:
        print(f"Playwright error: {e}")
        return False


def try_chrome_cli():
    """Attempt PDF generation with Chrome CLI."""
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]

    chrome_path = None
    for path in chrome_paths:
        if Path(path).exists():
            chrome_path = path
            break

    if not chrome_path:
        print("Chrome/Chromium not found in standard locations.")
        return False

    print(f"Generating PDF with Chrome CLI ({chrome_path})...")
    try:
        subprocess.run([
            chrome_path,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={PDF_FILE}",
            "--no-margins",
            f"file://{HTML_FILE.absolute()}"
        ], check=True, capture_output=True)
        print(f"PDF generated: {PDF_FILE}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Chrome CLI error: {e}")
        return False


def print_manual_instructions():
    """Print manual PDF generation instructions."""
    print("""
================================================================================
MANUAL PDF GENERATION
================================================================================

Since automated PDF generation requires additional dependencies, please generate
the PDF manually using your browser:

1. Open the HTML file in your browser:
   file://{html_path}

2. Print to PDF:
   - Chrome/Edge: Cmd+P (Mac) or Ctrl+P (Windows)
   - Select destination: "Save as PDF"
   - Layout: Portrait
   - Paper size: A4
   - Margins: None (or Minimum)
   - IMPORTANT: Enable "Background graphics" checkbox
   - Click "Save"

3. Save as:
   {pdf_path}

================================================================================
""".format(
        html_path=HTML_FILE.absolute(),
        pdf_path=PDF_FILE.absolute()
    ))


def main():
    print("=" * 60)
    print("Axis Allocation — Agent Pilot Pack PDF Generator")
    print("=" * 60)
    print()

    # Try each method in order of preference
    if try_playwright():
        return 0

    print()
    if try_weasyprint():
        return 0

    print()
    if try_chrome_cli():
        return 0

    print()
    print_manual_instructions()
    return 1


if __name__ == "__main__":
    sys.exit(main())
