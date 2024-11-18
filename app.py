import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta
import numpy as np
import io
import zipfile

# Set page config
st.set_page_config(layout="wide", page_title="Commodity Charter Pro")

# Bloomberg-style dark theme
st.markdown("""
    <style>
        /* Main app background */
        .stApp {
            background-color: #001133;
            color: #FFFFFF;
        }
        
        /* Sidebar */
        .css-1d391kg {
            background-color: #001133;
        }
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF;
        }
        section[data-testid="stSidebar"] .stMarkdown {
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] div {
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] .stSelectbox > div > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] .stDateInput > div > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] .stSelectbox label {
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] .stDateInput label {
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] h4 {
            color: #000000 !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background-color: #001133;
        }
        .stTabs [data-baseweb="tab"] {
            color: #FFFFFF;
        }
        
        /* Metrics */
        div[data-testid="stMetricValue"] {
            color: #FFB000;
        }
        div[data-testid="stMetricDelta"] {
            color: #00B8E6;
        }
        
        /* DataFrames */
        .stDataFrame {
            background-color: #001133;
        }
        div[data-testid="stTable"] {
            background-color: #001133;
        }
        .dataframe {
            background-color: #001133;
            color: #FFFFFF !important;
        }
        .dataframe th {
            background-color: #002266 !important;
            color: #FFFFFF !important;
        }
        .dataframe td {
            background-color: #001133 !important;
            color: #FFFFFF !important;
        }
        
        /* Headers in main content */
        .main h1, .main h2, .main h3, .main h4, .main h5, .main h6 {
            color: #FFFFFF !important;
        }
        
        /* Text elements in main content */
        .main p, .main span, .main label {
            color: #FFFFFF !important;
        }
        
        /* Info boxes */
        .stAlert {
            background-color: #002266 !important;
            color: #FFFFFF !important;
        }
        .stAlert > div {
            color: #FFFFFF !important;
        }
        
        /* Selectbox in main content */
        .main .stSelectbox > div > div {
            background-color: #002266 !important;
            color: #FFFFFF !important;
        }
        .main .stSelectbox label {
            color: #FFFFFF !important;
        }
        
        /* Date input in main content */
        .main .stDateInput > div > div {
            background-color: #002266 !important;
            color: #FFFFFF !important;
        }
        .main .stDateInput label {
            color: #FFFFFF !important;
        }
    </style>
    """, unsafe_allow_html=True)

# Load COT signal configurations
@st.cache_data
def load_cot_signals():
    signals_df = pd.read_csv('cot_signals.csv')
    # Process ranges into min-max values
    signals_df[['Bearish_Min', 'Bearish_Max']] = signals_df['Bearish_Range'].str.split('-', expand=True).astype(float)
    signals_df[['Bullish_Min', 'Bullish_Max']] = signals_df['Bullish_Range'].str.split('-', expand=True).astype(float)
    return signals_df

# Function to get CFTC data
@st.cache_data
def get_cftc_data():
    # URL for the CFTC Commitments of Traders data
    url = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2024.zip"
    
    try:
        response = requests.get(url)
        z = zipfile.ZipFile(io.BytesIO(response.content))
        
        # Read all files in the zip and concatenate
        dfs = []
        for filename in z.namelist():
            if filename.endswith('.txt'):
                df = pd.read_csv(z.open(filename), on_bad_lines='skip')
                dfs.append(df)
        
        if dfs:
            cot_df = pd.concat(dfs, ignore_index=True)
            # Process the data
            cot_df['Date'] = pd.to_datetime(cot_df['Report_Date_as_YYYY-MM-DD'])
            return cot_df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching CFTC data: {str(e)}")
        return pd.DataFrame()

