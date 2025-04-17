
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import datetime

st.set_page_config(layout="wide", page_title="QuickStockEval", page_icon=":chart_with_upwards_trend:")
st.title("QuickStockEval – Streamlit Edition")

ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, MSFT)", "AAPL")

st.sidebar.markdown("### Chart Settings")

selected_period = st.sidebar.selectbox(
    "Time Range",
    ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
    index=4
)

selected_interval = st.sidebar.selectbox(
    "Candle Interval",
    ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"],
    index=5
)

# Optional warning for invalid combos
if selected_interval == "1m" and selected_period not in ["1d", "5d", "7d"]:
    st.warning("⚠️ 1-minute interval only works with time ranges up to 7 days on Yahoo Finance.")


@st.cache_data
def get_stock_data(ticker, period, interval):
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period, interval=interval)
    info = stock.info
    return stock, hist, info


@st.cache_data
def get_news(ticker):
    url = f"https://finance.yahoo.com/quote/{ticker}?p={ticker}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    headlines = soup.find_all("h3", limit=5)
    news = []
    for h in headlines:
        link = h.find("a")
        if link:
            news.append({
                "title": link.text.strip(),
                "url": "https://finance.yahoo.com" + link.get("href")
            })
    return news

@st.cache_data
def dcf_valuation(eps, growth_rate=0.1, discount_rate=0.12, years=5):
    cash_flows = [eps * ((1 + growth_rate) ** i) for i in range(1, years+1)]
    present_values = [cf / ((1 + discount_rate) ** i) for i, cf in enumerate(cash_flows, start=1)]
    terminal_value = cash_flows[-1] * (1 + growth_rate) / (discount_rate - growth_rate)
    terminal_discounted = terminal_value / ((1 + discount_rate) ** years)
    intrinsic_value = sum(present_values) + terminal_discounted
    return intrinsic_value

hist, info = get_stock_data(ticker)
news_list = get_news(ticker)

if 'shortName' in info:
    st.subheader(f"{info['shortName']} ({ticker.upper()})")
else:
    st.subheader(f"({ticker.upper()})")

tab1, tab2, tab3, tab4,tab5 = st.tabs(["Overview", "Chart", "Valuation", "News","Calendar"])

with tab1:
    st.write(f"Ticker Data: https://finviz.com/quote.ashx?t={ticker}&p=d")
    st.write(f"Ticker Earning Date: https://www.earningswhispers.com/stocks/{ticker}")
    st.write(f"Hedge Follow Activity: https://hedgefollow.com/stocks/{ticker}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current Price", f"${info.get('currentPrice')}")
        st.metric("Market Cap", info.get("marketCap"))
        st.metric("P/E Ratio", info.get("trailingPE"))
    with col2:
        st.metric("P/B Ratio", info.get("priceToBook"))
        st.metric("ROE", f"{round(info.get('returnOnEquity', 0)*100, 2)}%")
        st.metric("Debt/Equity", info.get("debtToEquity"))
    with col3:
        st.metric("Current Ratio", info.get("currentRatio"))
        st.metric("EPS", info.get("trailingEps"))
        st.metric("Free Cash Flow", info.get("freeCashflow"))

    sector_benchmarks = {
        'Technology': {'pe': 25, 'pb': 6, 'roe': 18},
        'Healthcare': {'pe': 20, 'pb': 5, 'roe': 15},
        'Financial Services': {'pe': 12, 'pb': 1.5, 'roe': 10},
        'Energy': {'pe': 10, 'pb': 1.2, 'roe': 12},
        'Consumer Cyclical': {'pe': 18, 'pb': 3.5, 'roe': 14},
    }

    sector = info.get('sector')
    bench = sector_benchmarks.get(sector, None)

    if bench:
        st.markdown(f"### {sector} Sector Comparison")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("P/E", f"{info.get('trailingPE')} vs {bench['pe']}")
        with col2:
            st.metric("P/B", f"{info.get('priceToBook')} vs {bench['pb']}")
        with col3:
            st.metric("ROE", f"{round(info.get('returnOnEquity', 0)*100, 2)}% vs {bench['roe']}%")

stock, hist, info = get_stock_data(ticker, selected_period, selected_interval)

