import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlalchemy as sa
from urllib.parse import quote_plus
from datetime import datetime


st.set_page_config(
    page_title="Customer Activity Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_engine():
    """
    Create a SQLAlchemy engine for SQL Server via ODBC (pyodbc).
    """
    odbc_params = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=HARSHYY;"
        "DATABASE=AdventureWorksDW2022;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    
    conn_str = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_params)}"
    return sa.create_engine(conn_str, fast_executemany=True, pool_pre_ping=True)


@st.cache_data(ttl=600)
def load_data(query: str) -> pd.DataFrame:
    """
    Load data from SQL Server with caching (10-minute TTL).
    """
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


# 1. Main KPI Query
kpi_query = """
SELECT 'Total Customers' AS Metric, COUNT(*) AS Value FROM dbo.DimCustomer
UNION ALL
SELECT 'With Phone', COUNT(*) FROM dbo.DimCustomer WHERE Phone IS NOT NULL
UNION ALL
SELECT 'Email Opt-In', COUNT(*) FROM dbo.DimCustomer WHERE EmailAddress IS NOT NULL
UNION ALL
SELECT 'Total Activities', COUNT(*) FROM dbo.FactInternetSales
"""

# 2. Activity Breakdown Query
activity_by_type_query = """
SELECT 
    d.EnglishMonthName AS ActivityTypeName,
    COUNT(*) AS TotalActivities,
    COUNT(DISTINCT s.CustomerKey) AS UniqueCustomers
FROM dbo.FactInternetSales s
INNER JOIN dbo.DimDate d ON s.OrderDateKey = d.DateKey
GROUP BY d.EnglishMonthName, d.MonthNumberOfYear
ORDER BY d.MonthNumberOfYear
"""

# 3. Engagement Summary Query
engagement_query = """
SELECT 
    CASE 
        WHEN OrderCount >= 5 THEN 'Highly Engaged'
        WHEN OrderCount BETWEEN 2 AND 4 THEN 'Moderately Engaged'
        WHEN OrderCount = 1 THEN 'Low Engagement'
        ELSE 'No Engagement'
    END AS EngagementLevel,
    COUNT(*) AS CustomerCount
FROM (
    SELECT c.CustomerKey, COUNT(s.SalesOrderNumber) AS OrderCount
    FROM dbo.DimCustomer c
    LEFT JOIN dbo.FactInternetSales s ON c.CustomerKey = s.CustomerKey
    GROUP BY c.CustomerKey
) sub
GROUP BY 
    CASE 
        WHEN OrderCount >= 5 THEN 'Highly Engaged'
        WHEN OrderCount BETWEEN 2 AND 4 THEN 'Moderately Engaged'
        WHEN OrderCount = 1 THEN 'Low Engagement'
        ELSE 'No Engagement'
    END
"""

# 4. Channel Performance Query
channel_query = """
SELECT 
    p.EnglishProductCategoryName AS ChannelName,
    COUNT(*) AS Activities,
    COUNT(DISTINCT s.CustomerKey) AS Reach
FROM dbo.FactInternetSales s
INNER JOIN dbo.DimProduct pr ON s.ProductKey = pr.ProductKey
INNER JOIN dbo.DimProductSubcategory ps ON pr.ProductSubcategoryKey = ps.ProductSubcategoryKey
INNER JOIN dbo.DimProductCategory p ON ps.ProductCategoryKey = p.ProductCategoryKey
GROUP BY p.EnglishProductCategoryName
"""

# 5. Top Customers Query
top_customers_query = """
SELECT TOP 10
    CONCAT(c.FirstName, ' ', c.LastName) AS FullName,
    COUNT(*) AS TotalActivities,
    COUNT(DISTINCT s.OrderDateKey) AS DaysActive,
    SUM(CASE WHEN s.PromotionKey = 1 THEN 1 ELSE 0 END) AS EmailOpens,
    COUNT(*) - SUM(CASE WHEN s.PromotionKey = 1 THEN 1 ELSE 0 END) AS PhoneCalls
FROM dbo.FactInternetSales s
INNER JOIN dbo.DimCustomer c ON s.CustomerKey = c.CustomerKey
GROUP BY c.FirstName, c.LastName
ORDER BY TotalActivities DESC
"""

# 6. Activity by Day of Week Query
day_of_week_query = """
SELECT 
    d.EnglishDayNameOfWeek AS DayName,
    COUNT(*) AS TotalActivities
FROM dbo.FactInternetSales s
INNER JOIN dbo.DimDate d ON s.OrderDateKey = d.DateKey
GROUP BY d.EnglishDayNameOfWeek, d.DayNumberOfWeek
ORDER BY d.DayNumberOfWeek
"""

st.title("📊 Customer Activity Analytics Dashboard")
st.markdown("**Real-time insights from your data warehouse**")
st.markdown("---")


