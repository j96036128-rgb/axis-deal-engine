# Axis Deal Engine

Internal property deal evaluation engine for identifying below-market-value opportunities. Combines BMV scoring with planning potential assessment to surface high-value acquisition targets.

> **Note:** Scraping and live data integrations are intentionally excluded at this stage. The engine uses mock data for development and demonstration purposes.

## Status

**Development** — Mock scraper only. No external data sources connected.

## Requirements

- Python 3.11+
- pip or uv for dependency management

## Quick Start

### Web App (FastAPI)

```bash
# Clone and enter directory
cd axis-deal-engine

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Run the server
python run.py
```

Open http://127.0.0.1:8000 in your browser.

### Desktop App (Electron)

```bash
# From the repo root
cd desktop

# Install Node dependencies
npm install

# Run the desktop app
npm start
```

The Electron wrapper spawns the FastAPI backend automatically and displays the UI in a native window.

## Project Structure

```
axis-deal-engine/
├── core/               # Business logic
│   ├── models.py       # Data models (PropertyListing, SearchCriteria, etc.)
│   └── scoring.py      # BMV scoring algorithm
├── scraper/            # Data fetching
│   ├── base.py         # Abstract scraper interface
│   └── mock.py         # Mock data generator for development
├── web/                # Web interface
│   ├── app.py          # FastAPI application + planning assessment
│   ├── templates/      # Jinja2 HTML templates
│   └── static/         # CSS, JS assets
├── desktop/            # Electron desktop wrapper
│   ├── main.js         # Electron main process
│   └── package.json    # Node dependencies
├── utils/              # Utilities
│   ├── config.py       # Configuration management
│   └── formatting.py   # Display formatting helpers
├── data/               # Local data storage
├── run.py              # Entry point
└── pyproject.toml      # Project configuration
```

## Features

### Current
- Search by location, bedrooms, bathrooms, max price
- Target BMV percentage filtering
- Composite scoring algorithm:
  - BMV Score (40%): How far below market value
  - Urgency Score (25%): Days on market indicating seller motivation
  - Location Score (20%): Area desirability (placeholder)
  - Value Score (15%): Whether deal meets target criteria
- Deal recommendations: Strong / Moderate / Weak / Avoid
- Clean, responsive web UI

### Planned
- Real scraper integrations (Rightmove, Zoopla, OnTheMarket)
- Location scoring based on actual data
- Deal history and tracking
- Export to CSV/JSON
- API endpoints for programmatic access
- User authentication for SaaS deployment

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable debug mode |
| `SCRAPER_TYPE` | `mock` | Scraper to use |
| `DEFAULT_TARGET_BMV` | `15.0` | Default target BMV % |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Search form |
| `POST` | `/search` | Execute search |
| `GET` | `/api/health` | Health check |

## Scoring Methodology

### BMV Score (0-100)
- 20%+ below market: 80-100
- 10-20% below market: 50-80
- 5-10% below market: 25-50
- 0-5% below market: 0-25
- Overpriced: 0

### Urgency Score (0-100)
- 90+ days on market: 70-100 (motivated seller)
- 60-90 days: 40-70
- 30-60 days: 20-40
- <30 days: 0-20 (new listing)

### Recommendations
- **Strong**: Overall 70+ AND 10%+ BMV
- **Moderate**: Overall 50+ OR 15%+ BMV
- **Weak**: Overall 30+ OR 5%+ BMV
- **Avoid**: Below all thresholds

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run with auto-reload
DEBUG=true python run.py

# Run tests
pytest

# Lint
ruff check .
```

## License

Internal use only — Axis Allocation.
