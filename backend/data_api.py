from flask import Flask, jsonify
from flask_cors import CORS
from backend.data_fetcher import get_market_data_for_plot
import logging
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains (for local dev)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Simple in-memory cache
CACHE = {'data': None, 'timestamp': 0}
CACHE_TTL = 300  # seconds

@app.route('/api/market_data')
def market_data():
    now = time.time()
    # Use cache if data is fresh
    if CACHE['data'] and now - CACHE['timestamp'] < CACHE_TTL:
        logging.info('Serving market data from cache.')
        return jsonify(CACHE['data'])
    try:
        data = get_market_data_for_plot()  # You must implement this function
        # Validate and normalize data
        filtered = []
        for d in data:
            try:
                x = float(d['x'])
                y = float(d['y'])
                z = float(d['z'])
                ticker = str(d['Ticker'])
                # Clamp/normalize values to 0-1
                x = max(0, min(1, x))
                y = max(0, min(1, y))
                z = max(0, min(1, z))
                filtered.append({'x': x, 'y': y, 'z': z, 'Ticker': ticker})
            except Exception as e:
                logging.warning(f"Skipping bad data: {d} ({e})")
        CACHE['data'] = filtered
        CACHE['timestamp'] = now
        return jsonify(filtered)
    except Exception as e:
        logging.error(f"Error fetching market data: {e}")
        return jsonify({'error': 'Failed to fetch data'}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
