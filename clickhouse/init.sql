CREATE DATABASE IF NOT EXISTS crypto;

CREATE TABLE IF NOT EXISTS crypto.spot_klines_1m
(
  symbol LowCardinality(String),

  -- 원본 timestamp 보관(단위 혼재 가능성 대비)
  open_ts UInt64,
  ts_unit LowCardinality(String), -- 'ms' or 'us'

  open_time DateTime64(6, 'UTC')
    MATERIALIZED
      if(ts_unit='us',
         fromUnixTimestamp64Micro(open_ts),
         fromUnixTimestamp64Milli(open_ts)
      ),

  open Float64,
  high Float64,
  low Float64,
  close Float64,

  volume Float64,

  close_ts UInt64,
  quote_volume Float64,
  trade_count UInt32,
  taker_buy_base_volume Float64,
  taker_buy_quote_volume Float64,

  source LowCardinality(String) DEFAULT 'binance_vision',
  ingest_time DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY (symbol, toYYYYMM(open_time))
ORDER BY (symbol, open_time);
