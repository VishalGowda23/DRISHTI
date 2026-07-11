# MongoDB Atlas Migration — Complete Setup

**Date**: 2026-07-11  
**Status**: ✅ All systems consolidated to MongoDB Atlas

---

## What Changed

### ❌ Removed
- **Docker MongoDB service** — no longer needed
- **mongo-express UI** — removed from docker-compose
- **MongoDB initialization script** (`docker/mongo/init-mongo.js`) — replaced with Python setup script
- **Default localhost MongoDB** — was only for local development

### ✅ Added
- **Atlas Index Setup Script** — `scripts/setup_atlas_indexes.py`
- **Atlas connection string** in `.env` (already present)
- **Updated docker-compose.yml** — now reads `MONGODB_URI` from `.env`
- **Updated config.py** — defaults to Atlas database name

---

## Before vs. After

### Before
```
┌─ Local Docker MongoDB (port 27017)
│  ├─ Database: risklens
│  ├─ User: risklens / risklens2026
│  └─ Data: persisted in Docker volume
│
└─ MongoDB Atlas (unused)
   ├─ Database: portfolio_risk
   └─ Credentials: in .env only
```

**Problem**: docker-compose had hardcoded `MONGODB_URI` that overrode .env  
→ Running `docker-compose up` always used Docker MongoDB, not Atlas

### After
```
┌─ MongoDB Atlas (ONLY)
│  ├─ Database: portfolio_risk
│  ├─ Credentials: from .env MONGODB_URI
│  └─ Setup: via scripts/setup_atlas_indexes.py
│
└─ docker-compose.yml
   ├─ No MongoDB service
   ├─ Reads MONGODB_URI from .env
   └─ Connects to Atlas
```

**Benefit**: Single source of truth — all environments use Atlas

---

## Setup Instructions

### 1. Verify .env Configuration

```bash
# Check your .env file
cat risklens-ai/.env | grep MONGODB

# Expected output:
# MONGODB_URI=mongodb+srv://admin:FuukCDSEIqxpXlGu@portfolio-risk.l6t35te.mongodb.net/
# MONGODB_DB_NAME=portfolio_risk
```

✅ Your credentials are already in `.env` — no changes needed.

### 2. Create Collections & Indexes in Atlas

Run the setup script **once** to initialize the database:

```bash
cd risklens-ai
python scripts/setup_atlas_indexes.py
```

**What it does:**
- Creates 8 collections (portfolios, positions, assessments, alerts, etc.)
- Creates all necessary indexes for performance
- Sets up TTL index for market_data (auto-delete after 24h)

**Output example:**
```
✅ Connected to portfolio_risk
Setting up collection: portfolios
  ✓ Created collection
  ✓ Index created: {'status': 1}
  ✓ Index created: {'fund_name': 1}
  ✓ Index created: {'created_at': -1}
...
✅ Database setup complete!
```

### 3. Start Services with docker-compose

Now when you run the full stack, everything connects to Atlas:

```bash
docker-compose -f docker/docker-compose.yml up --build
```

**What's included:**
- ✅ FastAPI Backend (uses .env MONGODB_URI)
- ✅ React Frontend
- ✅ Apache Kafka + Zookeeper
- ✅ Kafka UI (port 8082)

**What's NOT included:**
- ❌ Docker MongoDB (no longer needed)
- ❌ mongo-express (use MongoDB Atlas web UI instead)

### 4. Run Backend Locally (Optional)

If you want to run the backend outside Docker:

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Backend will read `.env` and connect to Atlas automatically.

---

## Accessing Your Data

### MongoDB Atlas Web Console
1. Go to https://cloud.mongodb.com
2. Navigate to your cluster: **portfolio-risk**
3. Click **Collections** tab
4. Browse your data in **portfolio_risk** database

### Kafka UI (while Docker is running)
- URL: `http://localhost:8082`
- View Kafka topics and messages
- Monitor consumer groups

### FastAPI Swagger Docs
- URL: `http://localhost:8000/docs`
- Test all API endpoints interactively

---

## Troubleshooting

### Error: "MongoDB connection failed"

```
Check:
1. MONGODB_URI in .env is correct
2. Atlas cluster IP whitelist includes your IP
   → MongoDB Atlas → Network Access → Add IP
3. Database user credentials are correct
   → MongoDB Atlas → Database Access → Check user
4. Database network is running (not paused)
   → MongoDB Atlas → Clusters → Cluster status
```

### Error: "Could not find module 'motor'"

```bash
# Install dependencies
cd backend
pip install -r requirements.txt
```

### Error: "Index already exists" (first run)

This is normal and safe — the script skips existing indexes:

```
✓ Collection already exists
⚠ Index creation failed: Index with name 'status_1' already exists
```

Can safely ignore these warnings.

---

## Migration Checklist

- [x] Updated `docker-compose.yml` (removed local MongoDB)
- [x] Updated `config.py` (defaults to Atlas)
- [x] Updated `.env.example` (Atlas instructions)
- [x] Created `scripts/setup_atlas_indexes.py` (index setup)
- [x] Verified `.env` has Atlas credentials
- [x] All code uses `.env` MONGODB_URI

---

## Files Changed

| File | Change |
|------|--------|
| `docker/docker-compose.yml` | Removed MongoDB & mongo-express services |
| `backend/app/core/config.py` | Changed default db_name to `portfolio_risk` |
| `.env.example` | Updated with Atlas instructions |
| `scripts/setup_atlas_indexes.py` | NEW — replaces docker init script |

---

## Next Steps

1. ✅ Verify `.env` MONGODB_URI is set (already done)
2. ⏭️ Run `python scripts/setup_atlas_indexes.py`
3. ⏭️ Run `docker-compose -f docker/docker-compose.yml up`
4. ⏭️ Start developing!

---

## Questions?

- **Atlas Connection String**: Check MongoDB Atlas → Connect → Connection String
- **Database Name**: Should be `portfolio_risk` in your Atlas cluster
- **User Credentials**: Should be set in MongoDB Atlas → Database Access
