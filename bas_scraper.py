import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta
import re
from html import unescape

# Configuration
BASE_LIST_URL = "https://bezoekbas.nl/wp-json/zmp_toolbox_blocks/v1/get_block_data/?id=22&block_id=e7458a8f-a5f3-4983-a790-eb6aed0e47c6&_page={page}&_keyword=&_sort=date:DESC"
BASE_DETAIL_URL = "https://bezoekbas.nl/wp-json/zmp_toolbox_blocks/v1/get_page_by_slug/?slug={slug}"
STATE_FILE = "runway_state.json"
OUTPUT_FILE = "runway_usage.md"
DB_FILE = "runway_data.db"

# Browser-like headers to avoid 403 errors
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bezoekbas.nl/home/actuele-informatie",
}

def init_db():
    """Initializes the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runway_usage'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE runway_usage (
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                operation TEXT,
                runway_name TEXT,
                direction TEXT,
                post_date TEXT,
                slug TEXT,
                PRIMARY KEY (date, start_time, end_time, operation, runway_name, direction)
            )
        ''')
    conn.commit()
    return conn

def clean_html(html):
    """Removes HTML tags and decodes entities."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = unescape(text)
    return ' '.join(text.split())

def extract_runway_info(html_content):
    """Parses runway usage lines from the post content."""
    items = re.findall(r'<li>(.*?)</li>', html_content, re.DOTALL)
    if not items:
        items = re.findall(r'<p>(.*?)</p>', html_content, re.DOTALL)
    
    refined_items = []
    for item in items:
        cleaned = clean_html(item)
        if any(keyword in cleaned.lower() for keyword in ['landen', 'starten', 'baan']):
            refined_items.append(cleaned)
    
    return refined_items

def parse_usage_line(current_date, slot_time, description):
    """Parses a description into structured records, handling midnight crossings."""
    time_match = re.search(r'(\d{2}:\d{2}) tot (\d{2}:\d{2})', slot_time)
    if not time_match:
        return [], current_date

    start_t, end_t = time_match.group(1), time_match.group(2)
    
    # Logic to detect if we've crossed into the next day
    # If end_time < start_time, it crosses midnight.
    # Also, if we previously crossed midnight, current_date has already been incremented.
    
    crosses_midnight = end_t < start_t
    
    # Split the slot if it crosses midnight
    slots_to_process = []
    if crosses_midnight:
        slots_to_process.append({'date': current_date, 'start': start_t, 'end': '23:59'})
        # Increment date for the second part and future lines
        try:
            dt = datetime.strptime(current_date, '%Y-%m-%d')
            next_day = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            current_date = next_day
            slots_to_process.append({'date': current_date, 'start': '00:00', 'end': end_t})
        except ValueError:
            pass
    else:
        slots_to_process.append({'date': current_date, 'start': start_t, 'end': end_t})

    parts = re.split(r'(?i)(landen|starten)', description)
    records = []
    current_op = None
    # Support Left (L), Right (R), and Center (C) runways
    runway_re = re.compile(r'([a-zA-Z\s]+)\s*\((\d+[LRC]?)\)')
    
    for i, part in enumerate(parts):
        if i % 2 != 0:
            current_op = 'Landing' if part.lower() == 'landen' else 'Takeoff'
            continue
            
        if current_op and part.strip():
            # Find all runways in this segment
            matches = runway_re.findall(part)
            for name, direction in matches:
                clean_name = re.sub(r'^(en|en/of|of)\s+', '', name.strip(), flags=re.IGNORECASE).strip()
                for slot in slots_to_process:
                    records.append({
                        'date': slot['date'],
                        'start_time': slot['start'],
                        'end_time': slot['end'],
                        'operation': current_op,
                        'runway_name': clean_name,
                        'direction': direction.strip()
                    })
    
    return records, current_date

def parse_slot(line):
    """Attempts to split a line into a time slot and description."""
    match = re.search(r'^(Van \d{2}:\d{2} tot \d{2}:\d{2}):?\s*(.*)', line, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)
    return None, line

