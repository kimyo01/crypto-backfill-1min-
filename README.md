📌 Project Overview

이 프로젝트는 다음을 수행합니다:

Binance API를 통한 1분봉 과거 데이터 수집

월 단위 백필 실행

Docker 기반 실행 환경 구성

ClickHouse 적재 

📁 Directory Structure
crypto-backfill-1min/
│
├── docker-compose.yml
├── backfill/
│   ├── backfill.py
│   ├── config.py
│   └── utils.py
│
├── clickhouse/
│   └── init.sql
│
└── README.md

📌 현재 기본 설정:

BTCUSDT
다른 코인 심볼을 추가하고 싶으면, config.py에서 추가 가능.

1️⃣ Docker 실행
docker compose up -d clickhouse

2️⃣ Backfill 실행
docker compose run --rm backfill

🗄 Data Schema (ClickHouse)
CREATE TABLE agg_trades_1min
(
    symbol String,
    open_time DateTime,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64
)
ENGINE = MergeTree()
ORDER BY (symbol, open_time);
