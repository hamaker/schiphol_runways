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

def get_slot_date(post_datetime, time_str):
    """Returns the date string (YYYY-MM-DD) for a given HH:MM time, assuming it's near post_datetime."""
    time_obj = datetime.strptime(time_str, '%H:%M').time()
    best_candidate = None
    best_diff = float('inf')
    
    # We want to find the date where this time is closest to post_datetime + 6 hours.
    # This means a slot 6 hours in the future is considered the "ideal" center of our expected range.
    target_datetime = post_datetime + timedelta(hours=6)
    
    for days_offset in [-1, 0, 1, 2]:
        candidate_date = post_datetime.date() + timedelta(days=days_offset)
        candidate_dt = datetime.combine(candidate_date, time_obj)
        diff = abs((candidate_dt - target_datetime).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_candidate = candidate_dt
            
    return best_candidate.strftime('%Y-%m-%d')

def parse_usage_line(post_datetime, slot_time, description):
    """Parses a description into structured records, handling midnight crossings."""
    time_match = re.search(r'(\d{2}:\d{2}) tot (\d{2}:\d{2})', slot_time)
    if not time_match:
        return []

    start_t, end_t = time_match.group(1), time_match.group(2)
    start_date = get_slot_date(post_datetime, start_t)
    end_date = get_slot_date(post_datetime, end_t)
    
    slots_to_process = []
    if start_date != end_date:
        slots_to_process.append({'date': start_date, 'start': start_t, 'end': '23:59'})
        slots_to_process.append({'date': end_date, 'start': '00:00', 'end': end_t})
    else:
        slots_to_process.append({'date': start_date, 'start': start_t, 'end': end_t})

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
    
    return records

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
    
    posts_to_process = []
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
            post_modified_str = post.get('post_modified', post_date_str)
            if not post_date_str: continue

            try:
                post_datetime = datetime.strptime(post_date_str, '%Y-%m-%d %H:%M:%S')
            except ValueError: continue
            
            if post_datetime < cutoff_date:
                stop_searching = True
                break
            
            # API efficiency: Skip if already seen AND it is older than 2 days
            # We always re-process recent posts to catch same-slug updates.
            if slug in seen_slugs and post_datetime < (datetime.now() - timedelta(days=2)):
                cursor.execute("SELECT 1 FROM runway_usage WHERE slug = ? LIMIT 1", (slug,))
                if cursor.fetchone():
                    continue

            posts_to_process.append({
                'slug': slug,
                'post_date_str': post_date_str,
                'post_modified_str': post_modified_str,
                'post_datetime': post_datetime,
                'title': post.get('post_title')
            })
        
        page += 1
        if page > 5: break

    # Process from oldest to newest so newer posts overwrite older ones
    posts_to_process.reverse()

    for item in posts_to_process:
        slug = item['slug']
        post_date_str = item['post_date_str']
        post_modified_str = item['post_modified_str']
        post_datetime = item['post_datetime']
        title = item['title']
        
        print(f"Processing: {post_date_str} - {title}")
        
        detail_url = BASE_DETAIL_URL.format(slug=f"/runway/{slug}/")
        try:
            detail_res = requests.get(detail_url, headers=HEADERS, timeout=10)
            detail_res.raise_for_status()
            detail_data = detail_res.json()
            content_html = detail_data.get('post', {}).get('post', {}).get('post_content', '')
            
            runway_info = extract_runway_info(content_html)
            
            # Smart Overwrite: If we re-process a slug, or if another post has data for the same slot,
            # we delete the "inferior" data. 
            # 1. Delete all existing records for THIS slug before re-inserting (handles updates to the same post)
            cursor.execute('DELETE FROM runway_usage WHERE slug = ?', (slug,))

            for line in runway_info:
                slot_time, description = parse_slot(line)
                if slot_time:
                    # Update DB using heuristic date logic
                    db_records = parse_usage_line(post_datetime, slot_time, description)
                    
                    for rec in db_records:
                        # 2. Delete existing records from OTHER posts for this specific timeslot and operation
                        # if they are older than the current post's MODIFIED date.
                        cursor.execute('''
                            DELETE FROM runway_usage 
                            WHERE date = ? AND start_time = ? AND end_time = ? AND operation = ?
                            AND post_date < ?
                        ''', (rec['date'], rec['start_time'], rec['end_time'], rec['operation'], post_modified_str))

                        cursor.execute('''
                            INSERT OR REPLACE INTO runway_usage 
                            (date, start_time, end_time, operation, runway_name, direction, post_date, slug)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (rec['date'], rec['start_time'], rec['end_time'], 
                              rec['operation'], rec['runway_name'], rec['direction'], 
                              post_modified_str, slug))
                        
                        # Also update the JSON state for markdown
                        date_key = rec['date']
                        if date_key not in days:
                            days[date_key] = {"title": title, "slots": {}, "last_updated": post_modified_str}
                        
                        if post_modified_str >= days[date_key].get('last_updated', ''):
                            days[date_key]['slots'][slot_time] = description
                            days[date_key]['last_updated'] = post_modified_str
                            days[date_key]['title'] = title

            seen_slugs.add(slug)
        except Exception as e:
            print(f"Error fetching details for {slug}: {e}")

    conn.commit()
    conn.close()
    
    state["seen_slugs"] = list(seen_slugs)
    state["days"] = days
    write_markdown(state)
    save_state(state)
    print(f"Regenerated database and {OUTPUT_FILE} with midnight-crossing logic.")

if __name__ == "__main__":
    run_scraper(days_back=14)
