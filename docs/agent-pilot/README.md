# Axis Allocation — Agent Pilot Onboarding Pack

Institutional-grade onboarding document for estate agents participating in the Axis Allocation pilot programme.

## Contents

| File | Purpose |
|------|---------|
| `agent-pilot-pack.pdf` | Print-ready PDF (A4, 3 pages) |
| `agent-pilot-pack.html` | Web version / source file |
| `agent-pilot-pack.css` | Stylesheet |
| `generate-pdf.py` | PDF regeneration script |

---

## Regenerating the PDF

### Option 1: Chrome CLI (Recommended)

```bash
cd docs/agent-pilot

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless \
  --disable-gpu \
  --print-to-pdf=agent-pilot-pack.pdf \
  --no-pdf-header-footer \
  "file://$(pwd)/agent-pilot-pack.html"
```

### Option 2: Browser Print

1. Open `agent-pilot-pack.html` in Chrome or Safari
2. Press `Cmd+P` (Mac) or `Ctrl+P` (Windows)
3. Select **Save as PDF**
4. Settings:
   - Paper size: **A4**
   - Margins: **None**
   - Enable: **Background graphics**
5. Save as `agent-pilot-pack.pdf`

### Option 3: Python Script

```bash
python generate-pdf.py
```

Requires Playwright or WeasyPrint with system dependencies.

---

## Hosting the Web Version

### Static Hosting

Upload `agent-pilot-pack.html` and `agent-pilot-pack.css` to any static host:

- Vercel
- Netlify
- GitHub Pages
- AWS S3 + CloudFront

Both files must be in the same directory.

### Local Preview

```bash
cd docs/agent-pilot
python -m http.server 8080
```

Then open: http://localhost:8080/agent-pilot-pack.html

### Integration with Axis Allocation Website

To embed in the main site, copy the files to:

```
web/static/docs/agent-pilot-pack.html
web/static/docs/agent-pilot-pack.css
```

Access at: `/static/docs/agent-pilot-pack.html`

---

## Design Notes

- **Palette**: Black (#1a1a1a), Charcoal (#2d2d2d), White
- **Typography**: Georgia (serif) for body, Helvetica Neue (sans) for headers
- **Format**: A4 portrait, 25mm outer margins
- **Print optimised**: Page breaks, background colours preserved

---

## Authorship

Produced by Jon McMahon
Director, Axis Allocation

---

*Confidential — Agent Pilot*
