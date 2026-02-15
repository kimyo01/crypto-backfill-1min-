import os
import io
import csv
import zipfile
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# -------------------------
# Config
# -------------------------
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if s.strip()]
INTERVAL = "1m"

# Binance Vision (SPOT monthly klines)
BASE_URL_TMPL = "https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m"
# file: {SYMBOL}-1m-YYYY-MM.zip

CH_HOST  = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CH_PORT  = os.getenv("CLICKHOUSE_HTTP_PORT", "8123")
CH_DB    = os.getenv("CLICKHOUSE_DB", "crypto")
CH_TABLE = os.getenv("CLICKHOUSE_TABLE", "spot_klines_1m")

START_YEAR  = int(os.getenv("START_YEAR", "2017"))
START_MONTH = int(os.getenv("START_MONTH", "1"))

DL_WORKERS   = int(os.getenv("DL_WORKERS", "8"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/data/downloads")
BATCH_LINES  = int(os.getenv("BATCH_LINES", "80000"))

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
session = requests.Session()

# -------------------------
# Helpers
# -------------------------
def utc_now():
    return datetime.now(timezone.utc)

def last_completed_month():
    now = utc_now()
    y, m = now.year, now.month
    m -= 1
    if m == 0:
        m = 12
        y -= 1
    return y, m

def iter_months(start_y, start_m, end_y, end_m):
    """Inclusive start, inclusive end, yields (y,m) increasing."""
    y, m = start_y, start_m
    while (y < end_y) or (y == end_y and m <= end_m):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1

def zip_name(symbol: str, y: int, m: int) -> str:
    return f"{symbol}-{INTERVAL}-{y:04d}-{m:02d}.zip"

def zip_url(symbol: str, y: int, m: int) -> str:
    return f"{BASE_URL_TMPL.format(symbol=symbol)}/{zip_name(symbol, y, m)}"

def detect_ts_unit(ts: int) -> str:
    # ms ~ 1e12, us ~ 1e15
    return "us" if ts >= 10**14 else "ms"

def ch_post(query: str, body: bytes | None = None) -> str:
    url = f"http://{CH_HOST}:{CH_PORT}/"
    params = {"database": CH_DB, "query": query}
    r = session.post(url, params=params, data=body, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"ClickHouse error {r.status_code}: {r.text[:700]}")
    return r.text

def drop_partition(symbol: str, yyyymm: int):
    q = f"ALTER TABLE {CH_TABLE} DROP PARTITION ('{symbol}', {yyyymm})"
    try:
        ch_post(q)
        print(f"[ch] dropped partition (symbol={symbol}, yyyymm={yyyymm})")
    except Exception as e:
        msg = str(e)
        if "doesn't exist" in msg or "does not exist" in msg or "No such partition" in msg:
            print(f"[ch] partition missing -> skip drop (symbol={symbol}, yyyymm={yyyymm})")
            return
        raise

def insert_tsv(tsv: str):
    q = (
        f"INSERT INTO {CH_TABLE} "
        f"(symbol, open_ts, ts_unit, open, high, low, close, volume, close_ts, quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume) "
        f"FORMAT TabSeparated"
    )
    ch_post(q, body=tsv.encode("utf-8"))

def download(symbol: str, y: int, m: int) -> str:
    url = zip_url(symbol, y, m)
    path = os.path.join(DOWNLOAD_DIR, zip_name(symbol, y, m))

    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    r = session.get(url, timeout=HTTP_TIMEOUT)
    if r.status_code == 404:
        raise FileNotFoundError(f"404: {url}")
    r.raise_for_status()

    with open(path, "wb") as f:
        f.write(r.content)
    return path

def process_zip(symbol: str, path: str, y: int, m: int) -> int:
    yyyymm = y * 100 + m
    drop_partition(symbol, yyyymm)

    inserted = 0
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        if not names:
            print(f"[warn] empty zip: {path}")
            return 0
        csv_name = names[0]

        with zf.open(csv_name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8")
            reader = csv.reader(text)

            batch = []
            ts_unit = None

            for row in reader:
                # kline CSV columns:
                # 0 open_time, 1 open, 2 high, 3 low, 4 close, 5 volume,
                # 6 close_time, 7 quote_asset_volume, 8 number_of_trades,
                # 9 taker_buy_base, 10 taker_buy_quote, 11 ignore
                open_ts = int(row[0])
                if ts_unit is None:
                    ts_unit = detect_ts_unit(open_ts)

                o = float(row[1]); h = float(row[2]); l = float(row[3]); c = float(row[4])
                v = float(row[5])
                close_ts = int(row[6])
                quote_v = float(row[7])
                trades = int(float(row[8]))
                tb_base = float(row[9])
                tb_quote = float(row[10])

                batch.append(
                    f"{symbol}\t{open_ts}\t{ts_unit}\t{o}\t{h}\t{l}\t{c}\t{v}\t{close_ts}\t{quote_v}\t{trades}\t{tb_base}\t{tb_quote}"
                )

                if len(batch) >= BATCH_LINES:
                    insert_tsv("\n".join(batch) + "\n")
                    inserted += len(batch)
                    batch.clear()

            if batch:
                insert_tsv("\n".join(batch) + "\n")
                inserted += len(batch)

    return inserted

def main():
    end_y, end_m = last_completed_month()
    months = list(iter_months(START_YEAR, START_MONTH, end_y, end_m))
    print(f"[plan] symbols={SYMBOLS}, months={len(months)} ({months[0]}..{months[-1]})")
    print(f"[note] 404 month files will be skipped (this is normal).")

    # 1) parallel download
    downloads = {}  # (symbol,y,m)->path
    tasks = [(sym, y, m) for sym in SYMBOLS for (y, m) in months]

    errors = []
    with ThreadPoolExecutor(max_workers=DL_WORKERS) as ex:
        futs = {ex.submit(download, sym, y, m): (sym, y, m) for (sym, y, m) in tasks}
        for fut in as_completed(futs):
            sym, y, m = futs[fut]
            ym = f"{y:04d}-{m:02d}"
            try:
                path = fut.result()
                downloads[(sym, y, m)] = path
                print(f"[downloaded] {sym} {ym}")
            except FileNotFoundError:
                # 정상: 없는 월은 skip
                pass
            except Exception as e:
                errors.append((sym, y, m, str(e)))
                print(f"[error] download {sym} {ym}: {e}")

    if errors:
        print("[warn] some downloads failed (non-404):")
        for sym, y, m, msg in errors[:20]:
            print(f"  - {sym} {y:04d}-{m:02d}: {msg}")

    # 2) sequential load (drop partition + insert)
    total = 0
    for sym in SYMBOLS:
        for (y, m) in months:
            path = downloads.get((sym, y, m))
            if not path:
                continue
            ym = f"{y:04d}-{m:02d}"
            print(f"[load] {sym} {ym} (DROP PARTITION then INSERT)")
            ins = process_zip(sym, path, y, m)
            total += ins
            print(f"[inserted] {sym} {ym}: {ins} rows (cumulative={total})")

    print(f"[done] total_inserted={total}")

if __name__ == "__main__":
    main()