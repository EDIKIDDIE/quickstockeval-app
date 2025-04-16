
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from ta.trend import MACD
from ta.momentum import RSIIndicator

st.set_page_config(page_title="Quick Stock Evaluator", layout="wide")

# --- Helper Functions ---
@st.cache_data
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="6mo", interval="1d")
    info = stock.info
    return stock, hist, info

# --- Sidebar ---
st.sidebar.title("📈 Quick Stock Evaluator")
tickers = st.sidebar.text_input("Enter Ticker(s) separated by comma", "AAPL,MSFT").upper().split(",")

chart_type = st.sidebar.selectbox("Chart Type", ["Candlestick", "Line"])
show_indicators = st.sidebar.multiselect("Indicators", ["EMA 21", "EMA 34", "EMA 89", "EMA 200"], default=["EMA 21", "EMA 34"])
ema_colors = {
    "EMA 21": st.sidebar.color_picker("EMA 21 Color", "#FF5733"),
    "EMA 34": st.sidebar.color_picker("EMA 34 Color", "#33FF57"),
    "EMA 89": st.sidebar.color_picker("EMA 89 Color", "#3357FF"),
    "EMA 200": st.sidebar.color_picker("EMA 200 Color", "#8E44AD")
}

# --- Main Tabs ---
tab1, tab2 = st.tabs(["📊 Overview", "📰 News"])

# --- Overview Tab ---
with tab1:
    for ticker in tickers:
        ticker = ticker.strip()
        if not ticker:
            continue
        st.header(f"{ticker} Overview")
        stock, hist, info = get_stock_data(ticker)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Name:** {info.get('longName', '-')}")
            st.markdown(f"**Sector:** {info.get('sector', '-')}")
            st.markdown(f"**Industry:** {info.get('industry', '-')}")
            st.markdown(f"**Market Cap:** ${info.get('marketCap', 0):,.0f}")
            st.markdown(f"**Free Cash Flow:** ${info.get('freeCashflow', 0):,.0f}")
        with col2:
            st.markdown(f"**P/E Ratio:** {info.get('trailingPE', '-')}")
            st.markdown(f"**Forward P/E:** {info.get('forwardPE', '-')}")
            st.markdown(f"**PEG Ratio:** {info.get('pegRatio', '-')}")
            st.markdown(f"**Beta:** {info.get('beta', '-')}")

        try:
            holders = stock.get_institutional_holders()
            if holders is not None and not holders.empty:
                st.subheader("Top Institutional Holders")
                st.dataframe(holders.head(5))
        except:
            st.info("Holder data not available.")

        fig = go.Figure()

        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=hist.index, open=hist['Open'], high=hist['High'],
                low=hist['Low'], close=hist['Close'], name='Candlestick'))
        else:
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='Price'))

        for ema in show_indicators:
            period = int(ema.split()[1])
            color = ema_colors.get(ema, "#000000")
            hist[ema] = hist['Close'].ewm(span=period).mean()
            fig.add_trace(go.Scatter(x=hist.index, y=hist[ema], mode='lines', name=ema, line=dict(color=color)))

        fig.update_layout(title=f"{ticker} Price Chart", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Technical Indicators")
        rsi = RSIIndicator(hist['Close']).rsi()
        macd = MACD(hist['Close']).macd_diff()

        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(x=hist.index, y=rsi, name="RSI"))
        rsi_fig.update_layout(title="RSI", height=250)
        st.plotly_chart(rsi_fig, use_container_width=True)

        macd_fig = go.Figure()
        macd_fig.add_trace(go.Scatter(x=hist.index, y=macd, name="MACD Histogram"))
        macd_fig.update_layout(title="MACD", height=250)
        st.plotly_chart(macd_fig, use_container_width=True)

# --- News Section ---
with tab2:
    for ticker in tickers:
        ticker = ticker.strip()
        if not ticker:
            continue
        st.subheader(f"{ticker} News Feed")
        try:
            news = yf.Ticker(ticker).news
            if news:
                for item in news[:5]:
                    st.markdown(f"**[{item['title']}]({item['link']})**  
*{item['publisher']}*")
            else:
                st.info("No news found.")
        except:
            st.warning("News feed unavailable.")
