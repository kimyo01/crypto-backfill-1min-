import os
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import clickhouse_connect

st.set_page_config(page_title="Crypto Weekly OHLCV", layout="wide")

# ---- Config ----
CH_HOST = os.getenv("CH_HOST", "localhost")
CH_PORT = int(os.getenv("CH_PORT", "8123"))   # HTTP port
CH_USER = os.getenv("CH_USER", "default")
CH_PASS = os.getenv("CH_PASS", "")
CH_DB   = os.getenv("CH_DB", "crypto")
TABLE   = os.getenv("CH_TABLE", "spot_klines_1m")

DEFAULT_SYMBOL = os.getenv("SYMBOL", "BTCUSDT")

# ---- UI ----
st.title("Crypto Weekly OHLCV (from 1m klines in ClickHouse)")

symbol = st.text_input("Symbol", DEFAULT_SYMBOL).strip().upper()
weeks = st.slider("Weeks to show", min_value=20, max_value=400, value=200, step=10)

client = clickhouse_connect.get_client(
    host=CH_HOST, port=CH_PORT, username=CH_USER, password=CH_PASS, database=CH_DB
)

query = f"""
SELECT
  symbol,
  toStartOfWeek(open_time, 1) AS week_start,
  argMin(open, open_time)  AS open,
  max(high)                AS high,
  min(low)                 AS low,
  argMax(close, open_time) AS close,
  sum(volume)              AS volume,
  sum(trade_count)         AS trades
FROM {TABLE}
WHERE symbol = %(symbol)s
GROUP BY symbol, week_start
ORDER BY week_start DESC
LIMIT %(weeks)s
"""

df = client.query_df(query, parameters={"symbol": symbol, "weeks": weeks})
if df.empty:
    st.warning("No data returned. Check symbol/table and ClickHouse connection.")
    st.stop()

df = df.sort_values("week_start")  # oldest -> newest

st.subheader(f"{symbol} weekly OHLCV")
st.dataframe(df.tail(50), use_container_width=True)

# ---- Simple close line chart ----
fig = plt.figure()
plt.plot(df["week_start"], df["close"])
plt.xticks(rotation=30, ha="right")
plt.xlabel("Week")
plt.ylabel("Close")
st.pyplot(fig, clear_figure=True)

# ---- Volume chart ----
fig2 = plt.figure()
plt.plot(df["week_start"], df["volume"])
plt.xticks(rotation=30, ha="right")
plt.xlabel("Week")
plt.ylabel("Volume")
st.pyplot(fig2, clear_figure=True)
