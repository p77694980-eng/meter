import yfinance as yf
import pandas as pd
import numpy as np
import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Asset tickers mapping to USD reference pairs
TICKERS = {
    'EUR': 'EURUSD=X',
    'GBP': 'GBPUSD=X',
    'AUD': 'AUDUSD=X',
    'NZD': 'NZDUSD=X',
    'JPY': 'JPY=X',      # Quote pair (USD/JPY)
    'CAD': 'CAD=X',      # Quote pair (USD/CAD)
    'CHF': 'CHF=X',      # Quote pair (USD/CHF)
    'XAU': 'GC=F'        # Gold Futures / Spot Proxy
}

ASSETS = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD', 'XAU']

def raw_to_score(raw_pct):
    """
    Normalizes percentage change into a 0 - 100 strength score.
    Safely handles NaN or invalid float inputs.
    """
    if pd.isna(raw_pct) or np.isnan(raw_pct):
        return 50  # Default to Neutral baseline if data is missing/NaN
    
    score = int(round((raw_pct + 1.0) * 50))
    return max(0, min(100, score))

def fetch_live_market_data():
    print("\n[AvishFX Engine] Fetching live market rates from Yahoo Finance...")
    
    ticker_symbols = list(TICKERS.values())
    # Fetch 5 days of data so daily open is always available even on weekends
    data = yf.download(ticker_symbols, period="5d", interval="1m", progress=False)
    
    if data.empty or 'Close' not in data:
        print("Error: Failed to fetch market data from Yahoo Finance.")
        return None

    # Get latest non-NaN close prices across tickers
    close_prices = data['Close'].ffill().iloc[-1]
    
    raw_shifts = {}
    
    # Direct pairs (Base/USD)
    for asset in ['EUR', 'GBP', 'AUD', 'NZD']:
        sym = TICKERS[asset]
        open_series = data['Open'][sym].dropna()
        open_p = open_series.iloc[0] if not open_series.empty else close_prices[sym]
        curr_p = close_prices[sym]
        raw_shifts[asset] = ((curr_p - open_p) / open_p) * 100 if open_p else 0.0

    # Inverted pairs (USD/Quote)
    for asset in ['JPY', 'CAD', 'CHF']:
        sym = TICKERS[asset]
        open_series = data['Open'][sym].dropna()
        open_p = open_series.iloc[0] if not open_series.empty else close_prices[sym]
        curr_p = close_prices[sym]
        raw_shifts[asset] = -(((curr_p - open_p) / open_p) * 100) if open_p else 0.0

    # Gold (XAU)
    xau_sym = TICKERS['XAU']
    open_series = data['Open'][xau_sym].dropna()
    xau_open = open_series.iloc[0] if not open_series.empty else close_prices[xau_sym]
    xau_curr = close_prices[xau_sym]
    raw_shifts['XAU'] = ((xau_curr - xau_open) / xau_open) * 100 if xau_open else 0.0

    # USD reference strength (average inverse of majors)
    valid_shifts = [raw_shifts[a] for a in ['EUR', 'GBP', 'AUD', 'NZD'] if not np.isnan(raw_shifts[a])]
    usd_shift = -np.mean(valid_shifts) if valid_shifts else 0.0
    raw_shifts['USD'] = usd_shift

    # Build structured output with 0-100 scores
    output_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "xau_price": round(float(xau_curr), 2) if not np.isnan(xau_curr) else 0.0,
        "assets": {}
    }

    for asset in ASSETS:
        shift_val = raw_shifts[asset]
        shift = round(float(shift_val), 2) if not np.isnan(shift_val) else 0.0
        score = raw_to_score(shift)
        output_data["assets"][asset] = {
            "score": score,
            "raw_pct": shift
        }

    return output_data

def save_to_json(data):
    with open('live_data.json', 'w') as f:
        json.dump(data, f, indent=4)
    print(f"✅ Success! Data written to live_data.json at {data['timestamp']}")

if __name__ == "__main__":
    print("🚀 AvishFX Market Engine Initialized.")
    while True:
        try:
            market_data = fetch_live_market_data()
            if market_data:
                save_to_json(market_data)
        except Exception as e:
            print(f"⚠️ Engine Exception: {e}")
            
        # Refresh every 10 seconds
       
       

# Initialize FastAPI instance
app = FastAPI()

# Enable CORS so your website can fetch data without cross-origin blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
def start_engine():
    # Place your background calculation loop or initial fetch function here
    pass

@app.get("/")
def read_root():
    return {"status": "AvishFX Engine Online"}

@app.get("/api/live_data")
def get_live_data():
    # Call your calculation functions here to calculate scores
    # Example response format:
    return {
        "status": "success",
        "assets": {
            "USD": {"score": 50},
            "EUR": {"score": 62},
            "GBP": {"score": 45},
            "JPY": {"score": 38},
            "AUD": {"score": 58},
            "CAD": {"score": 51},
            "CHF": {"score": 49},
            "NZD": {"score": 55},
            "XAU": {"score": 72}
        }
    }