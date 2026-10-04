# Celery + Redis Implementation Guide
## OpsMind AI - Distributed Background Task Processing

---

## 📋 Executive Summary

**What we built:** A production-grade distributed background task processing system using **Celery + Redis** that replaces FastAPI's in-process background tasks with scalable, monitored, fault-tolerant workers.

**Why it matters for interviews:** Demonstrates senior-level understanding of distributed systems, async architecture, observability, and production operations.

---

## 🎯 The Problem: Before vs After

### ❌ BEFORE (FastAPI Lifespan Background Tasks)

```python
# app/main.py - OLD WAY
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background tasks running INSIDE the API process
    asyncio.create_task(poll_mailbox_loop())  # Blocks event loop!
    asyncio.create_task(smtp_dispatch_loop())
    yield
```

| Issue | Impact |
|-------|--------|
| **Single process** | API + background work share same CPU/memory |
| **No scaling** | Can't add more workers for heavy load |
| **Crash = data loss** | Worker dies → in-progress tasks lost |
| **No visibility** | Can't see what's running, failed, or queued |
| **Blocking** | Long tasks slow down API responses |
| **No retries** | Failed email = lost notification |

---

### ✅ AFTER (Celery + Redis Distributed Workers)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   FastAPI API   │────▶│     Redis       │◀───▶│  Celery Workers │
│  (Port 8000)    │     │  (Port 6379)    │     │  (4 threads)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐     ┌─────────────────┐
                       │  Celery Beat    │     │     Flower      │
                       │  (Scheduler)    │     │  (Monitoring)   │
                       └─────────────────┘     └─────────────────┘
```

| Feature | Implementation |
|---------|----------------|
| **Horizontal scaling** | `docker-compose up --scale celery-worker=3` |
| **Fault tolerance** | Auto-retry with exponential backoff (3 attempts) |
| **Dead letter queue** | Failed tasks → separate queue for inspection |
| **Full observability** | Flower UI: real-time tasks, workers, success rates |
| **Scheduled tasks** | Beat: IMAP polling every 30s, persistent schedule |
| **Idempotency** | Task IDs prevent duplicate processing |

---

## 🏗️ Architecture Components

### 1. **Celery App Configuration** (`backend/app/workers/celery_app.py`)

```python
celery_app = Celery(
    "opsmind",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_autoretry_for=(Exception,),
    task_retry_backoff=True,
    task_retry_backoff_max=600,
    task_retry_jitter=True,
    # Dead letter queue
    task_queues={
        "default": {},
        "dlq": {"routing_key": "dlq"},
    },
)

# Beat Schedule - Periodic Tasks
beat_schedule = {
    "poll-mailbox-every-30-seconds": {
        "task": "app.workers.tasks.poll_mailbox_task",
        "schedule": 30.0,
    },
}
```

**Key configs explained:**
- `task_acks_late=True` - Acknowledge AFTER completion (not before) → no lost tasks
- `task_reject_on_worker_lost=True` - Requeue if worker dies mid-task
- `task_autoretry_for=(Exception,)` - Auto-retry on ANY exception
- `task_retry_backoff=True` - Exponential backoff: 2s → 4s → 8s → 16s...
- `beat_schedule` - Declarative scheduling (no cron needed)

---

### 2. **Background Tasks** (`backend/app/workers/tasks.py`)

| Task | Purpose | Trigger |
|------|---------|---------|
| `poll_mailbox_task` | Check IMAP for new emails | Beat: every 30s |
| `process_single_email_task` | Parse email, extract order | Manual / chained |
| `extract_order_task` | AI extraction + catalog matching | Manual / chained |
| `dispatch_smtp_email_task` | Send email via SMTP | Manual / chained |
| `notify_customer_task` | Status change notifications | Manual / chained |

**Task signature example:**
```python
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    queue="default"
)
def poll_mailbox_task(self) -> dict:
    """Poll IMAP mailbox for new unread emails."""
    # ... implementation
    return {"polled": True, "count": n, "processed_orders": [...]}
```

---

### 3. **Docker Orchestration** (`docker-compose.yml`)

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  celery-worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker -l info --pool=threads -c 4
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      replicas: 1  # Scale with: docker-compose up --scale celery-worker=3

  celery-beat:
    build: ./backend
    command: celery -A app.workers.celery_app beat -l info --scheduler celery.beat:PersistentScheduler
    depends_on:
      redis:
        condition: service_healthy

  flower:
    build: ./backend
    command: celery -A app.workers.celery_app flower --port=5555
    ports: ["5555:5555"]
    depends_on:
      redis:
        condition: service_healthy
```

