# Bas Scan - Runway Usage Tracker & Dashboard

## Overview
This project scrapes runway usage information from `bezoekbas.nl` and visualizes it in interactive dashboards. It tracks Schiphol runways used for landing and takeoff during specific time-slots.

Two dashboard implementations are available:
1. **Streamlit (`app.py`):** Original rapid-prototype dashboard.
2. **Flask (`webapp.py`):** Standard web application with custom Tailwind CSS styling and enhanced control.

## Architecture

### 1. Scraper (`bas_scraper.py`)
- **API Integration:** Fetches from WordPress JSON APIs (List & Detail).
- **Advanced Parsing:**
    - Uses regex to extract structured data from natural language strings.
    - **Multi-Runway Support:** Correctly identifies multiple runways per operation (e.g., "starten X en Y").
    - **Directional Support:** Handles `L` (Left), `R` (Right), and `C` (Center) runways.
- **Midnight Logic:** Detects time slots crossing midnight (e.g., 22:10 - 07:00), splitting them and assigning subsequent slots to the next calendar day.
- **Efficiency:** Tracks processed posts via `runway_state.json` and skips previously processed slugs already present in the database.

### 2. Database (`runway_data.db`)
- **SQLite Storage:** Persistent storage for historical usage analysis.
- **Data Integrity:** Primary key `(date, start_time, end_time, operation, runway_name, direction)`.
- **Smart Updates:** Newer posts (based on publication timestamp) automatically overwrite older data for the same timeslot.

### 3. Dashboards
- **Streamlit (`app.py`):** 
    - Dutch UI, dynamic flat-path URLs.
    - Altair timelines with merged slots.
- **Flask (`webapp.py`):**
    - Jinja2 templates with Tailwind CSS.
    - Vega-Lite for rendering Altair charts in the browser.
    - DataTables for interactive details view.
    - 2-minute server-side caching via Flask-Caching.

## Implementation Status
- [x] **Core Scraper:** Multi-runway, center-runway, and midnight-crossing logic.
- [x] **Data Persistence:** SQLite with incremental update support.
- [x] **Streamlit Dashboard:** Interactive filters, dynamic routing, and persistent state.
- [x] **Flask Dashboard:** Tailwind CSS clone with Vega-Lite and DataTables.
- [x] **Localization:** fully Dutch user experience.
- [x] **Analytics & Freshness:** GoatCounter and "Last Updated" indicators.

## Files
- `bas_scraper.py`: Automated incremental scraper.
- `app.py`: Streamlit dashboard.
- `webapp.py`: Flask dashboard.
- `templates/`: Jinja2 templates for the Flask dashboard.
- `runway_data.db`: SQLite database.
- `runway_state.json`: Metadata for API efficiency.
- `requirements.txt`: Project dependencies.
