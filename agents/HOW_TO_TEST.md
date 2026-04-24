# How to Verify Trinetra Agents (Redis + FastAPI)

This project runs on Redis Pub/Sub and FastAPI backend APIs.

## Prerequisites
1. **Redis Running** at `redis://localhost:6379`
2. **Backend Running** at `http://localhost:8000`
3. **Dependencies**:
   ```bash
   pip install redis requests flask
   ```

## Step 1: Start backend
```bash
cd backend
python main.py
```

## Step 2: Start agents
```bash
cd agents
./start_all_agents.sh
```

## Step 3: Trigger pipeline
Use the Redis-based pipeline test:
```bash
python agents/test_pipeline.py
```

## Step 4: Verify state and events
1. Fetch UCSO:
   ```bash
   curl http://localhost:8000/api/application/<application_id>
   ```
2. Watch logs:
   ```bash
   tail -f agents/logs/*.log
   ```
3. Verify websocket status feed from `/ws/<application_id>`.

## Full-chain sanity flow
1. Create application via `POST /api/application`
2. Upload required docs via `POST /api/files/upload`
3. Confirm `agent_status` events are emitted
4. Validate `risk`, `stress_results`, `bias_checks`, and `cam_output` namespaces populate in UCSO
