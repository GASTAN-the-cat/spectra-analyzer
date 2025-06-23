# spectra-analyzer/app.py
import os
import time
import logging
import psycopg2
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="[%(asctime)s] %(message)s")

DB = {
    'dbname':   os.getenv('DB_NAME', 'spectra'),
    'user':     os.getenv('DB_USER', 'spectra_user'),
    'password': os.getenv('DB_PASSWORD', 'very_secret_pass'),
    'host':     os.getenv('DB_HOST', 'timescaledb'),
    'port':     int(os.getenv('DB_PORT', 5432)),
}
SYMBOL_TABLE = os.getenv('SYMBOL_TABLE', 'btc_usdt_ohlcv')
IND_TABLE    = os.getenv('IND_TABLE', 'btc_usdt_indicators')
RSI_PERIOD   = int(os.getenv('RSI_PERIOD', 14))
MACD_FAST    = int(os.getenv('MACD_FAST', 12))
MACD_SLOW    = int(os.getenv('MACD_SLOW', 26))
MACD_SIGNAL  = int(os.getenv('MACD_SIGNAL', 9))
INTERVAL     = int(os.getenv('INTERVAL', 60))  # seconds
# ────────────────────────────────────────────────────────────────────────────

def wait_for_db():
    while True:
        try:
            conn = psycopg2.connect(**DB)
            logging.info("Connected to DB")
            return conn
        except psycopg2.OperationalError:
            logging.info("Waiting for DB…")
            time.sleep(5)

def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {IND_TABLE} (
              timestamp    TIMESTAMPTZ PRIMARY KEY,
              rsi14        DOUBLE PRECISION,
              macd         DOUBLE PRECISION,
              macd_signal  DOUBLE PRECISION,
              macd_hist    DOUBLE PRECISION
            );
        """)
        conn.commit()

def fetch_closes(conn):
    with conn.cursor() as cur:
        cur.execute(f"SELECT timestamp, close FROM {SYMBOL_TABLE} ORDER BY timestamp")
        return cur.fetchall()  # list of (ts, close)

def compute_rsi(closes):
    gains, losses = [], []
    for prev, curr in zip(closes, closes[1:]):
        diff = curr - prev
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    if len(gains) < RSI_PERIOD:
        return [None]*len(closes)
    avg_gain = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    avg_loss = sum(losses[:RSI_PERIOD]) / RSI_PERIOD
    rsi = [None]*RSI_PERIOD
    rs = avg_gain / avg_loss if avg_loss else float('inf')
    rsi.append(100 - 100/(1+rs))
    for g, l in zip(gains[RSI_PERIOD:], losses[RSI_PERIOD:]):
        avg_gain = (avg_gain*(RSI_PERIOD-1) + g) / RSI_PERIOD
        avg_loss = (avg_loss*(RSI_PERIOD-1) + l) / RSI_PERIOD
        rs = avg_gain / avg_loss if avg_loss else float('inf')
        rsi.append(100 - 100/(1+rs))
    return rsi

def compute_macd(closes):
    def ema(seq, period):
        k = 2/(period+1)
        ema_vals = []
        ema_vals.append(sum(seq[:period])/period)
        for price in seq[period:]:
            ema_vals.append(price*k + ema_vals[-1]*(1-k))
        return ema_vals

    if len(closes) < MACD_SLOW+MACD_SIGNAL:
        return [None]*len(closes), [None]*len(closes), [None]*len(closes)

    ema_fast = ema(closes, MACD_FAST)
    ema_slow = ema(closes, MACD_SLOW)
    # align: ema_fast starts at index FAST-1, ema_slow at SLOW-1
    macd_line = [f - s for f, s in zip(ema_fast[MACD_SLOW-MACD_FAST:], ema_slow)]
    signal_line = ema(macd_line, MACD_SIGNAL)
    hist = [m - s for m, s in zip(macd_line[MACD_SIGNAL-1:], signal_line)]

    # pad to match original length
    pad = MACD_SLOW-1 + MACD_SIGNAL-1
    macd_full   = [None]*pad + macd_line[MACD_SIGNAL-1:]
    signal_full = [None]*pad + signal_line
    hist_full   = [None]*pad + hist
    return macd_full, signal_full, hist_full

def upsert(conn, data):
    with conn.cursor() as cur:
        for ts, rsi14, macd, sig, hist in data:
            if rsi14 is None or macd is None: 
                continue
            cur.execute(f"""
                INSERT INTO {IND_TABLE}
                  (timestamp, rsi14, macd, macd_signal, macd_hist)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (timestamp) DO UPDATE
                  SET rsi14       = EXCLUDED.rsi14,
                      macd        = EXCLUDED.macd,
                      macd_signal = EXCLUDED.macd_signal,
                      macd_hist   = EXCLUDED.macd_hist;
            """, (ts, rsi14, macd, sig, hist))
        conn.commit()

if __name__ == "__main__":
    conn = wait_for_db()
    ensure_table(conn)
    while True:
        try:
            rows = fetch_closes(conn)
            timestamps, closes = zip(*rows)
            rsi_list = compute_rsi(list(closes))
            macd_list, sig_list, hist_list = compute_macd(list(closes))
            combined = zip(timestamps, rsi_list, macd_list, sig_list, hist_list)
            upsert(conn, combined)
            logging.info("Wrote indicator rows.")
        except Exception as e:
            logging.error(f"Error: {e}")
        time.sleep(INTERVAL)
