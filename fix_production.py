import sqlite3
import json
import os
import shutil
from datetime import datetime

DB_FILE = "runway_data.db"
STATE_FILE = "runway_state.json"
BACKUP_DB = "runway_data.db.bak"

def cleanup():
    # 1. Backup
    if os.path.exists(DB_FILE):
        print(f"Creating backup: {BACKUP_DB}")
        shutil.copy2(DB_FILE, BACKUP_DB)
    
    # 2. Cleanup Database
    # We delete records from May 25th onwards to cover all reported issues
    # and ensure the scraper re-imports them with correct logic.
    cutoff_date = "2026-05-25"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print(f"Deleting records from {DB_FILE} where date >= {cutoff_date}...")
    cursor.execute("SELECT DISTINCT slug FROM runway_usage WHERE date >= ?", (cutoff_date,))
    affected_slugs = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("DELETE FROM runway_usage WHERE date >= ?", (cutoff_date,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"Deleted {deleted_count} records.")

    # 3. Cleanup State JSON
    if os.path.exists(STATE_FILE):
        print(f"Removing affected slugs from {STATE_FILE} to force re-processing...")
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        
        original_count = len(state.get("seen_slugs", []))
        # Remove any slugs that were associated with the deleted records
        state["seen_slugs"] = [s for s in state.get("seen_slugs", []) if s not in affected_slugs]
        
        # Also clean up the 'days' dictionary for the affected period
        new_days = {}
        for d, val in state.get("days", {}).items():
            if d < cutoff_date:
                new_days[d] = val
        state["days"] = new_days
        
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"Removed {original_count - len(state['seen_slugs'])} slugs from state.")

    print("\nCleanup complete. You can now run 'python3 bas_scraper.py' to re-import correct data.")

if __name__ == "__main__":
    cleanup()
