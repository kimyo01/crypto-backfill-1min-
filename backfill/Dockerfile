FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backfill_spot_klines_1m.py .

CMD ["python", "backfill_spot_klines_1m.py"]