try:
    df_kpi = load_data(kpi_query)
    df_activity_type = load_data(activity_by_type_query)
    df_engagement = load_data(engagement_query)
    df_channel = load_data(channel_query)
    df_top_customers = load_data(top_customers_query)
    df_day_of_week = load_data(day_of_week_query)

    col1, col2, col3, col4 = st.columns(4)
    kpi_dict = dict(zip(df_kpi["Metric"], df_kpi["Value"]))

    with col1:
        st.metric(
            label="👥 Total Customers", value=f"{kpi_dict.get('Total Customers', 0):,}"
        )

    with col2:
        st.metric(
            label="📞 With Phone",
            value=f"{kpi_dict.get('With Phone', 0):,}",
            delta=f"{round(kpi_dict.get('With Phone', 0) / max(kpi_dict.get('Total Customers', 1), 1) * 100, 1)}%",
        )

    with col3:
        st.metric(
            label="📧 Email Opt-In",
            value=f"{kpi_dict.get('Email Opt-In', 0):,}",
            delta=f"{round(kpi_dict.get('Email Opt-In', 0) / max(kpi_dict.get('Total Customers', 1), 1) * 100, 1)}%",
        )

    with col4:
        st.metric(
            label="🎯 Total Activities",
            value=f"{kpi_dict.get('Total Activities', 0):,}",
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Activities by Type")
        fig_activity = px.bar(
            df_activity_type,
            x="ActivityTypeName",
            y="TotalActivities",
            text="TotalActivities",
            color="ActivityTypeName",
            labels={
                "TotalActivities": "Total Activities",
                "ActivityTypeName": "Activity Type",
            },
            height=400,
        )
        fig_activity.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_activity.update_layout(showlegend=False)
        st.plotly_chart(fig_activity, width="stretch")

    with col2:
        st.subheader("🎯 Customer Engagement Levels")

        engagement_order = [
            "Highly Engaged",
            "Moderately Engaged",
            "Low Engagement",
            "No Engagement",
        ]
        df_engagement["EngagementLevel"] = pd.Categorical(
            df_engagement["EngagementLevel"], categories=engagement_order, ordered=True
        )
        df_engagement = df_engagement.sort_values("EngagementLevel")

        fig_engagement = px.pie(
            df_engagement,
            values="CustomerCount",
            names="EngagementLevel",
            hole=0.4,
            color="EngagementLevel",
            color_discrete_map={
                "Highly Engaged": "#00CC96",
                "Moderately Engaged": "#FFA15A",
                "Low Engagement": "#EF553B",
                "No Engagement": "#636EFA",
            },
            height=400,
        )
        fig_engagement.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_engagement, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📱 Channel Performance")
        fig_channel = go.Figure()
        fig_channel.add_trace(
            go.Bar(
                name="Activities",
                x=df_channel["ChannelName"],
                y=df_channel["Activities"],
                marker_color="#636EFA",
            )
        )
        fig_channel.add_trace(
            go.Bar(
                name="Reach",
                x=df_channel["ChannelName"],
                y=df_channel["Reach"],
                marker_color="#EF553B",
            )
        )
        fig_channel.update_layout(
            barmode="group", height=400, xaxis_title="Channel", yaxis_title="Count"
        )
        st.plotly_chart(fig_channel, width="stretch")

    with col2:
        st.subheader("📅 Activity by Day of Week")
        fig_day = px.line(
            df_day_of_week,
            x="DayName",
            y="TotalActivities",
            markers=True,
            text="TotalActivities",
            height=400,
        )
        fig_day.update_traces(
            textposition="top center",
            line_color="#00CC96",
            line_width=3,
            marker_size=10,
        )
        fig_day.update_layout(xaxis_title="Day of Week", yaxis_title="Total Activities")
        st.plotly_chart(fig_day, width="stretch")

    st.markdown("---")
    st.subheader("🏆 Top 10 Most Engaged Customers")

    df_top_display = df_top_customers.copy()
    df_top_display.columns = [
        "Customer Name",
        "Total Activities",
        "Days Active",
        "Email Opens",
        "Phone Calls",
    ]

    st.dataframe(
        df_top_display,
        width="stretch",  # replaces use_container_width
        hide_index=True,
        column_config={
            "Customer Name": st.column_config.TextColumn(
                "Customer Name", width="large"
            ),
            "Total Activities": st.column_config.NumberColumn(
                "Total Activities", format="%d"
            ),
            "Days Active": st.column_config.NumberColumn("Days Active", format="%d"),
            "Email Opens": st.column_config.NumberColumn("Email Opens", format="%d"),
            "Phone Calls": st.column_config.NumberColumn("Phone Calls", format="%d"),
        },
    )

    with st.sidebar:
        st.header("📊 Detailed Metrics")

        st.markdown("### Activity Breakdown")
        for _, row in df_activity_type.iterrows():
            st.metric(
                label=row["ActivityTypeName"],
                value=f"{row['TotalActivities']:,}",
                delta=f"{row['UniqueCustomers']:,} customers",
            )
        st.markdown("---")
        st.markdown("### Engagement Summary")
        total_customers_in_buckets = df_engagement["CustomerCount"].sum()
        for _, row in df_engagement.iterrows():
            pct = (
                (row["CustomerCount"] / total_customers_in_buckets * 100)
                if total_customers_in_buckets
                else 0
            )
            st.metric(
                label=row["EngagementLevel"],
                value=f"{row['CustomerCount']:,}",
                delta=f"{pct:.1f}%",
            )

        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.info("Please check your database connection settings.")

st.markdown("---")
st.caption("Customer Activity Data Warehouse | Built with Streamlit & Plotly")

