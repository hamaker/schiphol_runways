# Bas Scan - Runway Usage Scraper

## Overview
This project scrapes runway usage information from `bezoekbas.nl` to track which Schiphol runways are in use during specific time-slots.

## Research Findings
- **Source URL:** `https://bezoekbas.nl/home/actuele-informatie`
- **List API:** `https://bezoekbas.nl/wp-json/zmp_toolbox_blocks/v1/get_block_data/?id=22&block_id=e7458a8f-a5f3-4983-a790-eb6aed0e47c6&_page=1&_keyword=&_sort=date:DESC`
- **Detail API:** `https://bezoekbas.nl/wp-json/zmp_toolbox_blocks/v1/get_page_by_slug/?slug={slug}`
- **Data Structure:** 
    - List API returns posts with `post_name` (slug) and `post_date`.
    - Detail API returns `post_content` containing HTML with runway info (usually in `<li>` or `<p>` tags).

## Implementation Status
- [x] **Initial Research:** Identified API endpoints and data structure.
- [x] **Automated Scraper:** Implemented `bas_scraper.py` which:
    - Tracks seen posts and daily runway state via `runway_state.json`.
    - Merges multiple posts from the same day into a single daily entry.
    - De-duplicates time slots, ensuring newer updates override older information.
    - Regenerates `runway_usage.md` from the structured state.
    - Can be run regularly (via cron or manually).
- [x] **Data Validation:** Robust parsing of runway info from Gutenberg blocks HTML.

## Files
- `bas_scraper.py`: Main automated scraper script.
- `runway_usage.md`: Output file containing the formatted runway data.
- `seen_posts.json`: State file to avoid duplicate processing.
