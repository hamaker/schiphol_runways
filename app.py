import streamlit as st
import pandas as pd
import sqlite3
import os

# Configuration
DB_FILE = "runway_data.db"

st.set_page_config(page_title="Schiphol Runway Usage", layout="wide")

st.title("✈️ Schiphol Runway Usage Dashboard")
st.markdown("Visualize which runways are in use for landing and takeoff based on data from `bezoekbas.nl`.")

if not os.path.exists(DB_FILE):
    st.error(f"Database file `{DB_FILE}` not found. Please run `bas_scraper.py` first.")
    st.stop()

# Helper function to load data
@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM runway_usage", conn)
    conn.close()
    # Convert date to datetime for filtering
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df

df = load_data()

# Sidebar filters
st.sidebar.header("Filters")

# Date range filter
min_date = df['date'].min()
max_date = df['date'].max()
date_range = st.sidebar.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

# Multi-select filters
all_runways = sorted(df['runway_name'].unique())
selected_runways = st.sidebar.multiselect("Select Runways", options=all_runways, default=all_runways)

all_directions = sorted(df['direction'].unique())
selected_directions = st.sidebar.multiselect("Select Directions", options=all_directions, default=all_directions)

all_operations = sorted(df['operation'].unique())
selected_operations = st.sidebar.multiselect("Select Operations", options=all_operations, default=all_operations)

# Apply filters
filtered_df = df[
    (df['runway_name'].isin(selected_runways)) &
    (df['direction'].isin(selected_directions)) &
    (df['operation'].isin(selected_operations))
]

# Date filtering (handle single date vs range)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[(filtered_df['date'] >= start_date) & (filtered_df['date'] <= end_date)]
elif isinstance(date_range, datetime.date):
    filtered_df = filtered_df[filtered_df['date'] == date_range]

# Sort by date and start_time DESC
filtered_df = filtered_df.sort_values(by=['date', 'start_time', 'post_date'], ascending=[False, False, False])

# Main layout
col1, col2, col3 = st.columns(3)
col1.metric("Total Slots", len(filtered_df))
col2.metric("Runways Selected", len(selected_runways))
col3.metric("Operations Selected", len(selected_operations))

st.subheader("Runway Usage Data")
# Reorder columns for better display
display_cols = ['date', 'start_time', 'end_time', 'operation', 'runway_name', 'direction', 'post_date']
st.dataframe(filtered_df[display_cols], use_container_width=True)

# Visualizations
if not filtered_df.empty:
    st.subheader("Usage Frequency by Runway")
    usage_counts = filtered_df.groupby(['runway_name', 'operation']).size().reset_index(name='count')
    st.bar_chart(usage_counts, x="runway_name", y="count", color="operation", use_container_width=True)

    st.subheader("Usage Frequency by Direction")
    direction_counts = filtered_df.groupby(['direction', 'operation']).size().reset_index(name='count')
    st.bar_chart(direction_counts, x="direction", y="count", color="operation", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.info("Data is updated manually by running `bas_scraper.py`.")
