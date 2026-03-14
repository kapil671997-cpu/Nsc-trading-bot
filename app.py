import os, math, time, threading, logging, json
import numpy as np
import yfinance as yf
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, date, timedelta
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════
# TELEGRAM CONFIG
# ═══════════════════════════════════
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN",  "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID= os.environ.get("TELEGRAM_CHAT_ID","YOUR_CHAT_ID_HERE")
SERVER_URL      = os.environ.get("SERVER_URL", "https://nsc-trading-bot.onrender.com")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# ═══════════════════════════════════
# INSTRUMENTS
# ═══════════════════════════════════
STOCKS = {
    # LARGE CAP
    'RELIANCE.NS': {'name':'Reliance Industries','cat':'LARGE','sec':'Energy'},
    'TCS.NS':      {'name':'TCS',                'cat':'LARGE','sec':'IT'},
    'HDFCBANK.NS': {'name':'HDFC Bank',          'cat':'LARGE','sec':'Banking'},
    'INFY.NS':     {'name':'Infosys',            'cat':'LARGE','sec':'IT'},
    'ICICIBANK.NS':{'name':'ICICI Bank',         'cat':'LARGE','sec':'Banking'},
    'SBIN.NS':     {'name':'SBI',                'cat':'LARGE','sec':'Banking'},
    'HINDUNILVR.NS':{'name':'HUL',               'cat':'LARGE','sec':'FMCG'},
    'ITC.NS':      {'name':'ITC',                'cat':'LARGE','sec':'FMCG'},
    'KOTAKBANK.NS':{'name':'Kotak Bank',         'cat':'LARGE','sec':'Banking'},
    'LT.NS':       {'name':'L&T',                'cat':'LARGE','sec':'Infra'},
    'AXISBANK.NS': {'name':'Axis Bank',          'cat':'LARGE','sec':'Banking'},
    'BAJFINANCE.NS':{'name':'Bajaj Finance',     'cat':'LARGE','sec':'NBFC'},
    'MARUTI.NS':   {'name':'Maruti Suzuki',      'cat':'LARGE','sec':'Auto'},
    'TATAMOTORS.NS':{'name':'Tata Motors',       'cat':'LARGE','sec':'Auto'},
    'SUNPHARMA.NS':{'name':'Sun Pharma',         'cat':'LARGE','sec':'Pharma'},
    'HCLTECH.NS':  {'name':'HCL Tech',           'cat':'LARGE','sec':'IT'},
    'WIPRO.NS':    {'name':'Wipro',              'cat':'LARGE','sec':'IT'},
    'ONGC.NS':     {'name':'ONGC',               'cat':'LARGE','sec':'Energy'},
    'NTPC.NS':     {'name':'NTPC',               'cat':'LARGE','sec':'Power'},
    'BHARTIARTL.NS':{'name':'Airtel',            'cat':'LARGE','sec':'Telecom'},
    'TATASTEEL.NS':{'name':'Tata Steel',         'cat':'LARGE','sec':'Metal'},
    'ADANIENT.NS': {'name':'Adani Ent',          'cat':'LARGE','sec':'Infra'},
    'HINDALCO.NS': {'name':'Hindalco',           'cat':'LARGE','sec':'Metal'},
    'JSWSTEEL.NS': {'name':'JSW Steel',          'cat':'LARGE','sec':'Metal'},
    'DRREDDY.NS':  {'name':'Dr Reddy',           'cat':'LARGE','sec':'Pharma'},
    'CIPLA.NS':    {'name':'Cipla',              'cat':'LARGE','sec':'Pharma'},
    'TITAN.NS':    {'name':'Titan',              'cat':'LARGE','sec':'Consumer'},
    'ASIANPAINT.NS':{'name':'Asian Paints',      'cat':'LARGE','sec':'Chemical'},
    'BAJAJ-AUTO.NS':{'name':'Bajaj Auto',        'cat':'LARGE','sec':'Auto'},
    'HEROMOTOCO.NS':{'name':'Hero MotoCorp',     'cat':'LARGE','sec':'Auto'},
    # MID CAP
    'ZOMATO.NS':   {'name':'Zomato',             'cat':'MID','sec':'Tech'},
    'PNB.NS':      {'name':'PNB',                'cat':'MID','sec':'Banking'},
    'BANKBARODA.NS':{'name':'Bank of Baroda',    'cat':'MID','sec':'Banking'},
    'CANBK.NS':    {'name':'Canara Bank',        'cat':'MID','sec':'Banking'},
    'IRCTC.NS':    {'name':'IRCTC',              'cat':'MID','sec':'Travel'},
    'NMDC.NS':     {'name':'NMDC',               'cat':'MID','sec':'Mining'},
    'MUTHOOTFIN.NS':{'name':'Muthoot Fin',       'cat':'MID','sec':'NBFC'},
    'LUPIN.NS':    {'name':'Lupin',              'cat':'MID','sec':'Pharma'},
    'MARICO.NS':   {'name':'Marico',             'cat':'MID','sec':'FMCG'},
    'COLPAL.NS':   {'name':'Colgate',            'cat':'MID','sec':'FMCG'},
    'DABUR.NS':    {'name':'Dabur',              'cat':'MID','sec':'FMCG'},
    'ASHOKLEY.NS': {'name':'Ashok Leyland',      'cat':'MID','sec':'Auto'},
    'MPHASIS.NS':  {'name':'Mphasis',            'cat':'MID','sec':'IT'},
    'COFORGE.NS':  {'name':'Coforge',            'cat':'MID','sec':'IT'},
    'APOLLOTYRE.NS':{'name':'Apollo Tyres',      'cat':'MID','sec':'Auto'},
    # SMALL CAP
    'RBLBANK.NS':  {'name':'RBL Bank',           'cat':'SMALL','sec':'Banking'},
    'YESBANK.NS':  {'name':'Yes Bank',           'cat':'SMALL','sec':'Banking'},
    'TANLA.NS':    {'name':'Tanla Platforms',    'cat':'SMALL','sec':'IT'},
    'KPITTECH.NS': {'name':'KPIT Tech',          'cat':'SMALL','sec':'IT'},
    'ESCORTS.NS':  {'name':'Escorts Kubota',     'cat':'SMALL','sec':'Auto'},
}