with tab2:
    st.markdown("### 6-Month Price Chart with EMAs, Volume, RSI, and MACD")

    chart_type = st.radio("Chart Type", ["Candlestick", "Line"], horizontal=True)

    show_indicators = st.multiselect(
        "Select EMAs to Display",
        ["EMA 21", "EMA 34", "EMA 89", "EMA 200"],
        default=["EMA 21", "EMA 34", "EMA 89", "EMA 200"]
    )

    ema_colors = {}
    for ema in show_indicators:
        ema_colors[ema] = st.color_picker(f"Pick color for {ema}", "#0000FF")

    # Calculate all EMAs
    ema_periods = [21, 34, 89, 200]
    for period in ema_periods:
        hist[f"EMA {period}"] = hist['Close'].ewm(span=period).mean()

    # Calculate RSI and MACD using ta
    from ta.momentum import RSIIndicator
    from ta.trend import MACD

    rsi = RSIIndicator(close=hist['Close']).rsi()
    macd = MACD(close=hist['Close'])
    macd_line = macd.macd()
    signal_line = macd.macd_signal()
    macd_hist = macd.macd_diff()

    # === Price Chart ===
    price_fig = go.Figure()

    if chart_type == "Candlestick":
        price_fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Candlestick'
        ))
    else:
        price_fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'],
            mode='lines',
            name='Close',
            line=dict(color='black')
        ))

    for ema in show_indicators:
        period = int(ema.split()[1])
        price_fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist[f"EMA {period}"],
            mode='lines',
            name=ema,
            line=dict(color=ema_colors.get(ema, "#000000"))
        ))

    price_fig.update_layout(height=500, width=1000, title="Price + EMAs", xaxis_title="Date", yaxis_title="Price")
    st.plotly_chart(price_fig, use_container_width=True)

    # === Volume Chart ===
    vol_fig = go.Figure()
    vol_fig.add_trace(go.Bar(
        x=hist.index,
        y=hist['Volume'],
        name='Volume',
        marker_color='gray',
        opacity=0.5
    ))
    vol_fig.update_layout(height=200, title="Volume", xaxis_title="Date", yaxis_title="Volume")
    st.plotly_chart(vol_fig, use_container_width=True)

    # === RSI Chart ===
    rsi_fig = go.Figure()
    rsi_fig.add_trace(go.Scatter(x=hist.index, y=rsi, name="RSI", line=dict(color='orange')))
    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
    rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")
    rsi_fig.update_layout(height=200, title="RSI", xaxis_title="Date", yaxis_title="RSI")
    st.plotly_chart(rsi_fig, use_container_width=True)

    # === MACD Chart ===
    macd_fig = go.Figure()
    macd_fig.add_trace(go.Scatter(x=hist.index, y=macd_line, name="MACD", line=dict(color='blue')))
    macd_fig.add_trace(go.Scatter(x=hist.index, y=signal_line, name="Signal", line=dict(color='red')))
    macd_fig.add_trace(go.Bar(x=hist.index, y=macd_hist, name="Histogram", marker_color='gray'))
    macd_fig.update_layout(height=250, title="MACD", xaxis_title="Date", yaxis_title="MACD")
    st.plotly_chart(macd_fig, use_container_width=True)


with tab3:
    st.markdown("### Intrinsic Value Estimate (EPS-based DCF)")
    st.write(f"Check DCF: https://www.gurufocus.com/stock/{ticker}/dcf")
    eps = info.get('trailingEps') or 0
    intrinsic_val = dcf_valuation(eps)
    curr_price = info.get('currentPrice')

    st.write(f"Estimated Fair Value: **${round(intrinsic_val, 2)}**")
    if curr_price and intrinsic_val:
        if intrinsic_val > curr_price:
            st.success(f"The stock appears **undervalued** by ~{round((intrinsic_val - curr_price)/curr_price * 100, 2)}%")
        else:
            st.warning(f"The stock appears **overvalued** by ~{round((curr_price - intrinsic_val)/curr_price * 100, 2)}%")

with tab4:
    st.markdown("### Latest News")
    for article in news_list:
        st.markdown(f"[{article['title']}]({article['url']})")

def generate_pdf(info, intrinsic_val, news):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt=f"QuickStockEval Report – {ticker.upper()}", ln=1, align='C')

    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=f"Date: {datetime.date.today()}", ln=1)
    pdf.cell(200, 10, txt=f"Company: {info.get('shortName')}", ln=1)
    pdf.cell(200, 10, txt=f"Current Price: ${info.get('currentPrice')}", ln=1)
    pdf.cell(200, 10, txt=f"P/E: {info.get('trailingPE')}  |  ROE: {round(info.get('returnOnEquity', 0)*100, 2)}%", ln=1)
    pdf.cell(200, 10, txt=f"Debt/Equity: {info.get('debtToEquity')}/100  |  FCF: {info.get('freeCashflow')}", ln=1)
    pdf.cell(200, 10, txt=f"Intrinsic Value (DCF): ${round(intrinsic_val, 2)}", ln=1)

    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Recent News", ln=1)
    pdf.set_font("Arial", '', 11)
    for article in news:
        pdf.multi_cell(0, 10, article['title'])

    filepath = f"{ticker.upper()}_report.pdf"
    pdf.output(filepath)
    return filepath

with tab5:
   st.write(f"Event Schedule: https://tradingeconomics.com/calendar")
   st.write(f"Today Earning List: https://www.earningswhispers.com/calendar/{datetime.date.today()}")


if st.button("Download PDF Report"):
    path = generate_pdf(info, intrinsic_val, news_list)
    with open(path, "rb") as f:
        st.download_button("Click to Download", f, file_name=path)
