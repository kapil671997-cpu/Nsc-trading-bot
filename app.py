import os, math, time, threading, logging
import numpy as np
import yfinance as yf
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, date, timedelta
import requests

logging.basicConfig(level=logging.WARNING)
app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════
# TELEGRAM CONFIG — APNA TOKEN YAHAN DALO
# ═══════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

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
    'HINDUNILVR.NS':{'name':'HUL',              'cat':'LARGE','sec':'FMCG'},
    'ITC.NS':      {'name':'ITC',               'cat':'LARGE','sec':'FMCG'},
    'KOTAKBANK.NS':{'name':'Kotak Bank',        'cat':'LARGE','sec':'Banking'},
    'LT.NS':       {'name':'L&T',               'cat':'LARGE','sec':'Infra'},
    'AXISBANK.NS': {'name':'Axis Bank',         'cat':'LARGE','sec':'Banking'},
    'BAJFINANCE.NS':{'name':'Bajaj Finance',    'cat':'LARGE','sec':'NBFC'},
    'MARUTI.NS':   {'name':'Maruti Suzuki',     'cat':'LARGE','sec':'Auto'},
    'TATAMOTORS.NS':{'name':'Tata Motors',      'cat':'LARGE','sec':'Auto'},
    'SUNPHARMA.NS':{'name':'Sun Pharma',        'cat':'LARGE','sec':'Pharma'},
    'HCLTECH.NS':  {'name':'HCL Tech',          'cat':'LARGE','sec':'IT'},
    'WIPRO.NS':    {'name':'Wipro',             'cat':'LARGE','sec':'IT'},
    'ONGC.NS':     {'name':'ONGC',             'cat':'LARGE','sec':'Energy'},
    'NTPC.NS':     {'name':'NTPC',             'cat':'LARGE','sec':'Power'},
    'BHARTIARTL.NS':{'name':'Airtel',          'cat':'LARGE','sec':'Telecom'},
    'TATASTEEL.NS':{'name':'Tata Steel',       'cat':'LARGE','sec':'Metal'},
    'ADANIENT.NS': {'name':'Adani Ent',        'cat':'LARGE','sec':'Infra'},
    'HINDALCO.NS': {'name':'Hindalco',         'cat':'LARGE','sec':'Metal'},
    'JSWSTEEL.NS': {'name':'JSW Steel',        'cat':'LARGE','sec':'Metal'},
    'DRREDDY.NS':  {'name':'Dr Reddy',         'cat':'LARGE','sec':'Pharma'},
    'CIPLA.NS':    {'name':'Cipla',            'cat':'LARGE','sec':'Pharma'},
    'TITAN.NS':    {'name':'Titan',            'cat':'LARGE','sec':'Consumer'},
    'ASIANPAINT.NS':{'name':'Asian Paints',   'cat':'LARGE','sec':'Chemical'},
    'BAJAJ-AUTO.NS':{'name':'Bajaj Auto',     'cat':'LARGE','sec':'Auto'},
    'HEROMOTOCO.NS':{'name':'Hero MotoCorp',  'cat':'LARGE','sec':'Auto'},
    # MID CAP
    'ZOMATO.NS':   {'name':'Zomato',          'cat':'MID','sec':'Tech'},
    'PNB.NS':      {'name':'PNB',             'cat':'MID','sec':'Banking'},
    'BANKBARODA.NS':{'name':'Bank of Baroda', 'cat':'MID','sec':'Banking'},
    'CANBK.NS':    {'name':'Canara Bank',     'cat':'MID','sec':'Banking'},
    'IRCTC.NS':    {'name':'IRCTC',           'cat':'MID','sec':'Travel'},
    'NMDC.NS':     {'name':'NMDC',            'cat':'MID','sec':'Mining'},
    'MUTHOOTFIN.NS':{'name':'Muthoot Fin',   'cat':'MID','sec':'NBFC'},
    'LUPIN.NS':    {'name':'Lupin',           'cat':'MID','sec':'Pharma'},
    'MARICO.NS':   {'name':'Marico',          'cat':'MID','sec':'FMCG'},
    'COLPAL.NS':   {'name':'Colgate',         'cat':'MID','sec':'FMCG'},
    'DABUR.NS':    {'name':'Dabur',           'cat':'MID','sec':'FMCG'},
    'ASHOKLEY.NS': {'name':'Ashok Leyland',  'cat':'MID','sec':'Auto'},
    'MPHASIS.NS':  {'name':'Mphasis',        'cat':'MID','sec':'IT'},
    'COFORGE.NS':  {'name':'Coforge',        'cat':'MID','sec':'IT'},
    'APOLLOTYRE.NS':{'name':'Apollo Tyres',  'cat':'MID','sec':'Auto'},
    # SMALL CAP
    'RBLBANK.NS':  {'name':'RBL Bank',       'cat':'SMALL','sec':'Banking'},
    'YESBANK.NS':  {'name':'Yes Bank',       'cat':'SMALL','sec':'Banking'},
    'TANLA.NS':    {'name':'Tanla Platforms','cat':'SMALL','sec':'IT'},
    'KPITTECH.NS': {'name':'KPIT Tech',      'cat':'SMALL','sec':'IT'},
    'ESCORTS.NS':  {'name':'Escorts Kubota', 'cat':'SMALL','sec':'Auto'},
}