**Windows Fix:** `--pool=threads` instead of default `--pool=prefork` (Windows multiprocessing bug)

---

### 4. **Integration with FastAPI** (`backend/app/main.py` + `email_service.py`)

**Old (removed from lifespan):**
```python
# REMOVED - was blocking API
asyncio.create_task(poll_mailbox_loop())
```

**New (delegated to Celery):**
```python
# app/services/email_service.py
async def _dispatch_real_smtp_email(self, to_email, subject, body):
    # Fire-and-forget via Celery
    dispatch_smtp_email_task.delay(to_email, subject, body)
    return {"status": "queued", "message": "Email queued for delivery"}
```

**API stays fast** - returns immediately, Celery handles delivery in background.

---

## 🔄 Message Flow: End-to-End

```
1. EMAIL ARRIVES (IMAP)
         │
         ▼
2. BEAT SCHEDULER (every 30s)
   └─▶ poll_mailbox_task.delay()
         │
         ▼
3. REDIS QUEUE (broker)
   └─▶ Task serialized as JSON
         │
         ▼
4. CELERY WORKER (1 of 4 threads)
   ├─▶ Fetch task
   ├─▶ Execute: IMAP fetch → Parse → Extract → Validate
   ├─▶ On success: Return result → Redis backend
   ├─▶ On failure: Retry (2s, 4s, 8s...) → Max 3 → DLQ
   └─▶ Ack message (task_acks_late=True)
         │
         ▼
5. FLOWER UI (Real-time)
   ├─▶ Task: STARTED → SUCCESS/FAILURE
   ├─▶ Worker: Online/Offline
   ├─▶ Queue depth, throughput, latency
   └─▶ History: 7 days retained
```

---

## 📊 Flower Monitoring Dashboard

**URL:** http://localhost:5555

### Key Panels:

| Tab | What You See | Interview Talking Point |
|-----|--------------|------------------------|
| **Workers** | Online/offline, concurrency, load | "Horizontal scaling - add workers dynamically" |
| **Tasks** | Real-time list: ID, name, args, state, runtime | "Full traceability - every task tracked" |
| **Tasks → Detail** | Stack trace on failure, retry count | "Debugging production issues in seconds" |
| **Monitor** | Throughput graph (tasks/sec) | "Capacity planning - see peak loads" |
| **Brokers** | Queue depths, memory usage | "Backpressure detection before OOM" |

### Task States Visualized:
```
PENDING → STARTED → SUCCESS (green)
                ↘ RETRY (yellow) → SUCCESS/FAILURE
                ↘ FAILURE (red) → DLQ
```

---

## 🛡️ Production-Grade Features Implemented

### 1. **Retry with Exponential Backoff**
```python
# Automatic: 2s → 4s → 8s → 16s → 32s → 60s (max)
task_retry_backoff=True
task_retry_backoff_max=600
task_retry_jitter=True  # Prevents thundering herd
```

### 2. **Dead Letter Queue (DLQ)**
```python
# Failed tasks after max retries → routed to 'dlq' queue
# Inspect manually: celery -A app.workers.celery_app inspect dump
```

### 3. **Idempotency via Task IDs**
```python
# Each task has unique UUID
task_id = "550e8400-e29b-41d4-a716-446655440000"
# Deduplication: same task_id = same work, not re-executed
```

### 4. **Graceful Shutdown**
```python
# SIGTERM → finish current task → ack → exit
# No in-progress work lost
```

### 5. **Health Checks**
```yaml
# Docker healthchecks for all services
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 5s
```

---

## 📈 Scaling Strategies

### Horizontal Scaling (More Workers)
```bash
# Scale to 3 workers (12 threads total)
docker-compose up --scale celery-worker=3 -d

# Or Kubernetes HPA based on queue depth
```

### Vertical Scaling (More Threads)
```yaml
# docker-compose.yml
command: celery -A app.workers.celery_app worker -l info --pool=threads -c 8
```

### Queue Separation (Priority)
```python
# High priority: customer notifications
notify_customer_task.apply_async(queue="high")

# Low priority: batch processing
process_batch_task.apply_async(queue="low")

# Worker per queue:
# celery -A app.workers.celery_app worker -Q high -c 2
# celery -A app.workers.celery_app worker -Q default,low -c 4
```