# ═══════════════════════════════════
# TECHNICAL INDICATORS
# ═══════════════════════════════════
def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def calc_macd(prices, fast=12, slow=26, signal=9):
    ema_fast   = prices.ewm(span=fast).mean()
    ema_slow   = prices.ewm(span=slow).mean()
    macd_line  = ema_fast - ema_slow
    signal_line= macd_line.ewm(span=signal).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger(prices, period=20, std=2):
    sma     = prices.rolling(period).mean()
    std_dev = prices.rolling(period).std()
    return sma + (std * std_dev), sma, sma - (std * std_dev)

def calc_vwap(df):
    """Volume Weighted Average Price"""
    try:
        typical = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = (typical * df['Volume']).cumsum() / df['Volume'].cumsum()
        return float(vwap.iloc[-1])
    except:
        return float(df['Close'].iloc[-1])

def calc_supertrend(df, period=7, multiplier=3):
    """Supertrend Indicator"""
    try:
        hl2   = (df['High'] + df['Low']) / 2
        atr   = df['High'].rolling(period).max() - df['Low'].rolling(period).min()
        upper = hl2 + (multiplier * atr)
        lower = hl2 - (multiplier * atr)
        close = df['Close']
        supertrend = [True] * len(df)
        for i in range(1, len(df)):
            if close.iloc[i] > upper.iloc[i-1]:
                supertrend[i] = True
            elif close.iloc[i] < lower.iloc[i-1]:
                supertrend[i] = False
            else:
                supertrend[i] = supertrend[i-1]
        return supertrend[-1], round(float(lower.iloc[-1]), 2), round(float(upper.iloc[-1]), 2)
    except:
        return True, 0, 0

def calc_support_resistance(df, window=20):
    """Calculate Support and Resistance levels"""
    try:
        recent = df.tail(window)
        support    = round(float(recent['Low'].min()), 2)
        resistance = round(float(recent['High'].max()), 2)
        pivot      = round((float(df['High'].iloc[-1]) + float(df['Low'].iloc[-1]) + float(df['Close'].iloc[-1])) / 3, 2)
        return support, resistance, pivot
    except:
        p = float(df['Close'].iloc[-1])
        return p * 0.97, p * 1.03, p