def load_state():
    """Loads the processed data and seen slugs."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"seen_slugs": [], "days": {}}

def save_state(state):
    """Saves the processed data and seen slugs."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def write_markdown(state):
    """Generates the markdown file from the current state."""
    days = state.get("days", {})
    sorted_dates = sorted(days.keys(), reverse=True)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# Schiphol Runway Usage Tracker\n\n")
        f.write("Generated on: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n\n")
        
        for date_str in sorted_dates:
            day_data = days[date_str]
            f.write(f"## {day_data['title']}\n")
            f.write(f"**Date:** {date_str}\n\n")
            
            slots = day_data.get('slots', {})
            if slots:
                for slot_time in sorted(slots.keys()):
                    f.write(f"- {slot_time}: {slots[slot_time]}\n")
            else:
                f.write("*No structured runway info found.*\n")
            
            f.write("\n---\n\n")

def run_scraper(days_back=14):
    state = load_state()
    seen_slugs = set(state.get("seen_slugs", []))
    days = state.get("days", {})
    
    conn = init_db()
    cursor = conn.cursor()
    
    new_results = []
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    page = 1
    stop_searching = False
    
    print(f"Checking for new runway updates (since {cutoff_date.date()})...")
    
    while not stop_searching:
        url = BASE_LIST_URL.format(page=page)
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
            
        results = data.get('block', {}).get('result', {}).get('results', [])
        if not results:
            break
            
        for post_wrapper in results:
            post = post_wrapper.get('post', {})
            label = post_wrapper.get('post_type_label', '')
            if 'baangebruik' not in label.lower() and 'baangebruik' not in post.get('post_title', '').lower():
                continue

            slug = post.get('post_name')
            post_date_str = post.get('post_date')
            if not post_date_str: continue

            try:
                post_datetime = datetime.strptime(post_date_str, '%Y-%m-%d %H:%M:%S')
            except ValueError: continue
            
            if post_datetime < cutoff_date:
                stop_searching = True
                break
            
            # Restore API efficiency: Skip if already seen and in DB
            if slug in seen_slugs:
                cursor.execute("SELECT 1 FROM runway_usage WHERE slug = ? LIMIT 1", (slug,))
                if cursor.fetchone():
                    continue

            # Process post
            title = post.get('post_title')
            print(f"Processing: {post_date_str} - {title}")
            
            detail_url = BASE_DETAIL_URL.format(slug=f"/runway/{slug}/")
            try:
                detail_res = requests.get(detail_url, headers=HEADERS, timeout=10)
                detail_res.raise_for_status()
                detail_data = detail_res.json()
                content_html = detail_data.get('post', {}).get('post', {}).get('post_content', '')
                
                runway_info = extract_runway_info(content_html)
                
                # IMPORTANT: Initial date for the post is the calendar date of the post
                current_processing_date = post_datetime.strftime('%Y-%m-%d')
                
                for line in runway_info:
                    slot_time, description = parse_slot(line)
                    if slot_time:
                        # Update DB with midnight-crossing logic
                        db_records, next_date = parse_usage_line(current_processing_date, slot_time, description)
                        current_processing_date = next_date
                        
                        for rec in db_records:
                            cursor.execute('''
                                INSERT OR REPLACE INTO runway_usage 
                                (date, start_time, end_time, operation, runway_name, direction, post_date, slug)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (rec['date'], rec['start_time'], rec['end_time'], 
                                  rec['operation'], rec['runway_name'], rec['direction'], 
                                  post_date_str, slug))
                            
                            # Also update the JSON state for markdown (grouped by the ACTUAL date of the slot)
                            date_key = rec['date']
                            if date_key not in days:
                                days[date_key] = {"title": title, "slots": {}, "last_updated": post_date_str}
                            
                            # For the markdown, we still want the original slot_time string for display
                            # but we only update if it's a newer post for that day.
                            if post_date_str >= days[date_key].get('last_updated', ''):
                                days[date_key]['slots'][slot_time] = description
                                days[date_key]['last_updated'] = post_date_str
                                days[date_key]['title'] = title

                seen_slugs.add(slug)
            except Exception as e:
                print(f"Error fetching details for {slug}: {e}")
        
        page += 1
        if page > 5: break

    conn.commit()
    conn.close()
    
    state["seen_slugs"] = list(seen_slugs)
    state["days"] = days
    write_markdown(state)
    save_state(state)
    print(f"Regenerated database and {OUTPUT_FILE} with midnight-crossing logic.")

if __name__ == "__main__":
    run_scraper(days_back=14)
