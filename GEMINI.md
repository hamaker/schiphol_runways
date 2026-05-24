# Bas Scan - Runway Usage Tracker & Dashboard

## Overview
This project scrapes runway usage information from `bezoekbas.nl` and visualizes it in an interactive Streamlit dashboard. It tracks which Schiphol runways are in use for landing and takeoff during specific time-slots.

## Architecture
- **Scraper (`bas_scraper.py`):**
    - Fetches data from WordPress JSON APIs.
    - **Advanced Parsing:** Uses regex to extract structured data from natural language strings.
    - **Midnight Logic:** Automatically detects and splits time slots that cross midnight, correctly assigning them to the subsequent calendar day.
    - **Persistence:** Maintains state via `runway_state.json` (slug tracking) and stores structured records in a persistent SQLite database.
- **Database (`runway_data.db`):**
    - SQLite database containing the `runway_usage` table.
    - Primary key: `(date, start_time, end_time, operation, runway_name, direction)`.
    - Supports incremental updates where newer posts overwrite older data for the same slot.
- **Dashboard (`app.py`):**
    - **Framework:** Streamlit with dynamic routing via `st.navigation`.
    - **Routing:** Flat-path URLs (e.g., `/overview`, `/Buitenveldertbaan`).
    - **Visualizations:** Altair-based 24-hour horizontal timelines for runway activity.
    - **Persistence:** Client-side selection persistence using Browser Local Storage and URL Query Parameters.

## Implementation Status
- [x] **API Research:** Identified List and Detail API endpoints.
- [x] **Automated Scraper:** Robust script with incremental updates and multi-day slot handling.
- [x] **SQLite Integration:** Structured storage for historical usage analysis.
- [x] **Interactive Dashboard:** Modern web UI with filtering and timelines.
- [x] **Routing & Persistence:** Multi-page navigation and client-side state memory.

## Files
- `bas_scraper.py`: Main automated scraper script.
- `app.py`: Streamlit application entry point and logic.
- `runway_data.db`: SQLite database for structured usage logs.
- `runway_state.json`: Metadata tracking for API efficiency.
- `runway_usage.md`: Human-readable summary of usage (legacy output).
- `requirements.txt`: Python dependency list.
