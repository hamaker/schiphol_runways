import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import date, datetime

# Configuration
DB_FILE = "runway_data.db"

st.set_page_config(page_title="Schiphol Runway Usage", layout="wide")

if not os.path.exists(DB_FILE):
    st.error(f"Database file `{DB_FILE}` not found. Please run `bas_scraper.py` first.")
    st.stop()

# Helper function to load data
@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM runway_usage", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df

df = load_data()

# --- Page Functions ---

def overview_page():
    st.title("Schiphol Runway Usage Overview")
    st.markdown("Visualize overall runway activity based on data from `bezoekbas.nl`.")

    # Sidebar filters
    st.sidebar.header("Filters")
    min_date = df['date'].min()
    max_date = df['date'].max()
    date_range = st.sidebar.date_input(
        "Select Date Range", 
        value=(min_date, max_date), 
        min_value=min_date, 
        max_value=max_date,
        key="overview_date_range"
    )

    all_runways = sorted(df['runway_name'].unique())
    selected_runways = st.sidebar.multiselect(
        "Select Runways", 
        options=all_runways, 
        default=all_runways,
        key="overview_runway_select"
    )

    all_directions = sorted(df['direction'].unique())
    selected_directions = st.sidebar.multiselect(
        "Select Directions", 
        options=all_directions, 
        default=all_directions,
        key="overview_direction_select"
    )

    all_operations = sorted(df['operation'].unique())
    selected_operations = st.sidebar.multiselect(
        "Select Operations", 
        options=all_operations, 
        default=all_operations,
        key="overview_operation_select"
    )

    # Apply filters
    filtered_df = df[
        (df['runway_name'].isin(selected_runways)) &
        (df['direction'].isin(selected_directions)) &
        (df['operation'].isin(selected_operations))
    ]

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['date'] >= start_date) & (filtered_df['date'] <= end_date)]
    elif isinstance(date_range, date):
        filtered_df = filtered_df[filtered_df['date'] == date_range]

    filtered_df = filtered_df.sort_values(by=['date', 'start_time', 'post_date'], ascending=[False, False, False])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Slots", len(filtered_df))
    col2.metric("Runways Selected", len(selected_runways))
    col3.metric("Operations Selected", len(selected_operations))

    st.subheader("Filtered Usage Data")
    display_cols = ['date', 'start_time', 'end_time', 'operation', 'runway_name', 'direction', 'post_date']
    st.dataframe(filtered_df[display_cols], use_container_width=True)

    if not filtered_df.empty:
        st.subheader("Usage Frequency by Runway")
        usage_counts = filtered_df.groupby(['runway_name', 'operation']).size().reset_index(name='count')
        st.bar_chart(usage_counts, x="runway_name", y="count", color="operation", use_container_width=True)

def runway_detail_page(runway_name):
    st.title(f"{runway_name}")
    
    runway_df = df[df['runway_name'] == runway_name]
    today = date(2026, 5, 24)
    
    st.write(f"Showing historical usage for the **{runway_name}**.")
    
    # Today's slots
    today_slots = runway_df[runway_df['date'] == today].sort_values(by='start_time')
    
    st.markdown(f"### Today ({today.strftime('%d %B %Y')})")
    if not today_slots.empty:
        for _, row in today_slots.iterrows():
            st.write(f"**{row['start_time']} - {row['end_time']}**: {row['operation']} (Direction: {row['direction']})")
    else:
        st.info(f"No slots found for {runway_name} today.")
    
    st.divider()
    
    # Past slots
    past_slots = runway_df[runway_df['date'] != today].sort_values(by=['date', 'start_time'], ascending=[False, True])
    
    if not past_slots.empty:
        current_date = None
        for _, row in past_slots.iterrows():
            if row['date'] != current_date:
                current_date = row['date']
                st.markdown(f"### {current_date.strftime('%d %B %Y')}")
            st.write(f"- **{row['start_time']} - {row['end_time']}**: {row['operation']} (Direction: {row['direction']})")
    else:
        st.write("No historical data available for this runway.")

# --- Navigation Setup ---

all_runway_names = sorted(df['runway_name'].unique())

# Define base pages
pages = {
    "Overview": [st.Page(overview_page, title="Overview", url_path="overview")],
    "Runways": [
        st.Page(
            lambda r=name: runway_detail_page(r), 
            title=name, 
            url_path=name.replace(" ", "_")
        ) for name in all_runway_names
    ]
}

pg = st.navigation(pages)
pg.run()
