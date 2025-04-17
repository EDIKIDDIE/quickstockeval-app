
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import datetime
from webull import webull

# Initialize Webull (no login required for gappers)
wb = webull()

def get_premarket_gappers(count=20, min_volume=500000):
    try:
        gainers = wb.active_gainers(region='us', count=count)
        df = pd.DataFrame(gainers)
        df = df[["ticker", "name", "close", "change", "volume"]]
        df.rename(columns={
            "ticker": "Ticker",
            "name": "Name",
            "close": "Last Price",
            "change": "Change %",
            "volume": "Volume"
        }, inplace=True)
        df = df[df["Volume"] >= min_volume]  # Apply volume filter
        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Error fetching premarket gappers: {e}")
        return pd.DataFrame()
        
st.set_page_config(layout="wide", page_title="QuickStockEval", page_icon=":chart_with_upwards_trend:")
st.title("QuickStockEval – Streamlit Edition")

ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, MSFT)", "AAPL")

@st.cache_data
def get_stock_data(ticker):
    ticker_obj = yf.Ticker(ticker)
    hist = ticker_obj.history(period="6mo")
    info = ticker_obj.info
    return hist, info

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

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Overview", "Chart", "Valuation", "News","Calendar","Gappers"])

with tab1:
    st.write(f"Ticker Data: https://finviz.com/quote.ashx?t={ticker}&p=d")
    st.write(f"Ticker Earning Date: https://www.earningswhispers.com/stocks/{ticker}")
    st.write(f"Hedge Follow Activity: https://www.earningswhispers.com/stocks/{ticker}")

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

with tab2:
    st.markdown("### 6-Month Price Chart")
    hist['MA50'] = hist['Close'].rolling(window=50).mean()
    hist['MA200'] = hist['Close'].rolling(window=200).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='Close'))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['MA50'], mode='lines', name='50MA'))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['MA200'], mode='lines', name='200MA'))
    fig.update_layout(height=400, width=1000)
    st.plotly_chart(fig)

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

with tab6:
    st.header("🚀 Premarket Gappers (Webull)")
    
    col1, col2 = st.columns(2)
    with col1:
        num_stocks = st.slider("Number of top movers to check", 5, 50, 20)
    with col2:
        min_volume = st.number_input("Minimum Volume", value=500000, step=100000)

    gappers_df = get_premarket_gappers(count=num_stocks, min_volume=min_volume)

    if not gappers_df.empty:
        st.dataframe(gappers_df, use_container_width=True)
    else:
        st.warning("No gappers found with the given criteria.")



if st.button("Download PDF Report"):
    path = generate_pdf(info, intrinsic_val, news_list)
    with open(path, "rb") as f:
        st.download_button("Click to Download", f, file_name=path)
