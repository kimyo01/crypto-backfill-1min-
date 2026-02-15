# 📊 Crypto 1-Min Backfill Pipeline

Binance 1분봉(Kline) 과거 데이터를 월 단위로 백필(backfill)하여  
ClickHouse에 적재하는 Docker 기반 배치 파이프라인입니다.

---

## 📌 프로젝트 개요

이 프로젝트는 다음 작업을 수행합니다.

- Binance API를 이용한 1분봉 과거 데이터 수집
- 월 단위 백필 실행
- Docker 기반 실행 환경 구성
- ClickHouse 데이터 적재

---

## 📁 디렉토리 구조

```text
crypto-backfill/
├── docker-compose.yml
├── backfill/
│   ├── backfill_spot_klines_1m.py
│   ├── Dockerfile
│   └── requirements.txt
├── clickhouse/
│   └── init.sql
└── README.md
```
---

## 📁 기본 설정

기본 심볼: BTCUSDT, ETHUSDT

다른 코인을 추가하려면
docker-compose.yml 파일에서 심볼을 수정하면 됩니다.

```text
environment:
      CLICKHOUSE_HOST: clickhouse
      CLICKHOUSE_HTTP_PORT: "8123"
      CLICKHOUSE_DB: crypto
      CLICKHOUSE_TABLE: spot_klines_1m

      # 대상 심볼
      SYMBOLS: "BTCUSDT,ETHUSDT"
```

--- 
## 실행 방법
1️⃣ ClickHouse 실행
docker compose up -d clickhouse

2️⃣ Backfill 실행 
docker compose run --rm backfill

---

## 🗄ClickHouse 테이블 스키마

```text
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
```
--- 


