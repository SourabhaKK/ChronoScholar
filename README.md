# ChronoScholar

## Running the Demo

### 1. Start the server
```bash
docker-compose up
# OR locally:
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

### 2. Verify graph is loaded
```bash
curl http://localhost:8000/ready
# Must return: {"ready": true, "entity_count": 118, "edge_count": 203}
# If not ready, run: python scripts/seed_corpus.py
```

### 3. Pre-warm comparison cache (run before presenting)
```bash
python scripts/prewarm_cache.py
# Takes 30-120 seconds on first run, then all /compare calls are instant
```

### 4. Open the UI
http://localhost:8000