---

## 🧪 Testing Commands

```bash
# 1. Verify worker connectivity
celery -A app.workers.celery_app inspect ping
# → pong

# 2. View active tasks
celery -A app.workers.celery_app inspect active

# 3. View registered tasks
celery -A app.workers.celery_app inspect registered

# 4. View queue stats
celery -A app.workers.celery_app inspect stats

# 5. Manual task trigger
python -c "
from app.workers.tasks import extract_order_task
r = extract_order_task.delay('test@email.com', 'Order', 'I need 5 widgets')
print(r.get(timeout=30))
"

# 6. Purge all queues (dev only)
celery -A app.workers.celery_app purge
```

---

## 💡 Interview Q&A Cheat Sheet

### Q: "Why Celery over FastAPI BackgroundTasks?"
**A:** BackgroundTasks runs in-process, shares event loop. Celery provides:
- Process isolation (crash doesn't kill API)
- Horizontal scaling (add workers)
- Persistence (Redis survives restarts)
- Retries, scheduling, monitoring built-in

### Q: "How do you handle task failures?"
**A:** 3-layer approach:
1. **Auto-retry** with exponential backoff (3 attempts)
2. **Dead letter queue** for failed tasks after retries
3. **Flower alerts** + manual replay from DLQ

### Q: "How do you ensure idempotency?"
**A:** Task IDs + database-level deduplication:
- Each inbound email gets unique `message_id`
- Before processing: check if `EmailMessage(message_id=...)` exists
- If yes → skip (already processed)

### Q: "How do you monitor in production?"
**A:** Flower (real-time) + Prometheus metrics + structured logs:
- Task success rate, latency p50/p99
- Queue depth → auto-scale trigger
- Worker CPU/memory → capacity planning

### Q: "What's the Windows multiprocessing issue?"
**A:** Default `prefork` pool uses `fork()` which doesn't exist on Windows.
**Fix:** `--pool=threads` or `--pool=solo` (production: Linux containers)

### Q: "How does Beat scheduler persist schedule?"
**A:** `PersistentScheduler` writes to `celerybeat-schedule` file (or DB).
Survives restarts - no duplicate/missed runs.

---

## 🚀 Deployment Checklist

- [ ] Redis: `maxmemory-policy allkeys-lru` (prevent OOM)
- [ ] Celery: `task_acks_late=True` (no lost tasks)
- [ ] Beat: `PersistentScheduler` (survive restarts)
- [ ] Workers: `--pool=threads` on Windows, `prefork` on Linux
- [ ] Monitoring: Flower behind auth (basic auth / VPN)
- [ ] Logs: Structured JSON → ELK/Datadog
- [ ] Alerts: Task failure rate > 5%, queue depth > 1000
- [ ] Backup: Redis RDB/AOF, beat schedule file
- [ ] Security: Redis `requirepass`, TLS in prod

---

## 📁 Files Modified/Created

| File | Purpose |
|------|---------|
| `backend/app/workers/celery_app.py` | Celery config, beat schedule, retry policy |
| `backend/app/workers/tasks.py` | 5 background task definitions |
| `backend/app/workers/__init__.py` | Export celery_app |
| `backend/app/main.py` | Removed lifespan background tasks |
| `backend/app/services/email_service.py` | SMTP dispatch via Celery |
| `docker-compose.yml` | Added redis, celery-worker, celery-beat, flower |
| `backend/requirements.txt` | Added `celery>=5.3.6`, `flower>=2.0.1` |

---

## 🎓 Key Takeaways for Interview

1. **Architecture decision**: Moved from in-process to distributed → shows system design maturity
2. **Reliability patterns**: Retry, DLQ, idempotency, graceful shutdown → production mindset
3. **Observability**: Flower + structured logging → debugging skills
4. **Scalability**: Horizontal scaling, queue separation → growth planning
5. **Windows/Linux parity**: Pool configuration → cross-platform awareness
6. **Docker orchestration**: Health checks, depends_on, scaling → DevOps basics

---

## 🔗 Related Documentation

- [FastAPI + Celery Best Practices](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html)
- [Flower Monitoring Guide](https://flower.readthedocs.io/)
- [Redis as Message Broker](https://redis.io/docs/manual/pubsub/)
- [Celery Windows Workers](https://docs.celeryq.dev/en/stable/faq.html#windows)

---

*Generated for OpsMind AI Portfolio Project - Demonstrates Senior AI/Backend Engineering Competency*