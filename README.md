# Portfolio Risk Analysis - Data Generation Layer

## Setup

### 1. Install Dependencies
```bash
cd "C:\Users\Lenovo\Desktop\Portfolio Analysis"
./venv/Scripts/pip.exe install -r backend/requirements.txt
```

### 2. Install and Start Kafka 4.3.1 (KRaft Mode)

Download Kafka 4.3.1 from https://kafka.apache.org/downloads

Extract and navigate to the Kafka directory:
```bash
# One-time format step (KRaft)
.\bin\windows\kafka-storage.bat format --snapshot-file .\data\meta.properties --cluster-id MkQkDJWdOUCy_rw3x2 --path.logs data

# Start broker (in one terminal)
.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties
```

### 3. Create Kafka Topic
```bash
# From Kafka directory (in another terminal)
.\bin\windows\kafka-topics.bat --create --topic stock-price-updates --bootstrap-server localhost:9092 --partitions 6 --replication-factor 1
```

### 4. Verify Environment Variables
Ensure `.env` in the project root has:
```
mongo_user=admin
mongo_password=<your-password>
mongo_uri=mongodb+srv://admin:<password>@portfolio-risk.l6t35te.mongodb.net/
```

## Running the System

All components run as separate processes in independent terminals:

### Terminal 1: Seed Portfolios (one-time)
```bash
cd backend
python data-generation.py seed
```

### Terminal 2: FastAPI Health/Shock Endpoint
```bash
cd backend
uvicorn data-mongo:app --reload --port 8000
```

### Terminal 3: Price Poller (publishes to Kafka)
```bash
cd backend
python price_poller.py
```

### Terminal 4: Price Consumer (consumes from Kafka, updates Mongo)
```bash
cd backend
python price_consumer.py
```

### Terminal 5 (Optional): Trade Simulator (mutates portfolios)
```bash
cd backend
python trade_simulator.py
```

## Testing

### Test 1: Kafka Connectivity
```bash
cd backend
python test_kafka_smoke.py
```
Requires Kafka broker running on localhost:9092.

### Test 2: Seeding
```bash
cd backend
python test_seed.py
```
Requires MongoDB accessible and populated via seeding.

### Test 3: Triggering a Shock Scenario
Via CLI:
```bash
python data-generation.py shock --symbol RELIANCE --direction down --pct 12
```

Via API:
```bash
curl -X POST http://localhost:8000/shock \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE", "direction": "down", "magnitude_pct": 12}'
```

### Test 4: Monitor MongoDB
Use MongoDB Compass or mongosh to inspect:
- `portfolio_risk.portfolios` — live portfolio documents
- `portfolio_risk.price_ticks` — raw price tick history (time-series)
- `portfolio_risk.trades` — trade activity log

## Architecture

### Components

1. **data-generation.py** — CLI entry point (seed, shock commands)
2. **seed.py** — Generates 10 portfolios with 4-7 random NSE stock holdings each
3. **price_poller.py** — Every 60s, batches Yahoo Finance prices, publishes to Kafka
4. **price_consumer.py** — Consumes price ticks, recomputes portfolios, upserts MongoDB
5. **trade_simulator.py** — Random 5-10 min interval, mutates portfolio holdings
6. **data-mongo.py** — FastAPI app with `/ping-db` and `/shock` endpoints
7. **shock.py** — Triggers extreme price moves via Kafka (for testing alerting)

### Shared Modules

- **config.py** — Environment loading, Kafka/Mongo/timing constants
- **symbol_pool.py** — 18 static NSE symbols + metadata
- **models.py** — Data shapes (Portfolio, Holding, PriceTick, Trade)
- **mongo_client.py** — AsyncMongoClient factory, collection setup, indexes
- **kafka_common.py** — Kafka producer/consumer factories, message serialization

### Data Flow

```
Seed portfolios (10x, 4-7 holdings each) → MongoDB
                                        ↓
Price Poller (every 60s) → Kafka Topic (stock-price-updates, partitioned by symbol)
                           ↓
                        Price Consumer → Recompute + Upsert MongoDB
                                      → Insert price_ticks (time-series)
                                      
Trade Simulator (every 5-10 min) → Direct MongoDB mutation → Log trades
                                   
Shock Trigger (manual) → Kafka (same topic) → Consumer path (exercises alerting logic)
```

## MongoDB Schema

### `portfolios` Collection
- **_id**: ObjectId
- **user_id**: str (unique)
- **portfolio_id**: str (unique)
- **broker**: str ("ZERODHA")
- **portfolio_value**: float
- **total_invested**: float
- **total_pnl**: float
- **total_pnl_percentage**: float
- **holdings**: array of {symbol, instrument_token, quantity, average_price, current_price, invested_value, current_value, pnl, portfolio_weight_percentage}
- **last_updated**: datetime

**Indexes**: portfolio_id (unique), user_id (unique), holdings.symbol (multikey)

### `price_ticks` Collection (Time-Series)
- **ts**: datetime (timeField)
- **symbol**: str (metaField)
- **instrument_token**: int
- **price**: float
- **source**: str ("poll" or "shock")

### `trades` Collection
- **_id**: ObjectId
- **trade_id**: str (uuid)
- **portfolio_id**: str
- **ts**: datetime
- **action**: str (ADJUST_QUANTITY, ADD_HOLDING, REMOVE_HOLDING)
- **symbol**: str
- **quantity_delta**: int (optional)
- **new_average_price**: float (optional)
- **resulting_quantity**: int (optional)

**Indexes**: {portfolio_id, ts}

## Kafka Topic

- **Topic**: `stock-price-updates`
- **Partitions**: 6
- **Replication Factor**: 1
- **Key**: symbol (ensures per-symbol ordering)
- **Value** (JSON): {event_id, symbol, instrument_token, price, previous_close, ts, source}
- **Consumer Group**: `portfolio-recompute-group`

## Known Considerations

1. **yfinance Reliability**: May rate-limit or return stale data at high polling frequency. 1-minute interval should be stable; reduce if needed.
2. **Outside Market Hours**: yfinance returns last close outside IST 9:15-15:30 — normal behavior.
3. **Windows Process Management**: No supervisor; use 4+ terminals (or a `.ps1` script) to manage processes.
4. **KRaft Broker**: Requires one-time `kafka-storage.bat format` before first start.
5. **Time-Series Collections**: Insert-only by design; `price_ticks` cannot be updated like `portfolios`.

## Future Enhancements

- `portfolio_snapshots` time-series collection for historical portfolio value snapshots
- Risk analytics layer (VaR, stress testing)
- Alerting rules (price thresholds, portfolio P&L bounds)
- Frontend dashboard (React, real-time WebSocket updates)
- Consumer group scaling (up to 6 instances matching partition count)
