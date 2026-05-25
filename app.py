import streamlit as st
import pandas as pd
import sqlite3
import os
import altair as alt
from datetime import date, datetime, timedelta

# Configuration
DB_FILE = "runway_data.db"

# Helper for Dutch date formatting
def dutch_date(d):
    months = ["januari", "februari", "maart", "april", "mei", "juni", 
              "juli", "augustus", "september", "oktober", "november", "december"]
    return f"{d.day} {months[d.month-1]} {d.year}"

st.set_page_config(page_title="baangebruik Schiphol", layout="wide")

if not os.path.exists(DB_FILE):
    st.error(f"Databasebestand `{DB_FILE}` niet gevonden. Voer eerst `bas_scraper.py` uit.")
    st.stop()

# Helper function to load data
@st.cache_data(ttl=120) # Cache for 2 minutes
def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM runway_usage", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date']).dt.date
    # Translate operations in the dataframe for consistent display
    df['operation'] = df['operation'].replace({'Landing': 'Landen', 'Takeoff': 'Starten'})
    return df

df = load_data()

# Helper function for timeline chart
def plot_runway_timeline(runway_df, plot_date):
    base_dt = datetime.combine(plot_date, datetime.min.time())
    next_day_dt = base_dt + timedelta(days=1)

    def to_dt(t_str):
        try:
            h, m = map(int, t_str.split(':'))
            return base_dt + timedelta(hours=h, minutes=m)
        except:
            return base_dt

    # Combined data approach for clean layering
    records = []
    
    # 1. Active slots
    if not runway_df.empty:
        for _, row in runway_df.iterrows():
            start_dt = to_dt(row['start_time'])
            end_dt = to_dt(row['end_time'])
            if row['end_time'] == '23:59':
                end_dt = next_day_dt
            
            records.append({
                'start_dt': start_dt,
                'end_dt': end_dt,
                'operation': row['operation'],
                'direction': row['direction'],
                'tooltip_start': row['start_time'],
                'tooltip_end': row['end_time']
            })

    # 2. Information gap (airport-wide)
    if not df.empty:
        max_date_in_db = df['date'].max()
        if plot_date < max_date_in_db:
            global_max_dt = next_day_dt
        elif plot_date == max_date_in_db:
            global_day_data = df[df['date'] == plot_date]
            global_max_time_str = global_day_data['end_time'].max()
            global_max_dt = to_dt(global_max_time_str)
            if global_max_time_str == '23:59':
                global_max_dt = next_day_dt
        else:
            global_max_dt = base_dt
    else:
        global_max_dt = base_dt

    if global_max_dt < next_day_dt:
        records.append({
            'start_dt': global_max_dt,
            'end_dt': next_day_dt,
            'operation': 'Geen informatie',
            'direction': '',
            'tooltip_start': global_max_dt.strftime('%H:%M'),
            'tooltip_end': '00:00'
        })

    # 3. Anchors for full 24h axis
    records.append({'start_dt': base_dt, 'end_dt': base_dt + timedelta(seconds=1), 'operation': 'Anchor'})
    records.append({'start_dt': next_day_dt - timedelta(seconds=1), 'end_dt': next_day_dt, 'operation': 'Anchor'})

    plot_df = pd.DataFrame(records)
    plot_df['mid_dt'] = plot_df['start_dt'] + (plot_df['end_dt'] - plot_df['start_dt']) / 2

    # Unified base chart
    base = alt.Chart(plot_df).encode(
        x=alt.X('start_dt:T', 
                title=None, 
                scale=alt.Scale(domain=[base_dt, next_day_dt]),
                axis=alt.Axis(format='%H:%M', tickCount=24, labelAngle=0, labelFlush=False)),
        tooltip=[
            alt.Tooltip('tooltip_start:N', title='Start'),
            alt.Tooltip('tooltip_end:N', title='Eind'),
            alt.Tooltip('operation:N', title='Gebruik'),
            alt.Tooltip('direction:N', title='Richting')
        ]
    )

    # Bars layer
    bars = base.mark_bar(
        stroke='white', 
        strokeWidth=1,
        size=30
    ).encode(
        x2='end_dt:T',
        y=alt.value(15), # Centered in the 60px area
        color=alt.Color('operation:N', 
                        scale=alt.Scale(
                            domain=['Landen', 'Starten', 'Geen informatie', 'Anchor'], 
                            range=['#1f77b4', '#ff7f0e', '#999999', 'transparent']
                        ),
                        legend=alt.Legend(title="Gebruik", values=['Landen', 'Starten']))
    )

    # Text layer
    text = base.transform_filter(
        alt.FieldOneOfPredicate(field='operation', oneOf=['Landen', 'Starten'])
    ).mark_text(
        align='center',
        baseline='middle',
        color='white',
        fontWeight='bold',
        fontSize=12
    ).encode(
        x='mid_dt:T',
        y=alt.value(15), # Centered in the 60px area
        text='direction:N'
    )

    chart = (bars + text).properties(
        height=68, # Reduced from 100
        width='container'
    )
    
    return chart

