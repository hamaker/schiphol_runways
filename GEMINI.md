# Bas Scan - Runway Usage Tracker & Dashboard

## Overview
This project scrapes runway usage information from `bezoekbas.nl` and visualizes it in an interactive, localized Streamlit dashboard. It tracks Schiphol runways used for landing and takeoff during specific time-slots.

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

### 3. Dashboard (`app.py`)
- **Framework:** Streamlit with a 10-minute cache TTL for real-time data freshness.
- **Localization:** Full Dutch UI ("Landen", "Starten", "Overzicht", etc.), while maintaining English code comments.
- **Routing:** Dynamic flat-path URLs (e.g., `/Buitenveldertbaan`) using `st.navigation`.
- **Visuals:**
    - **Altair Timelines:** 24-hour horizontal bars showing usage blocks.
    - **Consolidated View:** Adjacent slots with identical usage are merged for readability.
    - **Continuous History:** Shows all dates in a range, explicitly marking dates with no activity.
    - **Aesthetics:** Compact markdown display without bullet points for a modern schedule look.
- **Persistence:** Remembers the last viewed runway using Browser Local Storage and URL sync.
- **Analytics:** Integrated GoatCounter tracking.

## Implementation Status
- [x] **Core Scraper:** Multi-runway, center-runway, and midnight-crossing logic.
- [x] **Data Persistence:** SQLite with incremental update support.
- [x] **Web Dashboard:** Interactive filters, dynamic routing, and persistent state.
- [x] **Localization:** fully Dutch user experience.
- [x] **Analytics & Freshness:** GoatCounter and "Last Updated" indicators.

## Files
- `bas_scraper.py`: Automated incremental scraper.
- `app.py`: Multi-page Streamlit dashboard.
- `runway_data.db`: SQLite database.
- `runway_state.json`: Metadata for API efficiency.
- `requirements.txt`: Project dependencies.
