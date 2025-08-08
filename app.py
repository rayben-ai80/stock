import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from pykrx import stock
import numpy as np

# --- 데이터 로딩 및 캐싱 ---
@st.cache_data
def get_kr_stock_info():
    """
    KOSPI 및 KOSDAQ 시장의 모든 주식 티커와 이름을 가져옵니다.
    종목명을 티커로 매핑하는 사전과 시장 조회를 위한 사전을 반환합니다.
    """
    name_to_ticker = {}
    ticker_to_market = {}

    for market in ["KOSPI", "KOSDAQ"]:
        tickers = stock.get_market_ticker_list(market=market)
        for ticker in tickers:
            name = stock.get_market_ticker_name(ticker)
            name_to_ticker[name] = ticker
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            ticker_to_market[ticker] = suffix

    return name_to_ticker, ticker_to_market

def get_ticker_from_input(user_input, name_map, market_map):
    """
    사용자 입력(종목명 또는 티커)으로부터 유효한 yfinance 티커를 찾습니다.
    """
    # 입력이 직접 티커인 경우
    if user_input in market_map:
        return user_input + market_map[user_input]

    # 입력이 종목명인 경우
    if user_input in name_map:
        ticker = name_map[user_input]
        return ticker + market_map[ticker]

    # 입력이 yfinance 티커 형식인 경우 (예: 005930.KS)
    if "." in user_input and user_input.split('.')[0] in market_map:
        return user_input

    return None

# --- 데이터 가져오기 및 처리 헬퍼 함수 ---
def get_stock_data(ticker):
    try:
        # 150일 이동평균을 위해 충분한 데이터를 다운로드 (2년)
        data = yf.download(ticker, period="2y", interval="1d")
        if data.empty:
            st.error(f"티커 {ticker}에 대한 데이터를 찾을 수 없습니다. 티커를 확인해주세요 (예: '005930.KS').")
            return None

        # 이동평균 계산
        data['SMA50'] = data['Close'].rolling(window=50).mean()
        data['SMA150'] = data['Close'].rolling(window=150).mean() # 30주 이동평균은 약 150일

        return data
    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return None

def get_stage_and_recommendation(data):
    """
    스탠 와인스타인의 방법에 따라 주식의 현재 단계를 결정합니다.
    """
    if data is None or len(data) < 151:
        return "데이터 부족", "N/A"

    # .iloc[-1]을 사용하여 마지막 행의 값을 스칼라로 가져옵니다.
    price = data['Close'].iloc[-1]
    sma50 = data['SMA50'].iloc[-1]
    sma150 = data['SMA150'].iloc[-1]

    # 롤링 평균으로 인한 NaN 값을 처리합니다.
    if pd.isna(price) or pd.isna(sma50) or pd.isna(sma150):
        return "분석을 위한 데이터 부족", "N/A"

    # 150일 이동평균의 기울기 계산
    if len(data) < 150 + 22:
         sma150_slope = 0
    else:
        sma150_prev = data['SMA150'].iloc[-22]
        if sma150_prev > 0 and not pd.isna(sma150_prev):
            sma150_slope = (sma150 - sma150_prev) / sma150_prev
        else:
            sma150_slope = 0

    # 각 단계에 대한 조건 정의
    is_stage_2 = price > sma150 and sma50 > sma150 and sma150_slope > 0.01
    is_stage_4 = price < sma150 and sma50 < sma150 and sma150_slope < -0.01
    is_flat_zone = abs((price - sma150) / sma150) < 0.1 and abs(sma150_slope) < 0.02 if sma150 > 0 else False

    if is_stage_2:
        return "2단계: 상승 국면", "매수 / 보유"
    elif is_stage_4:
        return "4단계: 하락 국면", "매도 / 회피"
    elif is_flat_zone:
        if price > sma150:
            return "3단계: 정점 영역", "주의 / 비중 축소"
        else:
            return "1단계: 기반 다지기", "중립 / 관망"
    else:
        return "단계를 알 수 없음", "중립 / 관망"

# --- 메인 앱 ---
st.title("스탠 와인스타인 단계 분석 대시보드")

# 주식 정보 로드
name_map, market_map = get_kr_stock_info()

# --- 사용자 입력 ---
user_input = st.text_input("종목명 또는 티커를 입력하세요 (예: 삼성전자, 005930)", "삼성전자")
analyze_button = st.button("분석하기")

if analyze_button:
    final_ticker = get_ticker_from_input(user_input, name_map, market_map)

    if final_ticker:
        st.write(f"'{user_input}' ({final_ticker}) 분석 중...")
        data = get_stock_data(final_ticker)

        if data is not None:
            st.success("데이터를 성공적으로 불러왔습니다!")
            stage, recommendation = get_stage_and_recommendation(data)

            st.subheader(f"현재 분석: {stage}")

            if "매수" in recommendation:
                st.success(f"추천: {recommendation}")
            elif "매도" in recommendation or "주의" in recommendation:
                st.warning(f"추천: {recommendation}")
            else:
                st.info(f"추천: {recommendation}")

            # --- 데이터 시각화 ---
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='종가', line=dict(color='blue')))
            fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name='50일 이동평균', line=dict(color='orange', dash='dash')))
            fig.add_trace(go.Scatter(x=data.index, y=data['SMA150'], name='150일 이동평균', line=dict(color='red', dash='longdash')))

            fig.update_layout(
                title=f"'{user_input}' 가격 차트",
                xaxis_title="날짜",
                yaxis_title="가격 (KRW)",
                legend_title="범례"
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(f"'{user_input}' 종목을 찾을 수 없습니다. 올바른 종목명 또는 티커를 입력해주세요.")