def get_merchant_positions(cot_data, commodity):
    # Filter for the specific commodity
    commodity_data = cot_data[cot_data['Market_and_Exchange_Names'].str.contains(commodity, case=False, na=False)]
    
    if not commodity_data.empty:
        # Get merchant positions as percentages directly from CFTC data
        merchant_long_pct = commodity_data['Pct_of_OI_Prod_Merc_Long_All']
        merchant_short_pct = commodity_data['Pct_of_OI_Prod_Merc_Short_All']
        
        # Get absolute positions and Open Interest
        merchant_long = commodity_data['Prod_Merc_Positions_Long_All']
        merchant_short = commodity_data['Prod_Merc_Positions_Short_All']
        open_interest = commodity_data['Open_Interest_All']
        
        result_df = pd.DataFrame({
            'Date': commodity_data['Date'],
            'Merchant_Long': merchant_long,
            'Merchant_Short': merchant_short,
            'Merchant_Long_Pct': merchant_long_pct,
            'Merchant_Short_Pct': merchant_short_pct,
            'Open_Interest': open_interest
        })
        return result_df.sort_values('Date')
    return pd.DataFrame()

def get_position_signal(short_pct, long_pct, signals_df, commodity):
    commodity_signals = signals_df[signals_df['Commodity'] == commodity]
    if commodity_signals.empty:
        return 'NEUTRAL', []
    
    signal = 'NEUTRAL'
    reasons = []
    
    # Check for bullish signal (based on short percentage)
    if (short_pct >= commodity_signals['Bullish_Min'].iloc[0] and 
        short_pct <= commodity_signals['Bullish_Max'].iloc[0]):
        signal = 'BULLISH'
        reasons.append(f'Short {short_pct:.1f}% in bullish range')
    
    # Check for bearish signal (based on long percentage)
    if (long_pct >= commodity_signals['Bearish_Min'].iloc[0] and 
        long_pct <= commodity_signals['Bearish_Max'].iloc[0]):
        signal = 'BEARISH'
        reasons.append(f'Long {long_pct:.1f}% in bearish range')
    
    return signal, reasons

def analyze_trend_changes(price_data, open_interest_data, dates, window=50):
    """Analyze trend changes near Open Interest peaks with 50-day window"""
    # Create DataFrame with dates as index
    oi_df = pd.DataFrame({
        'Open_Interest': open_interest_data,
        'Date': pd.to_datetime(dates)
    }).set_index('Date')
    
    # Resample both datasets to daily frequency and align them
    price_daily = price_data.resample('D').last()
    oi_daily = oi_df.resample('D').last()
    
    # Forward fill missing values
    price_daily = price_daily.fillna(method='ffill')
    oi_daily = oi_daily.fillna(method='ffill')
    
    # Calculate price moving average for trend determination
    price_daily['MA'] = price_daily['Close'].rolling(window=window).mean()
    price_daily['Trend'] = np.where(price_daily['Close'] > price_daily['MA'], 'Up', 'Down')
    
    return price_daily, oi_daily

def analyze_merchant_behavior(price_data, merchant_positions, lookback_days=365):
    """Analyze merchant positioning relative to price trends"""
    # Ensure we're only looking at the specified lookback period
    cutoff_date = pd.Timestamp.now(tz='America/New_York') - pd.Timedelta(days=lookback_days)
    
    # Convert price data index to same timezone
    price_data = price_data.copy()
    price_data.index = price_data.index.tz_convert('America/New_York')
    
    # Filter data
    price_data = price_data[price_data.index >= cutoff_date]
    merchant_positions = merchant_positions[
        pd.to_datetime(merchant_positions['Date']).dt.tz_localize('America/New_York') >= cutoff_date
    ]
    
    if price_data.empty or merchant_positions.empty:
        return pd.DataFrame()
    
    # Calculate weekly price changes
    price_weekly = price_data['Close'].resample('W').last()
    price_weekly_pct = price_weekly.pct_change()
    
    # Align merchant positions with price changes
    merchant_positions['Date'] = pd.to_datetime(merchant_positions['Date']).dt.tz_localize('America/New_York')
    merchant_weekly = merchant_positions.set_index('Date').resample('W').last()
    
    # Analyze correlation between price changes and merchant positioning
    correct_positions = []
    for date in merchant_weekly.index:
        if date in price_weekly_pct.index:
            price_change = price_weekly_pct[date]
            merchant_short_pct = merchant_weekly.loc[date, 'Merchant_Short_Pct']
            merchant_long_pct = merchant_weekly.loc[date, 'Merchant_Long_Pct']
            
            # Check if merchants were correctly positioned
            if price_change < 0 and merchant_short_pct > merchant_long_pct:
                correct_positions.append({
                    'Date': date,
                    'Price_Change': price_change * 100,
                    'Position': 'Short',
                    'Short_Pct': merchant_short_pct,
                    'Long_Pct': merchant_long_pct
                })
            elif price_change > 0 and merchant_long_pct > merchant_short_pct:
                correct_positions.append({
                    'Date': date,
                    'Price_Change': price_change * 100,
                    'Position': 'Long',
                    'Short_Pct': merchant_short_pct,
                    'Long_Pct': merchant_long_pct
                })
    
    return pd.DataFrame(correct_positions)