# ═══════════════════════════════════
# CANDLESTICK PATTERN DETECTION
# ═══════════════════════════════════
def detect_patterns(df):
    """Detect candlestick patterns"""
    patterns = []
    if len(df) < 3:
        return patterns

    o  = df['Open'].values
    h  = df['High'].values
    l  = df['Low'].values
    c  = df['Close'].values

    # Last 3 candles
    o1,o2,o3 = o[-3], o[-2], o[-1]
    h1,h2,h3 = h[-3], h[-2], h[-1]
    l1,l2,l3 = l[-3], l[-2], l[-1]
    c1,c2,c3 = c[-3], c[-2], c[-1]

    body3   = abs(c3 - o3)
    range3  = h3 - l3 + 1e-9
    body_pct= body3 / range3

    # Doji
    if body_pct < 0.1:
        patterns.append({"name":"Doji","type":"NEUTRAL","desc":"Market confused — wait karo","emoji":"😐"})

    # Hammer (Bullish)
    lower_wick = min(o3, c3) - l3
    upper_wick = h3 - max(o3, c3)
    if lower_wick > 2 * body3 and upper_wick < body3 and c3 > o3:
        patterns.append({"name":"Hammer","type":"BULLISH","desc":"Reversal aane wala hai — BUY ready karo","emoji":"🔨"})

    # Shooting Star (Bearish)
    if upper_wick > 2 * body3 and lower_wick < body3 and c3 < o3:
        patterns.append({"name":"Shooting Star","type":"BEARISH","desc":"Overbought — SELL ready karo","emoji":"💫"})

    # Bullish Engulfing
    if c2 < o2 and c3 > o3 and o3 < c2 and c3 > o2:
        patterns.append({"name":"Bullish Engulfing","type":"BULLISH","desc":"Strong reversal — BUY signal","emoji":"🟢"})

    # Bearish Engulfing
    if c2 > o2 and c3 < o3 and o3 > c2 and c3 < o2:
        patterns.append({"name":"Bearish Engulfing","type":"BEARISH","desc":"Strong reversal — SELL signal","emoji":"🔴"})

    # Morning Star (Bullish - 3 candle)
    if c1 < o1 and body_pct < 0.3 and c3 > o3 and c3 > (o1 + c1) / 2:
        patterns.append({"name":"Morning Star","type":"BULLISH","desc":"Bullish trend shuru — 3 candle pattern","emoji":"🌟"})

    # Evening Star (Bearish - 3 candle)
    if c1 > o1 and body_pct < 0.3 and c3 < o3 and c3 < (o1 + c1) / 2:
        patterns.append({"name":"Evening Star","type":"BEARISH","desc":"Bearish trend shuru — SELL ready","emoji":"🌙"})

    # Three White Soldiers (Bullish)
    if c1 > o1 and c2 > o2 and c3 > o3 and c3 > c2 > c1:
        patterns.append({"name":"Three White Soldiers","type":"BULLISH","desc":"Bahut strong uptrend — paisa lagao","emoji":"💪"})

    # Three Black Crows (Bearish)
    if c1 < o1 and c2 < o2 and c3 < o3 and c3 < c2 < c1:
        patterns.append({"name":"Three Black Crows","type":"BEARISH","desc":"Bahut strong downtrend — bacho","emoji":"🦅"})

    # Marubozu (Strong candle)
    if body_pct > 0.9 and c3 > o3:
        patterns.append({"name":"Bullish Marubozu","type":"BULLISH","desc":"Buyers ka full control — strong BUY","emoji":"🚀"})
    elif body_pct > 0.9 and c3 < o3:
        patterns.append({"name":"Bearish Marubozu","type":"BEARISH","desc":"Sellers ka full control — strong SELL","emoji":"💣"})

    return patterns

# ═══════════════════════════════════
# NEXT CANDLE PREDICTION
# ═══════════════════════════════════
def predict_next_candle(df, score, patterns, rsi_val, macd_val, vol_ratio):
    """AI-based next candle prediction"""
    try:
        close  = df['Close']
        highs  = df['High']
        lows   = df['Low']
        price  = float(close.iloc[-1])

        # ATR for range prediction
        atr = float((highs - lows).rolling(14).mean().iloc[-1])

        # Recent volatility
        returns   = close.pct_change().dropna()
        recent_vol= float(returns.tail(10).std()) * price

        # Direction probability based on score
        bull_score = 0
        bear_score = 0

        if score >= 5:   bull_score += 40
        elif score >= 2: bull_score += 25
        elif score <= -5: bear_score += 40
        elif score <= -2: bear_score += 25

        if rsi_val < 40:  bull_score += 15
        elif rsi_val > 65: bear_score += 15

        if macd_val > 0:  bull_score += 15
        else:             bear_score += 15

        if vol_ratio > 1.5: bull_score += 10

        for p in patterns:
            if p['type'] == 'BULLISH': bull_score += 12
            elif p['type'] == 'BEARISH': bear_score += 12

        total = bull_score + bear_score + 1e-9
        bull_prob = min(90, max(10, int(bull_score / total * 100)))
        bear_prob = 100 - bull_prob

        # Price range prediction
        if bull_prob > 55:
            pred_direction = "GREEN 🟢"
            pred_min = round(price, 2)
            pred_max = round(price + atr * 0.8, 2)
            pred_center = round(price + atr * 0.4, 2)
        elif bear_prob > 55:
            pred_direction = "RED 🔴"
            pred_min = round(price - atr * 0.8, 2)
            pred_max = round(price, 2)
            pred_center = round(price - atr * 0.4, 2)
        else:
            pred_direction = "NEUTRAL 😐"
            pred_min = round(price - atr * 0.3, 2)
            pred_max = round(price + atr * 0.3, 2)
            pred_center = round(price, 2)

        # Candle size prediction
        if vol_ratio > 2:   size = "BADA candle (High Volume)"
        elif vol_ratio > 1.2: size = "MEDIUM candle"
        else:               size = "CHOTA candle (Low Volume)"

        return {
            'direction':   pred_direction,
            'probability': bull_prob if bull_prob > bear_prob else bear_prob,
            'bull_prob':   bull_prob,
            'bear_prob':   bear_prob,
            'min_price':   pred_min,
            'max_price':   pred_max,
            'center_price':pred_center,
            'size':        size,
            'atr':         round(atr, 2),
        }
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return None