def merge_slots(df):
    """Merges adjacent time slots with the same operation and direction."""
    if df.empty:
        return df
    
    df = df.sort_values('start_time').reset_index(drop=True)
    
    merged = []
    if not df.empty:
        curr = df.iloc[0].to_dict()
        
        for i in range(1, len(df)):
            nxt = df.iloc[i].to_dict()
            
            if (curr['end_time'] == nxt['start_time'] and 
                curr['operation'] == nxt['operation'] and 
                curr['direction'] == nxt['direction']):
                curr['end_time'] = nxt['end_time']
            else:
                merged.append(curr)
                curr = nxt
        merged.append(curr)
        
    return pd.DataFrame(merged)

# Helper function for analytics
def inject_analytics(path):
    # In Streamlit, this runs in an iframe. We use the JS script AND an image pixel fallback.
    # We dynamically pass the current page URL to the pixel to ensure it's tracked even in the iframe.
    analytics_code = f"""
    <script data-goatcounter="https://schiphol-runways.goatcounter.com/count"
            async src="https://gc.zgo.at/count.js"></script>
    <img src="https://schiphol-runways.goatcounter.com/count?p=/{path}" style="display:none">
    """
    st.components.v1.html(analytics_code, height=1)

# Helper function for data freshness and coverage display
def show_last_update():
    if not df.empty:
        laatste_update = pd.to_datetime(df['post_date']).max()
        laatste_update_str = f"{dutch_date(laatste_update)} {laatste_update.strftime('%H:%M')}"
        
        max_date = df['date'].max()
        max_time = df[df['date'] == max_date]['end_time'].max()
        coverage_str = f"{dutch_date(max_date)} {max_time}"
        
        st.caption(f"Laatste update van bezoekbas.nl: {laatste_update_str}  \nDeze update bevat informatie tot: {coverage_str}")

# --- Page Functions ---

