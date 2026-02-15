Crypto 1-Min Backfill Pipeline
프로젝트 개요

이 프로젝트는 다음 작업을 수행합니다.

Binance API를 이용한 1분봉 과거 데이터 수집

월 단위 백필 실행

Docker 기반 실행 환경 구성

ClickHouse 데이터 적재

디렉토리 구조

crypto-backfill-1min/

├── docker-compose.yml
├── backfill/
│ ├── backfill.py
│ ├── config.py
│ └── utils.py
├── clickhouse/
│ └── init.sql
└── README.md

기본 설정

기본 심볼은 다음과 같습니다.

BTCUSDT

다른 코인을 추가하려면
backfill/config.py 파일에서 심볼을 수정하면 됩니다.

실행 방법

ClickHouse 실행

docker compose up -d clickhouse

Backfill 실행

docker compose run --rm backfill

ClickHouse 테이블 스키마

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
