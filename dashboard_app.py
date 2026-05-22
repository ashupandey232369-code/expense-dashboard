"""
dashboard_app.py — Live Expense Dashboard
Hosted on Streamlit Cloud — free permanent URL
Reads Google Sheets in real time
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import json
import os

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="💰 Expense Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #0f0f1a; }
    .stMetric { background: #16213e; border-radius: 12px; padding: 16px; border: 1px solid #2a2a4a; }
    .stMetric label { color: #888 !important; font-size: 12px !important; }
    .stMetric .metric-value { color: #4ECDC4 !important; }
    div[data-testid="metric-container"] { background: #16213e; border-radius: 12px; padding: 12px; border: 1px solid #2a2a4a; }
    .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Load data from Google Sheets ──────────────────────────────────────────────
SPREADSHEET_ID = "1bvUafJrhOkcq-U_E4OVXQsHQcdp4NimGnc0_s7YFr7s"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_data(ttl=300)  # refresh every 5 minutes
def load_data():
    # Load credentials from Streamlit secrets
    creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    creds      = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client     = gspread.authorize(creds)
    sheet      = client.open_by_key(SPREADSHEET_ID).sheet1
    rows       = sheet.get_all_records()
    df         = pd.DataFrame(rows)

    if df.empty:
        return df

    df['Amount']     = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
    df['Date']       = pd.to_datetime(df['Date'], errors='coerce')
    df               = df[df['Amount'] > 0].dropna(subset=['Date'])
    df['Month']      = df['Date'].dt.to_period('M').astype(str)
    df['MonthLabel'] = df['Date'].dt.strftime('%b %Y')
    df['Week']       = df['Date'].dt.to_period('W').astype(str)
    df['WeekLabel']  = df['Date'].apply(lambda d: f"Week {d.strftime('%d %b')}")
    df['Day']        = df['Date'].dt.date
    df['DayStr']     = df['Date'].dt.strftime('%Y-%m-%d')
    df['Weekday']    = df['Date'].dt.day_name()
    df['Hour']       = df['Date'].dt.hour

    return df

COLORS = ['#4ECDC4','#FF6B6B','#45B7D1','#96CEB4','#FFEAA7',
          '#DDA0DD','#98D8C8','#F7DC6F','#a29bfe','#fd79a8']

PLOT_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(22,33,62,0.5)',
    font=dict(color='#ccc', size=12),
    margin=dict(t=20, r=10, b=40, l=50),
    xaxis=dict(gridcolor='#2a2a4a', zerolinecolor='#2a2a4a'),
    yaxis=dict(gridcolor='#2a2a4a', zerolinecolor='#2a2a4a'),
    legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#ccc')),
)

# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("💰 Expense Tracker Dashboard")
        st.caption(f"Live data from Google Sheets · Auto-refreshes every 5 minutes")
    with col2:
        if st.button("🔄 Refresh Now"):
            st.cache_data.clear()
            st.rerun()

    # Load data
    with st.spinner("Loading expenses..."):
        df = load_data()

    if df.empty:
        st.warning("No expenses found. Start logging expenses on WhatsApp!")
        return

    # ── Sidebar filters ───────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🎛️ Filters")

        # View mode
        view_mode = st.radio(
            "View by",
            ["Daily", "Weekly", "Monthly"],
            index=2
        )

        # Date range
        st.subheader("Date Range")
        min_date = df['Date'].min().date()
        max_date = df['Date'].max().date()

        if view_mode == "Monthly":
            months = sorted(df['MonthLabel'].unique().tolist(), reverse=True)
            selected_period = st.selectbox("Select Month", ["All Time"] + months)
        elif view_mode == "Weekly":
            weeks = sorted(df['Week'].unique().tolist(), reverse=True)
            selected_period = st.selectbox("Select Week", ["All Time"] + weeks)
        else:
            date_range = st.date_input(
                "Select Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
            selected_period = date_range

        # Category filter
        st.subheader("Category")
        all_cats = sorted(df['Category'].unique().tolist())
        selected_cats = st.multiselect(
            "Select Categories",
            all_cats,
            default=all_cats
        )

        st.markdown("---")
        st.caption(f"Total records: {len(df)}")
        st.caption(f"Date range: {min_date} → {max_date}")

    # ── Filter data ───────────────────────────────────────────────────────────
    filtered = df.copy()

    if view_mode == "Monthly" and selected_period != "All Time":
        filtered = filtered[filtered['MonthLabel'] == selected_period]
    elif view_mode == "Weekly" and selected_period != "All Time":
        filtered = filtered[filtered['Week'] == selected_period]
    elif view_mode == "Daily" and len(selected_period) == 2:
        filtered = filtered[
            (filtered['Day'] >= selected_period[0]) &
            (filtered['Day'] <= selected_period[1])
        ]

    if selected_cats:
        filtered = filtered[filtered['Category'].isin(selected_cats)]

    if filtered.empty:
        st.warning("No data for selected filters.")
        return

    # ── KPI Metrics ───────────────────────────────────────────────────────────
    st.subheader("📊 Key Metrics")

    total       = filtered['Amount'].sum()
    num_days    = max(filtered['Date'].nunique(), 1)
    avg_daily   = total / num_days
    avg_tx      = filtered['Amount'].mean()
    top_cat     = filtered.groupby('Category')['Amount'].sum().idxmax()
    top_cat_amt = filtered.groupby('Category')['Amount'].sum().max()
    num_tx      = len(filtered)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Total Spent",    f"₹{total:,.0f}")
    c2.metric("📅 Daily Average",  f"₹{avg_daily:,.0f}")
    c3.metric("🧾 Transactions",   num_tx)
    c4.metric("📂 Top Category",   top_cat, f"₹{top_cat_amt:,.0f}")
    c5.metric("💳 Avg per entry",  f"₹{avg_tx:,.0f}")

    st.markdown("---")

    # ── Charts Row 1 ──────────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📈 Spending Trend")

        if view_mode == "Monthly":
            trend = filtered.groupby('MonthLabel')['Amount'].sum().reset_index()
            trend.columns = ['Period', 'Amount']
            # Sort by month
            trend['SortKey'] = pd.to_datetime(trend['Period'], format='%b %Y')
            trend = trend.sort_values('SortKey')
        elif view_mode == "Weekly":
            trend = filtered.groupby('Week')['Amount'].sum().reset_index()
            trend.columns = ['Period', 'Amount']
            trend = trend.sort_values('Period')
        else:
            trend = filtered.groupby('DayStr')['Amount'].sum().reset_index()
            trend.columns = ['Period', 'Amount']
            trend = trend.sort_values('Period')

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=trend['Period'], y=trend['Amount'],
            marker_color='#4ECDC4', opacity=0.85,
            hovertemplate='%{x}<br>₹%{y:,.0f}<extra></extra>'
        ))
        # Add average line
        avg_line = trend['Amount'].mean()
        fig_trend.add_hline(
            y=avg_line, line_dash="dash",
            line_color="#FF6B6B", opacity=0.7,
            annotation_text=f"Avg ₹{avg_line:,.0f}",
            annotation_font_color="#FF6B6B"
        )
        fig_trend.update_layout(**PLOT_LAYOUT, height=350)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_right:
        st.subheader("🍕 Category Split")
        cats_data = filtered.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        fig_pie = go.Figure(go.Pie(
            labels=cats_data.index,
            values=cats_data.values,
            marker_colors=COLORS[:len(cats_data)],
            hole=0.4,
            textinfo='label+percent',
            hovertemplate='%{label}<br>₹%{value:,.0f} (%{percent})<extra></extra>'
        ))
        fig_pie.update_layout(**PLOT_LAYOUT, height=350, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Charts Row 2 ──────────────────────────────────────────────────────────
    col_left2, col_right2 = st.columns([2, 3])

    with col_left2:
        st.subheader("📅 Day of Week Pattern")
        order   = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        weekday = filtered.groupby('Weekday')['Amount'].sum().reindex(order).fillna(0)
        avg_wd  = weekday.mean()
        fig_wd  = go.Figure(go.Bar(
            x=weekday.index,
            y=weekday.values,
            marker_color=['#FF6B6B' if v > avg_wd else '#4ECDC4' for v in weekday.values],
            hovertemplate='%{x}<br>₹%{y:,.0f}<extra></extra>'
        ))
        fig_wd.update_layout(**PLOT_LAYOUT, height=320)
        st.plotly_chart(fig_wd, use_container_width=True)

    with col_right2:
        st.subheader("📊 Category Trends Over Time")
        top_cats = filtered.groupby('Category')['Amount'].sum().nlargest(6).index

        if view_mode == "Monthly":
            pivot = filtered[filtered['Category'].isin(top_cats)].groupby(
                ['MonthLabel', 'Category'])['Amount'].sum().unstack(fill_value=0)
        elif view_mode == "Weekly":
            pivot = filtered[filtered['Category'].isin(top_cats)].groupby(
                ['Week', 'Category'])['Amount'].sum().unstack(fill_value=0)
        else:
            pivot = filtered[filtered['Category'].isin(top_cats)].groupby(
                ['DayStr', 'Category'])['Amount'].sum().unstack(fill_value=0)

        fig_cat = go.Figure()
        for i, cat in enumerate(pivot.columns):
            fig_cat.add_trace(go.Bar(
                name=cat,
                x=pivot.index.astype(str),
                y=pivot[cat],
                marker_color=COLORS[i % len(COLORS)],
                hovertemplate=f'{cat}<br>%{{x}}<br>₹%{{y:,.0f}}<extra></extra>'
            ))
        fig_cat.update_layout(**PLOT_LAYOUT, height=320, barmode='stack')
        st.plotly_chart(fig_cat, use_container_width=True)

    # ── Payment Mode ──────────────────────────────────────────────────────────
    if 'Payment Mode' in filtered.columns:
        col_pm1, col_pm2 = st.columns([1, 3])

        with col_pm1:
            st.subheader("💳 Payment Mode")
            pm = filtered.groupby('Payment Mode')['Amount'].sum()
            pm = pm[pm.index != 'Unknown'] if 'Unknown' in pm.index and len(pm) > 1 else pm
            fig_pm = go.Figure(go.Pie(
                labels=pm.index, values=pm.values,
                marker_colors=COLORS[:len(pm)],
                hole=0.4, textinfo='label+percent'
            ))
            fig_pm.update_layout(**PLOT_LAYOUT, height=280, showlegend=False)
            st.plotly_chart(fig_pm, use_container_width=True)

        with col_pm2:
            st.subheader("📈 Cumulative Spending")
            daily_cum = filtered.groupby('DayStr')['Amount'].sum().cumsum().reset_index()
            daily_cum.columns = ['Date', 'Cumulative']
            fig_cum = go.Figure()
            fig_cum.add_trace(go.Scatter(
                x=daily_cum['Date'], y=daily_cum['Cumulative'],
                fill='tozeroy', line_color='#4ECDC4',
                fillcolor='rgba(78,205,196,0.1)',
                hovertemplate='%{x}<br>₹%{y:,.0f}<extra></extra>'
            ))
            fig_cum.update_layout(**PLOT_LAYOUT, height=280)
            st.plotly_chart(fig_cum, use_container_width=True)

    # ── Recent Transactions ───────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🕐 Recent Transactions")

    recent = filtered.sort_values('Date', ascending=False).head(20)
    display_cols = ['Date', 'Amount', 'Category', 'Notes', 'Payment Mode', 'Raw Message']
    display_cols = [c for c in display_cols if c in recent.columns]

    st.dataframe(
        recent[display_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.0f"),
            "Date":   st.column_config.DateColumn("Date", format="DD MMM YYYY"),
        }
    )

    # ── Download button ───────────────────────────────────────────────────────
    csv = filtered.to_csv(index=False)
    st.download_button(
        label="⬇️ Download filtered data as CSV",
        data=csv,
        file_name=f"expenses_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

if __name__ == "__main__":
    main()
