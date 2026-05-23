import requests
import json
import os
from datetime import datetime, timedelta
import re
from html import unescape

# Configuration
BASE_LIST_URL = "https://bezoekbas.nl/wp-json/zmp_toolbox_blocks/v1/get_block_data/?id=22&block_id=e7458a8f-a5f3-4983-a790-eb6aed0e47c6&_page={page}&_keyword=&_sort=date:DESC"
BASE_DETAIL_URL = "https://bezoekbas.nl/wp-json/zmp_toolbox_blocks/v1/get_page_by_slug/?slug={slug}"
STATE_FILE = "runway_state.json"
OUTPUT_FILE = "runway_usage.md"

# Browser-like headers to avoid 403 errors
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bezoekbas.nl/home/actuele-informatie",
}

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

def parse_slot(line):
    """Attempts to split a line into a time slot and description."""
    # Matches "Van 09:20 tot 10:40: Description" or "Van 09:20 tot 10:40 Description"
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
                # Sort slots by time
                for slot_time in sorted(slots.keys()):
                    f.write(f"- {slot_time}: {slots[slot_time]}\n")
            else:
                f.write("*No structured runway info found.*\n")
            
            f.write("\n---\n\n")

def run_scraper(days_back=14):
    state = load_state()
    seen_slugs = set(state.get("seen_slugs", []))
    days = state.get("days", {})
    
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
            
            if not post_date_str:
                continue

            try:
                post_datetime = datetime.strptime(post_date_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
            
            if slug in seen_slugs:
                if post_datetime < cutoff_date:
                    stop_searching = True
                    break
                continue
                
            if post_datetime < cutoff_date:
                stop_searching = True
                break
            
            # New post found
            title = post.get('post_title')
            date_key = post_datetime.strftime('%Y-%m-%d')
            print(f"Processing: {post_date_str} - {title}")
            
            # Fetch detail
            detail_url = BASE_DETAIL_URL.format(slug=f"/runway/{slug}/")
            try:
                detail_res = requests.get(detail_url, headers=HEADERS, timeout=10)
                detail_res.raise_for_status()
                detail_data = detail_res.json()
                content_html = detail_data.get('post', {}).get('post', {}).get('post_content', '')
                
                runway_info = extract_runway_info(content_html)
                
                if date_key not in days:
                    days[date_key] = {
                        "title": title,
                        "slots": {},
                        "last_updated": post_date_str
                    }
                
                # Update slots. Since we process DESC (newest first), 
                # we should only update if the post is newer than what we have.
                # However, if we process multiple posts for the same day in one run, 
                # the first one we see is the newest.
                
                is_newer = post_date_str >= days[date_key].get('last_updated', '')
                
                for line in runway_info:
                    slot_time, description = parse_slot(line)
                    if slot_time:
                        # If it's a newer post, or the slot doesn't exist yet, update it
                        if is_newer or slot_time not in days[date_key]['slots']:
                            days[date_key]['slots'][slot_time] = description
                    else:
                        # Handle lines without clear slot (less common)
                        if is_newer:
                            # Use the line itself as a slot if we can't parse it? 
                            # Better to skip or add as a generic entry.
                            pass
                
                if is_newer:
                    days[date_key]['title'] = title
                    days[date_key]['last_updated'] = post_date_str

                seen_slugs.add(slug)
                new_results.append(slug)
            except Exception as e:
                print(f"Error fetching details for {slug}: {e}")
        
        page += 1
        if page > 5: # Safety break
            break

    if new_results:
        state["seen_slugs"] = list(seen_slugs)
        state["days"] = days
        write_markdown(state)
        save_state(state)
        print(f"Updated {len(new_results)} new posts and regenerated {OUTPUT_FILE}")
    else:
        print("No new updates found.")

if __name__ == "__main__":
    run_scraper(days_back=14)
