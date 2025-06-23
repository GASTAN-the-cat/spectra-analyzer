# Spectra Analyzer

This container reads OHLCV data from a TimescaleDB database and computes RSI and MACD indicators. Results are written back into a separate table. Configuration is done via environment variables so the service can be easily integrated in a `docker-compose` stack.

## Configuration

Environment variables (with defaults):

- `DB_NAME` – database name (`spectra`)
- `DB_USER` – database user (`spectra_user`)
- `DB_PASSWORD` – database password (`very_secret_pass`)
- `DB_HOST` – database host (`timescaledb`)
- `DB_PORT` – database port (`5432`)
- `SYMBOL_TABLE` – source OHLCV table (`btc_usdt_ohlcv`)
- `IND_TABLE` – destination indicator table (`btc_usdt_indicators`)
- `RSI_PERIOD` – RSI lookback period (`14`)
- `MACD_FAST` – MACD fast EMA period (`12`)
- `MACD_SLOW` – MACD slow EMA period (`26`)
- `MACD_SIGNAL` – MACD signal EMA period (`9`)
- `INTERVAL` – delay between computations in seconds (`60`)

## Running locally

```bash
# install dependencies
pip install -r requirements.txt

# run the analyzer
python app.py
```

Use the above environment variables to adjust database connection parameters.
