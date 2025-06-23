# spectra-analyzer/app.py
import time
import psycopg2
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────
DB = {
    'dbname':   'spectra',
    'user':     'spectra_user',
    'password': 'very_secret_pass',
    'host':     'timescaledb',
    'port':     5432
}
SYMBOL_TABLE = 'btc_usdt_ohlcv'
IND_TABLE    = 'btc_usdt_indicators'
INTERVAL     = 60  # seconds between each run
# ────────────────────────────────────────────────────────────────────────────

def wait_for_db():
    while True:
        try:
            conn = psycopg2.connect(**DB)
            print(f"[{datetime.utcnow()}] Connected to DB")
            return conn
        except psycopg2.OperationalError:
            print(f"[{datetime.utcnow()}] DB not ready, retrying in 5s…")
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

def fetch_ohlcv(conn):
    df = pd.read_sql(f"SELECT * FROM {SYMBOL_TABLE} ORDER BY timestamp", conn, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df

def compute_indicators(df):
    # Compute RSI
    rsi = RSIIndicator(df['close'], window=14)
    df['rsi14'] = rsi.rsi()
    # Compute MACD
    macd_ind = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['macd']        = macd_ind.macd()
    df['macd_signal'] = macd_ind.macd_signal()
    df['macd_hist']   = macd_ind.macd_diff()
    return df.dropna()[['rsi14','macd','macd_signal','macd_hist']]

def upsert_indicators(conn, ind_df):
    with conn.cursor() as cur:
        for ts, row in ind_df.iterrows():
            cur.execute(f"""
                INSERT INTO {IND_TABLE}(timestamp,rsi14,macd,macd_signal,macd_hist)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (timestamp) DO UPDATE
                  SET rsi14       = EXCLUDED.rsi14,
                      macd        = EXCLUDED.macd,
                      macd_signal = EXCLUDED.macd_signal,
                      macd_hist   = EXCLUDED.macd_hist;
            """, (ts, row['rsi14'], row['macd'], row['macd_signal'], row['macd_hist']))
        conn.commit()

if __name__ == "__main__":
    conn = wait_for_db()
    ensure_table(conn)
    while True:
        try:
            df = fetch_ohlcv(conn)
            ind = compute_indicators(df)
            upsert_indicators(conn, ind)
            print(f"[{datetime.utcnow()}] Wrote {len(ind)} indicator rows.")
        except Exception as e:
            print(f"[{datetime.utcnow()}] Error:", e)
        time.sleep(INTERVAL)
