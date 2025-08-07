import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.title("Stan Weinstein's Stage Analysis for Korean Stocks")

# --- Step 2: User Input ---
ticker_input = st.text_input("Enter the stock ticker (e.g., 005930.KS for Samsung Electronics)", "005930.KS")
analyze_button = st.button("Analyze")

# --- Helper function to fetch and process data ---
def get_stock_data(ticker):
    try:
        # Download data for the last 2 years to have enough data for 150-day MA
        data = yf.download(ticker, period="2y", interval="1d")
        if data.empty:
            st.error(f"No data found for ticker {ticker}. Please check the ticker symbol (e.g., '005930.KS').")
            return None

        # Calculate moving averages
        # 30-week MA is approximately 150 days (30 * 5 trading days)
        # We also calculate 50-day MA for shorter term trend
        data['SMA50'] = data['Close'].rolling(window=50).mean()
        data['SMA150'] = data['Close'].rolling(window=150).mean()

        return data
    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return None

def get_stage_and_recommendation(data):
    """
    Determines the stock's current stage based on Stan Weinstein's method.
    """
    if data is None or len(data) < 151: # Need at least 151 days for SMA150 and slope
        return "Not enough data", "N/A"

    latest = data.iloc[-1]

    # Calculate SMA150 slope (e.g., over the last month - 22 trading days)
    # A simple way is to check the percentage change.
    if len(data) < 150 + 22:
         sma150_slope = 0 # Can't calculate slope yet
    else:
        sma150_prev = data['SMA150'].iloc[-22]
        if sma150_prev > 0:
            sma150_slope = (latest['SMA150'] - sma150_prev) / sma150_prev
        else:
            sma150_slope = 0

    # Define conditions for each stage
    price = latest['Close']
    sma50 = latest['SMA50']
    sma150 = latest['SMA150']

    # Stage 2: Advancing Stage (The ideal time to buy)
    is_stage_2 = price > sma150 and sma50 > sma150 and sma150_slope > 0.01

    # Stage 4: Declining Stage (The time to sell or avoid)
    is_stage_4 = price < sma150 and sma50 < sma150 and sma150_slope < -0.01

    # Stage 1: Basing Area (Accumulation, neutral)
    is_stage_1 = abs((price - sma150) / sma150) < 0.1 and abs(sma150_slope) < 0.02

    # Stage 3: Top Area (Distribution, caution)
    is_stage_3 = abs((price - sma150) / sma150) < 0.1 and abs(sma150_slope) < 0.02 and price > sma150

    if is_stage_2:
        return "Stage 2: Advancing Stage", "Buy / Hold"
    elif is_stage_4:
        return "Stage 4: Declining Stage", "Sell / Avoid"
    elif is_stage_3:
        return "Stage 3: Top Area", "Caution / Reduce Position"
    elif is_stage_1:
        return "Stage 1: Basing Area", "Neutral / Accumulate"
    else:
        return "Indeterminate Stage", "Neutral / Hold"

if analyze_button:
    st.write(f"Analyzing {ticker_input}...")
    data = get_stock_data(ticker_input)

    if data is not None:
        st.success("Data loaded and processed successfully!")

        stage, recommendation = get_stage_and_recommendation(data)

        st.subheader(f"Current Analysis: {stage}")

        if "Buy" in recommendation:
            st.success(f"Recommendation: {recommendation}")
        elif "Sell" in recommendation or "Caution" in recommendation:
            st.warning(f"Recommendation: {recommendation}")
        else:
            st.info(f"Recommendation: {recommendation}")

        # --- Visualize the data ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='Close Price', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name='50-Day SMA', line=dict(color='orange', dash='dash')))
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA150'], name='150-Day SMA', line=dict(color='red', dash='longdash')))

        fig.update_layout(
            title=f"Price Chart for {ticker_input}",
            xaxis_title="Date",
            yaxis_title="Price",
            legend_title="Legend"
        )
        st.plotly_chart(fig, use_container_width=True)