RFR = 0.065

# ═══════════════════════════════════
# TECHNICAL ANALYSIS ENGINE
# ═══════════════════════════════════
def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def calc_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger(prices, period=20, std=2):
    sma = prices.rolling(period).mean()
    std_dev = prices.rolling(period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def ai_signal_score(df):
    """Multi-indicator AI-like scoring system"""
    if df is None or len(df) < 60:
        return None

    close = df['Close']
    volume = df['Volume']
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    chg = (price - prev) / prev * 100

    # Indicators
    rsi = calc_rsi(close)
    rsi_val = float(rsi.iloc[-1])

    macd_line, macd_sig, macd_hist = calc_macd(close)
    macd_val = float(macd_hist.iloc[-1])
    macd_prev = float(macd_hist.iloc[-2])

    ema9  = float(close.ewm(span=9).mean().iloc[-1])
    ema21 = float(close.ewm(span=21).mean().iloc[-1])
    ema50 = float(close.rolling(50).mean().iloc[-1])
    ema200= float(close.rolling(200).mean().iloc[-1]) if len(close)>=200 else ema50

    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    bb_u = float(bb_upper.iloc[-1])
    bb_l = float(bb_lower.iloc[-1])
    bb_pct = (price - bb_l) / (bb_u - bb_l + 1e-9) * 100

    vol_avg = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = float(volume.iloc[-1]) / max(vol_avg, 1)

    # Scoring — weighted
    score = 0
    reasons = []

    # RSI (weight: 20%)
    if rsi_val > 70:
        score -= 2; reasons.append(f"RSI={rsi_val:.0f} Overbought")
    elif rsi_val > 55:
        score += 2; reasons.append(f"RSI={rsi_val:.0f} Bullish zone")
    elif rsi_val < 30:
        score -= 2; reasons.append(f"RSI={rsi_val:.0f} Oversold")
    elif rsi_val < 45:
        score -= 1

    # MACD (weight: 25%)
    if macd_val > 0 and macd_prev < 0:
        score += 3; reasons.append("MACD Golden Cross!")
    elif macd_val < 0 and macd_prev > 0:
        score -= 3; reasons.append("MACD Death Cross!")
    elif macd_val > 0:
        score += 2; reasons.append("MACD Bullish")
    else:
        score -= 2; reasons.append("MACD Bearish")

    # EMA Trend (weight: 25%)
    if price > ema9 > ema21 > ema50:
        score += 3; reasons.append("Strong Uptrend — All EMAs aligned")
    elif price > ema21 > ema50:
        score += 2; reasons.append("Uptrend — Price above EMA21 & 50")
    elif price > ema9:
        score += 1
    elif price < ema9 < ema21 < ema50:
        score -= 3; reasons.append("Strong Downtrend — All EMAs falling")
    elif price < ema21:
        score -= 2; reasons.append("Downtrend — Price below EMAs")

    # Volume (weight: 15%)
    if vol_ratio > 1.5 and chg > 0:
        score += 2; reasons.append(f"High Volume BUY {vol_ratio:.1f}x avg")
    elif vol_ratio > 1.5 and chg < 0:
        score -= 2; reasons.append(f"High Volume SELL {vol_ratio:.1f}x avg")
    elif vol_ratio < 0.5:
        score -= 1

    # Bollinger Bands (weight: 15%)
    if bb_pct < 20:
        score += 2; reasons.append("Near BB Lower — Oversold bounce")
    elif bb_pct > 80:
        score -= 1; reasons.append("Near BB Upper — Overbought")

    # Signal
    MAX = 12
    strength = min(100, max(0, int(abs(score) / MAX * 100)))
    confidence = min(88, max(40, strength + 20))

    if score >= 5:
        sig = "STRONG BUY"
    elif score >= 2:
        sig = "BUY"
    elif score <= -5:
        sig = "STRONG SELL"
    elif score <= -2:
        sig = "SELL"
    else:
        sig = "HOLD"

    risk = "HIGH" if rsi_val > 72 or vol_ratio < 0.5 else "LOW" if strength > 65 else "MED"

    # Target & SL
    atr = float(close.rolling(14).apply(lambda x: x.max() - x.min()).iloc[-1])
    if sig in ("STRONG BUY", "BUY"):
        target = round(price + atr * 1.5, 2)
        sl = round(price - atr * 0.8, 2)
    else:
        target = round(price - atr * 1.5, 2)
        sl = round(price + atr * 0.8, 2)

    rr = round(abs(target - price) / max(abs(price - sl), 0.01), 2)

    return {
        'price': round(price, 2),
        'change': round(chg, 2),
        'open': round(float(df['Open'].iloc[-1]), 2),
        'high': round(float(df['High'].iloc[-1]), 2),
        'low':  round(float(df['Low'].iloc[-1]), 2),
        'volume': int(df['Volume'].iloc[-1]),
        'vol_ratio': round(vol_ratio, 2),
        'rsi': round(rsi_val, 1),
        'macd': round(macd_val, 3),
        'macd_signal': round(float(macd_sig.iloc[-1]), 3),
        'ema9': round(ema9, 2),
        'ema21': round(ema21, 2),
        'ema50': round(ema50, 2),
        'bb_upper': round(bb_u, 2),
        'bb_lower': round(bb_l, 2),
        'bb_pct': round(bb_pct, 1),
        'signal': sig,
        'score': score,
        'strength': strength,
        'confidence': confidence,
        'risk': risk,
        'target': target,
        'sl': sl,
        'rr': rr,
        'reasons': reasons[:4],
        'updated': datetime.now().isoformat()
    }

# ═══════════════════════════════════
# CACHE
# ═══════════════════════════════════
cache = {}
lock  = threading.Lock()
alerted = set()

def fetch_stock(ticker, meta):
    try:
        df = yf.download(ticker, period='1y', interval='1d',
                         auto_adjust=True, progress=False, threads=False)
        if df is None or len(df) < 60:
            return
        result = ai_signal_score(df)
        if result:
            t = ticker.replace('.NS','')
            result.update({'ticker': t, 'name': meta['name'],
                          'cat': meta['cat'], 'sec': meta['sec']})
            with lock:
                cache[t] = result
            # Telegram alert for strong signals
            check_alert(t, result)
    except Exception as e:
        print(f"Error {ticker}: {e}")

def check_alert(ticker, data):
    """Send Telegram alert for strong signals"""
    sig = data['signal']
    key = f"{ticker}_{sig}_{date.today()}"
    if sig in ('STRONG BUY', 'STRONG SELL') and key not in alerted:
        alerted.add(key)
        emoji = "🟢" if "BUY" in sig else "🔴"
        direction = "KHARIDO" if "BUY" in sig else "BECHO"
        msg = f"""{emoji} <b>{sig} ALERT!</b>

📊 <b>{ticker}</b> — {data['name']}
💰 <b>{direction}:</b> ₹{data['price']}
🎯 <b>Target:</b> ₹{data['target']}
🛑 <b>Stop Loss:</b> ₹{data['sl']}
📈 <b>R:R Ratio:</b> {data['rr']}:1
💪 <b>Confidence:</b> {data['confidence']}%
⚠️ <b>Risk:</b> {data['risk']}

📉 RSI: {data['rsi']} | MACD: {'Bullish' if data['macd']>0 else 'Bearish'}
📦 Volume: {data['vol_ratio']}x average

💡 {' | '.join(data['reasons'][:2])}

⏰ {datetime.now().strftime('%I:%M %p')} IST"""
        send_telegram(msg)

def load_all():
    print("Loading all stocks...")
    threads = []
    for t, m in STOCKS.items():
        th = threading.Thread(target=fetch_stock, args=(t, m))
        th.start()
        threads.append(th)
        time.sleep(0.3)
    for th in threads:
        th.join()
    print(f"Loaded {len(cache)} stocks!")

    # Send startup message to Telegram
    send_telegram(f"""🚀 <b>NSE Trading Bot LIVE!</b>

✅ {len(cache)} stocks loaded
📊 Scanning every 5 minutes
⏰ {datetime.now().strftime('%I:%M %p')} IST

Market: {'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}""")

def is_market_open():
    ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    if ist.weekday() >= 5:
        return False
    m = ist.hour * 60 + ist.minute
    return 9*60+15 <= m <= 15*60+30

def rolling_refresh():
    items = list(STOCKS.items())
    i = 0
    while True:
        t, m = items[i % len(items)]
        try:
            fetch_stock(t, m)
        except:
            pass
        i += 1
        time.sleep(5)

def daily_summary():
    """Send daily market summary at 3:30 PM"""
    while True:
        ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        if ist.hour == 15 and ist.minute == 30:
            with lock:
                all_data = list(cache.values())
            buy   = [d for d in all_data if 'BUY'  in d['signal']]
            sell  = [d for d in all_data if 'SELL' in d['signal']]
            top_b = sorted(buy,  key=lambda x: x['confidence'], reverse=True)[:3]
            top_s = sorted(sell, key=lambda x: x['confidence'], reverse=True)[:3]

            msg = f"""📊 <b>DAILY MARKET SUMMARY</b>
⏰ {ist.strftime('%d %b %Y')}

🟢 BUY Signals: {len(buy)}
🔴 SELL Signals: {len(sell)}

<b>Top BUY:</b>
"""
            for d in top_b:
                msg += f"• {d['ticker']} ₹{d['price']} → ₹{d['target']} ({d['confidence']}%)\n"
            msg += "\n<b>Top SELL:</b>\n"
            for d in top_s:
                msg += f"• {d['ticker']} ₹{d['price']} → ₹{d['target']} ({d['confidence']}%)\n"

            send_telegram(msg)
            time.sleep(60)
        time.sleep(30)

# ═══════════════════════════════════
# API ROUTES
# ═══════════════════════════════════
@app.route('/api/stocks')
def r_stocks():
    cat = request.args.get('cat', 'ALL').upper()
    sec = request.args.get('sec', 'ALL')
    with lock:
        data = list(cache.values())
    if cat != 'ALL':
        data = [d for d in data if d['cat'] == cat]
    if sec != 'ALL':
        data = [d for d in data if d['sec'] == sec]
    return jsonify(data)

@app.route('/api/stock/<ticker>')
def r_stock(ticker):
    with lock:
        d = cache.get(ticker.upper())
    if not d:
        return jsonify({'error': 'not found'}), 404
    return jsonify(d)

@app.route('/api/scan')
def r_scan():
    with lock:
        data = list(cache.values())
    strong = [d for d in data if d['signal'] in ('STRONG BUY','STRONG SELL','BUY','SELL')]
    strong.sort(key=lambda x: x['confidence'], reverse=True)
    return jsonify({'signals': strong[:20], 'count': len(strong),
                    'ts': datetime.now().isoformat()})

@app.route('/api/top')
def r_top():
    with lock:
        data = list(cache.values())
    buy  = sorted([d for d in data if 'BUY'  in d['signal']], key=lambda x: x['confidence'], reverse=True)[:5]
    sell = sorted([d for d in data if 'SELL' in d['signal']], key=lambda x: x['confidence'], reverse=True)[:5]
    return jsonify({'top_buy': buy, 'top_sell': sell})

@app.route('/api/status')
def r_status():
    with lock:
        n = len(cache)
    return jsonify({
        'loaded': n, 'total': len(STOCKS),
        'market_open': is_market_open(),
        'ts': datetime.now().isoformat()
    })

@app.route('/')
def home():
    return "NSE Trading Bot Server — LIVE! 🚀"

if __name__ == '__main__':
    load_all()
    threading.Thread(target=rolling_refresh, daemon=True).start()
    threading.Thread(target=daily_summary,   daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