def overview_page():
    inject_analytics("overzicht")
    st.title("Schiphol Baangebruik Overzicht")
    show_last_update()
    st.markdown("Visualiseer de algemene baanactiviteit op basis van gegevens van `bezoekbas.nl`.")

    # Sidebar filters
    st.sidebar.header("Filters")
    min_date = df['date'].min()
    max_date = df['date'].max()
    date_range = st.sidebar.date_input(
        "Selecteer Datumbereik", 
        value=(min_date, max_date), 
        min_value=min_date, 
        max_value=max_date,
        key="overview_date_range"
    )

    all_runways = sorted(df['runway_name'].unique())
    selected_runways = st.sidebar.multiselect(
        "Selecteer Banen", 
        options=all_runways, 
        default=all_runways,
        key="overview_runway_select"
    )

    all_directions = sorted(df['direction'].unique())
    selected_directions = st.sidebar.multiselect(
        "Selecteer Richtingen", 
        options=all_directions, 
        default=all_directions,
        key="overview_direction_select"
    )

    all_operations = sorted(df['operation'].unique())
    selected_operations = st.sidebar.multiselect(
        "Selecteer Gebruik", 
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
    col1.metric("Totaal aantal slots", len(filtered_df))
    col2.metric("Geselecteerde banen", len(selected_runways))
    col3.metric("Geselecteerd gebruik", len(selected_operations))

    st.subheader("Gefilterde Gebruiksgegevens")
    display_cols = ['date', 'start_time', 'end_time', 'operation', 'runway_name', 'direction', 'post_date']
    # Rename columns for the table
    display_df = filtered_df[display_cols].rename(columns={
        'date': 'Datum',
        'start_time': 'Start',
        'end_time': 'Eind',
        'operation': 'Gebruik',
        'runway_name': 'Baan',
        'direction': 'Richting',
        'post_date': 'Publicatiedatum'
    })
    st.dataframe(display_df, use_container_width=True)

    st.subheader("Dagelijks Overzicht")
    if not filtered_df.empty:
        min_date_val = filtered_df['date'].min()
        max_date_val = filtered_df['date'].max()
        
        effective_today = date.today()
        tomorrow = effective_today + timedelta(days=1)
        
        if max_date_val < tomorrow:
            if not filtered_df[filtered_df['date'] == tomorrow].empty:
                max_date_val = tomorrow
        
        if max_date_val < effective_today:
            max_date_val = effective_today
            
        full_range = [max_date_val - timedelta(days=x) for x in range((max_date_val - min_date_val).days + 1)]
        
        for d in full_range:
            date_display = dutch_date(d)
            if d == effective_today:
                date_display += " (Vandaag)"
            elif d == tomorrow:
                date_display += " (Morgen)"
            
            st.markdown(f"#### {date_display}")
            day_data = filtered_df[filtered_df['date'] == d]
            
            if not day_data.empty:
                summary = day_data.groupby(['runway_name', 'operation']).size().reset_index()
                # Merge items with compact line spacing and without bullets
                summary_text = "  \n".join([
                    f"**{row['runway_name']}**: {row['operation']}"
                    for _, row in summary.iterrows()
                ])
                st.markdown(summary_text)
            else:
                st.write("*Geen activiteit geregistreerd voor de geselecteerde filters.*")

        st.subheader("Gebruiksfrequentie per Baan")
        usage_counts = filtered_df.groupby(['runway_name', 'operation']).size().reset_index(name='aantal')
        st.bar_chart(usage_counts, x="runway_name", y="aantal", color="operation", use_container_width=True)
    else:
        st.write("Geen gegevens beschikbaar voor de huidige filters.")

def runway_detail_page(runway_name):
    inject_analytics(runway_name.replace(" ", "_"))
    st.title(f"{runway_name}")
    show_last_update()
    
    runway_df = df[df['runway_name'] == runway_name]
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    st.write(f"Verwacht gebruik voor de **{runway_name}**. Deze informatie is gebaseerd op de \
          meest actuele verwachting van Luchtverkeersleiding Nederland (LVNL) zoals gepubliceerd op \
          [bezoekbas.nl](https://bezoekbas.nl/actuele-informatie)")
    
    # --- Tomorrow's Section ---
    tomorrow_df = runway_df[runway_df['date'] == tomorrow]
    if not tomorrow_df.empty:
        st.markdown(f"### Morgen ({dutch_date(tomorrow)})")
        tomorrow_slots = merge_slots(tomorrow_df)
        chart = plot_runway_timeline(tomorrow_slots, tomorrow)
        if chart:
            st.altair_chart(chart, use_container_width=True)
        
        # Consolidate slots into a single markdown block for compact spacing
        # Note the two spaces before \n for a markdown line break
        slots_text = "  \n".join([
            f"**{row['start_time']} - {row['end_time']}**: {row['operation']} (Richting: {row['direction']})"
            for _, row in tomorrow_slots.iterrows()
        ])
        st.markdown(slots_text)
        st.divider()

    # --- Today's Section ---
    st.markdown(f"### Vandaag ({dutch_date(today)})")
    today_df = runway_df[runway_df['date'] == today]
    
    today_slots = merge_slots(today_df) if not today_df.empty else pd.DataFrame()
    chart = plot_runway_timeline(today_slots, today)
    if chart:
        st.altair_chart(chart, use_container_width=True)

    if not today_df.empty:
        # Consolidate slots into a single markdown block for compact spacing
        # Note the two spaces before \n for a markdown line break
        slots_text = "  \n".join([
            f"**{row['start_time']} - {row['end_time']}**: {row['operation']} (Richting: {row['direction']})"
            for _, row in today_slots.iterrows()
        ])
        st.markdown(slots_text)
    else:
        st.info(f"Een rustige dag: geen tijdslots gevonden voor {runway_name} vandaag.")
    
    st.divider()
    
    # --- Historical Section ---
    min_date_val = runway_df['date'].min()
    yesterday = today - timedelta(days=1)

    if min_date_val and min_date_val <= yesterday:
        full_date_range = [yesterday - timedelta(days=x) for x in range((yesterday - min_date_val).days + 1)]

        for d in full_date_range:
            st.markdown(f"### {dutch_date(d)}")
            day_df = runway_df[runway_df['date'] == d]
            
            merged_day_slots = merge_slots(day_df) if not day_df.empty else pd.DataFrame()
            chart = plot_runway_timeline(merged_day_slots, d)
            if chart:
                st.altair_chart(chart, use_container_width=True)

            if not day_df.empty:
                # Consolidate slots into a single markdown block for compact spacing
                # Note the two spaces before \n for a markdown line break
                slots_text = "  \n".join([
                    f"**{row['start_time']} - {row['end_time']}**: {row['operation']} (Richting: {row['direction']})"
                    for _, row in merged_day_slots.iterrows()
                ])
                st.markdown(slots_text)
            else:
                st.write("*Geen baangebruik geregistreerd voor deze datum.*")
    elif min_date_val == today:
        pass
    else:
        st.write("Geen historische gegevens beschikbaar voor deze baan.")


# --- Navigation Setup ---

all_runway_names = sorted(df['runway_name'].unique())

pages = {
    "Overzicht": [st.Page(overview_page, title="Overzicht", url_path="overzicht")],
    "Banen": [
        st.Page(
            lambda r=name: runway_detail_page(r), 
            title=name, 
            url_path=name.replace(" ", "_")
        ) for name in all_runway_names
    ]
}

pg = st.navigation(pages)

# Data freshness metadata in sidebar
if not df.empty:
    laatste_update = pd.to_datetime(df['post_date']).max()
    laatste_update_str = f"{dutch_date(laatste_update)} {laatste_update.strftime('%H:%M')}"
    
    max_date = df['date'].max()
    max_time = df[df['date'] == max_date]['end_time'].max()
    coverage_str = f"{dutch_date(max_date)} {max_time}"
    
    st.sidebar.markdown(f"**Laatste update van bezoekbas.nl:**  \n{laatste_update_str}")
    st.sidebar.markdown(f"**Informatie beschikbaar tot:**  \n{coverage_str}")
    st.sidebar.divider()

pg.run()