def maintain_signal_history(merchant_positions, signals_df, selected_commodity):
    """Maintain a history of weekly signals"""
    weekly_positions = merchant_positions.set_index('Date').resample('W').last()
    signal_history = []
    
    for date, row in weekly_positions.iterrows():
        signal, reasons = get_position_signal(
            row['Merchant_Short_Pct'],
            row['Merchant_Long_Pct'],
            signals_df,
            selected_commodity
        )
        signal_history.append({
            'Date': date,
            'Signal': signal,
            'Short_Pct': row['Merchant_Short_Pct'],
            'Long_Pct': row['Merchant_Long_Pct'],
            'Reasons': ', '.join(reasons) if reasons else 'No specific trigger'
        })
    
    return pd.DataFrame(signal_history)

# Sidebar for controls
st.sidebar.header("Controls")

# Commodity selection
commodity_symbols = {
    "Crude Oil": "CL=F",
    "Natural Gas": "NG=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Corn": "ZC=F",
    "Soybeans": "ZS=F",
    "Wheat": "ZW=F"
}

selected_commodity = st.sidebar.selectbox(
    "Select Commodity",
    list(commodity_symbols.keys())
)

# Date range selection
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(start_date, end_date),
    max_value=end_date
)

# Chart type selection
chart_type = st.sidebar.radio(
    "Select Chart Type",
    ["Candlestick", "Line"]
)

# Fetch price data
@st.cache_data
def get_price_data(symbol, start_date, end_date):
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)
    return df

# Load data
price_data = get_price_data(commodity_symbols[selected_commodity], date_range[0], date_range[1])
cot_data = get_cftc_data()
signals_df = load_cot_signals()
merchant_positions = get_merchant_positions(cot_data, selected_commodity)