# ═══════════════════════════════════
# HEALTH SCORE CARD
# ═══════════════════════════════════
def calc_health_score(rsi_val, macd_val, vol_ratio, score, supertrend_bull, bb_pct):
    """Stock health score out of 10"""
    h = 5.0
    # RSI health
    if 45 <= rsi_val <= 65: h += 1.5
    elif 35 <= rsi_val <= 75: h += 0.5
    else: h -= 1.0
    # MACD health
    if macd_val > 0: h += 1.0
    else: h -= 0.5
    # Volume health
    if vol_ratio > 1.2: h += 0.5
    elif vol_ratio < 0.5: h -= 0.5
    # Score health
    h += min(1.5, max(-1.5, score * 0.2))
    # Supertrend
    if supertrend_bull: h += 0.5
    else: h -= 0.5
    return round(min(10, max(0, h)), 1)

# ═══════════════════════════════════
# MAIN AI SIGNAL ENGINE
# ═══════════════════════════════════
def ai_signal_score(df):
    if df is None or len(df) < 60:
        return None

    close  = df['Close']
    volume = df['Volume']
    price  = float(close.iloc[-1])
    prev   = float(close.iloc[-2])
    chg    = (price - prev) / prev * 100

    # Core Indicators
    rsi              = calc_rsi(close)
    rsi_val          = float(rsi.iloc[-1])
    macd_line, macd_sig, macd_hist = calc_macd(close)
    macd_val         = float(macd_hist.iloc[-1])
    macd_prev        = float(macd_hist.iloc[-2])
    ema9             = float(close.ewm(span=9).mean().iloc[-1])
    ema21            = float(close.ewm(span=21).mean().iloc[-1])
    ema50            = float(close.rolling(50).mean().iloc[-1])
    ema200           = float(close.rolling(200).mean().iloc[-1]) if len(close)>=200 else ema50
    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    bb_u             = float(bb_upper.iloc[-1])
    bb_l             = float(bb_lower.iloc[-1])
    bb_pct           = (price - bb_l) / (bb_u - bb_l + 1e-9) * 100
    vol_avg          = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio        = float(volume.iloc[-1]) / max(vol_avg, 1)
    vwap             = calc_vwap(df)
    st_bull, st_low, st_high = calc_supertrend(df)
    support, resistance, pivot = calc_support_resistance(df)

    # Scoring
    score   = 0
    reasons = []

    # RSI
    if rsi_val > 70:
        score -= 2; reasons.append(f"RSI={rsi_val:.0f} Overbought ⚠️")
    elif rsi_val > 55:
        score += 2; reasons.append(f"RSI={rsi_val:.0f} Bullish zone ✅")
    elif rsi_val < 30:
        score -= 2; reasons.append(f"RSI={rsi_val:.0f} Oversold ⚠️")
    elif rsi_val < 45:
        score -= 1

    # MACD
    if macd_val > 0 and macd_prev < 0:
        score += 3; reasons.append("MACD Golden Cross! 🌟")
    elif macd_val < 0 and macd_prev > 0:
        score -= 3; reasons.append("MACD Death Cross! ☠️")
    elif macd_val > 0:
        score += 2; reasons.append("MACD Bullish 📈")
    else:
        score -= 2; reasons.append("MACD Bearish 📉")

    # EMA Trend
    if price > ema9 > ema21 > ema50:
        score += 3; reasons.append("Strong Uptrend — All EMAs aligned 💪")
    elif price > ema21 > ema50:
        score += 2; reasons.append("Uptrend — Price above EMA21 & 50 ✅")
    elif price > ema9:
        score += 1
    elif price < ema9 < ema21 < ema50:
        score -= 3; reasons.append("Strong Downtrend — All EMAs falling 🔴")
    elif price < ema21:
        score -= 2; reasons.append("Downtrend — Price below EMAs 📉")

    # Volume
    if vol_ratio > 1.5 and chg > 0:
        score += 2; reasons.append(f"High Volume BUY {vol_ratio:.1f}x avg 🔊")
    elif vol_ratio > 1.5 and chg < 0:
        score -= 2; reasons.append(f"High Volume SELL {vol_ratio:.1f}x avg 🔊")
    elif vol_ratio < 0.5:
        score -= 1

    # Bollinger
    if bb_pct < 20:
        score += 2; reasons.append("Near BB Lower — Oversold bounce 📊")
    elif bb_pct > 80:
        score -= 1; reasons.append("Near BB Upper — Overbought 📊")

    # VWAP
    if price > vwap:
        score += 1; reasons.append(f"Above VWAP ₹{vwap:.0f} ✅")
    else:
        score -= 1; reasons.append(f"Below VWAP ₹{vwap:.0f} ⚠️")

    # Supertrend
    if st_bull:
        score += 1; reasons.append("Supertrend Bullish 🟢")
    else:
        score -= 1; reasons.append("Supertrend Bearish 🔴")

    # Candlestick Patterns
    patterns = detect_patterns(df)
    for p in patterns:
        if p['type'] == 'BULLISH': score += 1
        elif p['type'] == 'BEARISH': score -= 1

    # Signal determination
    MAX = 14
    strength   = min(100, max(0, int(abs(score) / MAX * 100)))
    confidence = min(88, max(40, strength + 20))

    if score >= 7:   sig = "STRONG BUY"
    elif score >= 3: sig = "BUY"
    elif score <= -7: sig = "STRONG SELL"
    elif score <= -3: sig = "SELL"
    else:            sig = "HOLD"

    risk = "HIGH" if rsi_val > 72 or vol_ratio < 0.5 else "LOW" if strength > 65 else "MED"

    # Target & SL using ATR
    atr = float(close.rolling(14).apply(lambda x: x.max() - x.min()).iloc[-1])
    if "BUY" in sig:
        target    = round(price + atr * 1.5, 2)
        sl        = round(price - atr * 0.8, 2)
        tgt_min   = round(price + atr * 0.8, 2)
        tgt_max   = round(price + atr * 2.5, 2)
    else:
        target    = round(price - atr * 1.5, 2)
        sl        = round(price + atr * 0.8, 2)
        tgt_min   = round(price - atr * 2.5, 2)
        tgt_max   = round(price - atr * 0.8, 2)

    rr = round(abs(target - price) / max(abs(price - sl), 0.01), 2)

    # Health score
    health = calc_health_score(rsi_val, macd_val, vol_ratio, score, st_bull, bb_pct)

    # Next candle prediction
    prediction = predict_next_candle(df, score, patterns, rsi_val, macd_val, vol_ratio)

    # Divergence detection
    divergence = None
    if len(close) >= 5:
        price_up = float(close.iloc[-1]) > float(close.iloc[-5])
        rsi_up   = float(rsi.iloc[-1]) > float(rsi.iloc[-5])
        if price_up and not rsi_up:
            divergence = "BEARISH DIVERGENCE — Price upar, RSI neeche ⚠️"
        elif not price_up and rsi_up:
            divergence = "BULLISH DIVERGENCE — Price neeche, RSI upar 🌟"

    # AI Hindi summary
    if "BUY" in sig:
        hindi_summary = f"{'Bahut strong' if 'STRONG' in sig else 'Achha'} buying opportunity hai. {reasons[0] if reasons else ''}"
    elif "SELL" in sig:
        hindi_summary = f"{'Bahut strong' if 'STRONG' in sig else 'Achha'} selling opportunity hai. {reasons[0] if reasons else ''}"
    else:
        hindi_summary = "Abhi wait karo, clear signal nahi hai."

    # Trade type
    if strength > 70:
        trade_type = "INTRADAY + SWING"
    elif strength > 50:
        trade_type = "INTRADAY"
    else:
        trade_type = "WAIT"

    return {
        'price':      round(price, 2),
        'change':     round(chg, 2),
        'open':       round(float(df['Open'].iloc[-1]), 2),
        'high':       round(float(df['High'].iloc[-1]), 2),
        'low':        round(float(df['Low'].iloc[-1]), 2),
        'volume':     int(df['V