if not merchant_positions.empty:
    # Current signal
    latest_short_pct = merchant_positions['Merchant_Short_Pct'].iloc[-1]
    latest_long_pct = merchant_positions['Merchant_Long_Pct'].iloc[-1]
    latest_signal, signal_reasons = get_position_signal(
        latest_short_pct, latest_long_pct, signals_df, selected_commodity
    )
    
    # Signal history
    signal_history = maintain_signal_history(merchant_positions, signals_df, selected_commodity)
    
    # Merchant behavior analysis
    merchant_analysis = analyze_merchant_behavior(price_data, merchant_positions)
    
    # Display metrics in Bloomberg style
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Merchant Short %", f"{latest_short_pct:.2f}%")
    with col2:
        st.metric("Merchant Long %", f"{latest_long_pct:.2f}%")
    with col3:
        st.metric("Current Signal", latest_signal,
                 delta=", ".join(signal_reasons) if signal_reasons else None)
    with col4:
        st.metric("Open Interest", f"{merchant_positions['Open_Interest'].iloc[-1]:,.0f}")

    # Create main chart
    price_daily, oi_daily = analyze_trend_changes(
        price_data, 
        merchant_positions['Open_Interest'],
        merchant_positions['Date']
    )
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.7, 0.3])

    # Add price chart with Bloomberg-style colors
    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=price_data.index,
                open=price_data['Open'],
                high=price_data['High'],
                low=price_data['Low'],
                close=price_data['Close'],
                name="Price",
                increasing_line_color='#00B8E6',
                decreasing_line_color='#FF3366'
            ),
            row=1, col=1
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=price_data.index,
                y=price_data['Close'],
                name="Price",
                line=dict(color='#00B8E6')
            ),
            row=1, col=1
        )

    # Add 50-day moving average
    fig.add_trace(
        go.Scatter(
            x=price_daily.index,
            y=price_daily['MA'],
            name="50-day MA",
            line=dict(color='#FFB000', dash='dash')
        ),
        row=1, col=1
    )

    # Add Open Interest
    fig.add_trace(
        go.Scatter(
            x=oi_daily.index,
            y=oi_daily['Open_Interest'],
            name="Open Interest",
            line=dict(color='#00FF00')
        ),
        row=2, col=1
    )

    # Update layout with Bloomberg-style colors
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='#001133',
        plot_bgcolor='#001133',
        title=dict(
            text=f"{selected_commodity} Analysis",
            font=dict(color='#FFFFFF')
        ),
        xaxis_title="Date",
        yaxis_title="Price",
        yaxis2_title="Open Interest",
        height=800,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        font=dict(color='#FFFFFF')
    )

    # Display the chart
    st.plotly_chart(fig, use_container_width=True)

    # Display signal history
    st.subheader("Signal History (Weekly)")
    st.dataframe(
        signal_history.sort_values('Date', ascending=False).style.format({
            'Date': lambda x: x.strftime('%Y-%m-%d'),
            'Short_Pct': '{:.2f}%',
            'Long_Pct': '{:.2f}%'
        })
    )

    # Display merchant behavior analysis
    st.subheader("Merchant Position Analysis (Last 365 Days)")
    if not merchant_analysis.empty:
        st.dataframe(
            merchant_analysis.sort_values('Date', ascending=False).style.format({
                'Date': lambda x: x.strftime('%Y-%m-%d'),
                'Price_Change': '{:+.2f}%',
                'Short_Pct': '{:.2f}%',
                'Long_Pct': '{:.2f}%'
            })
        )
        
        # Calculate success rate
        success_rate = len(merchant_analysis) / len(merchant_positions) * 100
        st.info(f"Merchants correctly positioned {success_rate:.1f}% of the time in the last year")
    else:
        st.info("No clear positioning patterns found in the last year")

    # Display monthly extremes
    if not price_data.empty:
        last_month = price_data.last('30D')
        monthly_extremes = pd.DataFrame({
            'Metric': ['Highest Price', 'Lowest Price'],
            'Value': [last_month['High'].max(), last_month['Low'].min()],
            'Date': [last_month['High'].idxmax(), last_month['Low'].idxmin()]
        })
        
        st.subheader("Last Month Price Extremes")
        st.dataframe(monthly_extremes.style.format({
            'Value': '{:.2f}',
            'Date': lambda x: x.strftime('%Y-%m-%d')
        }))

    # Display position tables
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Merchant Positions")
        if not merchant_positions.empty:
            st.dataframe(merchant_positions.style.format({
                'Merchant_Long_Pct': '{:.2f}%',
                'Merchant_Short_Pct': '{:.2f}%',
                'Merchant_Long': '{:,.0f}',
                'Merchant_Short': '{:,.0f}',
                'Open_Interest': '{:,.0f}'
            }))

    with col2:
        if not signals_df[signals_df['Commodity'] == selected_commodity].empty:
            signal_info = signals_df[signals_df['Commodity'] == selected_commodity].iloc[0]
            st.info(f"""
            Signal Ranges for {selected_commodity}:
            - Bullish when Short % is between {signal_info['Bullish_Min']}% and {signal_info['Bullish_Max']}%
            - Bearish when Long % is between {signal_info['Bearish_Min']}% and {signal_info['Bearish_Max']}%
            """)
