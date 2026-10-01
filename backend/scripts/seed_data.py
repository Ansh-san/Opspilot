#!/usr/bin/env python3
"""
Seed script — populates the database with realistic Phase 2 demo data.

IDEMPOTENT: Safe to run multiple times. Existing rows are detected and
skipped; no data is duplicated or deleted.

Strategy: every row uses a deterministic UUID derived from a fixed seed
namespace + a stable key (slug, email, ticket title, …). This means
repeated runs produce the exact same UUIDs, so `INSERT … ON CONFLICT DO
NOTHING` silently skips rows that already exist.

Creates:
  • 1 Organization  (demo-corp)
  • 3 Users         (admin, manager, agent)
  • 15 IT tickets   with varied priority/status/severity
  • 2-3 comments per ticket (mix of human and AI-generated)
  • 1 audit log entry per ticket

Usage (inside Docker):
    docker compose exec backend python scripts/seed_data.py

Usage (local dev):
    cd backend
    DATABASE_URL="postgresql+asyncpg://..." python scripts/seed_data.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# ── make sure 'app' package is importable ────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

import bcrypt as _bcrypt

from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.organization import Organization
from app.db.models.ticket import (
    Ticket,
    TicketComment,
    TicketPriority,
    TicketSeverity,
    TicketStatus,
)
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.ai_run import RiskLevel, AIRun
from app.db.models.user import User, UserRole
from app.db.models.knowledge import (
    KnowledgeDocument,
    KnowledgeChunk,
    DocumentSourceType,
    DocumentStatus,
)
from app.services.chunker import chunk_pages
from app.services.document_processor import RawPage
from app.ai.rag.embedder import get_embedder

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://opspilot:opspilot_secret@localhost:5432/opspilot",
)

# ─── Deterministic UUID namespace ─────────────────────────────────────────────
# All seed IDs are derived from this fixed namespace so repeated runs produce
# identical UUIDs and ON CONFLICT DO NOTHING can skip them safely.
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _did(key: str) -> uuid.UUID:
    """Deterministic ID: uuid5(namespace, key)."""
    return uuid.uuid5(_NS, key)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def _ago(days: int = 0, hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours)


# ─── Seed data definitions ────────────────────────────────────────────────────

TICKET_DATA = [
    {
        "title": "API Gateway returning 500 errors on /v1/payments",
        "description": (
            "Customers are intermittently receiving 500 Internal Server Error responses "
            "when calling the payments API. Error rate is at 12% over the last 30 minutes. "
            "Downstream services may be affected. Logs show NullPointerException in PaymentProcessor."
        ),
        "category": "API",
        "priority": TicketPriority.CRITICAL,
        "severity": TicketSeverity.S1,
        "status": TicketStatus.INVESTIGATING,
        "affected_service": "payment-api",
        "comments": [
            ("Checked the payment-api logs. NullPointerException originates in line 347 of PaymentProcessor.java.", False),
            ("AI Analysis: Root cause is likely a null merchant_id when discount code is applied. Recommend rolling back commit a3f9c12.", True),
            ("Rolling back now. Monitoring error rate.", False),
        ],
    },
    {
        "title": "Database connection pool saturation — auth-service",
        "description": (
            "The auth-service is exhausting its PostgreSQL connection pool (max 100 connections). "
            "New auth requests are queuing and timing out after 30s. This started after the "
            "10:00 AM deployment of auth-service v2.4.1."
        ),
        "category": "Database",
        "priority": TicketPriority.HIGH,
        "severity": TicketSeverity.S2,
        "status": TicketStatus.IN_PROGRESS,
        "affected_service": "auth-service",
        "comments": [
            ("Pool size was increased from 100 to 200 as a temporary fix. Proper fix requires connection pooling refactor.", False),
            ("AI Analysis: PgBouncer should be introduced to manage connection pooling. Configuration template prepared.", True),
        ],
    },
    {
        "title": "Kafka consumer lag exceeding 50k messages",
        "description": (
            "The order-events Kafka consumer group is lagging behind by over 50,000 messages "
            "and increasing. Order fulfilment notifications are delayed. Consumer logs show "
            "repeated rebalancing every 45 seconds."
        ),
        "category": "Messaging",
        "priority": TicketPriority.HIGH,
        "severity": TicketSeverity.S2,
        "status": TicketStatus.INVESTIGATING,
        "affected_service": "order-service",
        "comments": [
            ("Consumer group is rebalancing due to processing timeouts exceeding session.timeout.ms.", False),
            ("AI Analysis: Increase max.poll.interval.ms to 300000 and scale consumer instances to 6.", True),
            ("Scaling to 6 instances now. Lag starting to decrease.", False),
        ],
    },
    {
        "title": "Redis cache miss rate above 80% — recommendation engine",
        "description": (
            "The product recommendation cache is experiencing >80% miss rates. "
            "Uncached requests are hitting the ML inference service directly, "
            "causing 4x latency increase on the product listing page."
        ),
        "category": "Caching",
        "priority": TicketPriority.MEDIUM,
        "severity": TicketSeverity.S3,
        "status": TicketStatus.OPEN,
        "affected_service": "recommendation-service",
        "comments": [
            ("TTL on recommendation keys was accidentally set to 60 seconds instead of 3600 during last deploy.", False),
            ("AI Analysis: Deploy config patch to reset TTL. Expected cache hit rate to recover to >90% within 10 minutes.", True),
        ],
    },
    {
        "title": "SSL certificate expiry warning — api.opspilot.io",
        "description": (
            "SSL certificate for api.opspilot.io expires in 7 days. "
            "Auto-renewal via cert-manager has failed. Manual renewal required. "
            "Let's Encrypt challenge is failing due to DNS misconfiguration."
        ),
        "category": "Security",
        "priority": TicketPriority.HIGH,
        "severity": TicketSeverity.S2,
        "status": TicketStatus.OPEN,
        "affected_service": "api-gateway",
        "comments": [
            ("cert-manager logs show ACME DNS-01 challenge failing. Route53 IAM policy missing route53:ChangeResourceRecordSets.", False),
        ],
    },
    {
        "title": "Memory leak in notification-worker — OOMKilled every 6h",
        "description": (
            "The notification-worker pods are being OOMKilled approximately every 6 hours. "
            "Memory usage grows linearly from 256MB to 1.5GB before the OOMKill. "
            "pprof heap profiles attached. Issue started with v1.8.3."
        ),
        "category": "Infrastructure",
        "priority": TicketPriority.HIGH,
        "severity": TicketSeverity.S2,
        "status": TicketStatus.RESOLVED,
        "affected_service": "notification-worker",
        "comments": [
            ("Heap profile shows WebSocket connections not being garbage collected on client disconnect.", False),
            ("AI Analysis: Missing ws.terminate() in error handler. Patch ready at PR #2847.", True),
            ("PR merged and deployed. Memory stable at 280MB for 3 hours now. Closing.", False),
        ],
    },
    {
        "title": "Grafana alerts not firing — PagerDuty integration broken",
        "description": (
            "Grafana alerts configured to trigger PagerDuty incidents stopped firing "
            "3 hours ago. On-call team has not received any pages. The integration "
            "webhook is returning 401 Unauthorized."
        ),
        "category": "Observability",
        "priority": TicketPriority.CRITICAL,
        "severity": TicketSeverity.S1,
        "status": TicketStatus.IN_PROGRESS,
        "affected_service": "monitoring",
        "comments": [
            ("PagerDuty integration key was rotated during security audit but not updated in Grafana.", False),
            ("Updating integration key in Grafana secrets. Webhook test confirmed working.", False),
        ],
    },
    {
        "title": "S3 bucket policy misconfiguration — staging data exposed",
        "description": (
            "Security scan detected that staging-data-exports S3 bucket has a "
            "public-read ACL on 3 objects containing PII data from 30-day-old exports. "
            "Objects have been confirmed to contain anonymized test data only."
        ),
        "category": "Security",
        "priority": TicketPriority.CRITICAL,
        "severity": TicketSeverity.S1,
        "status": TicketStatus.RESOLVED,
        "affected_service": "data-platform",
        "comments": [
            ("Objects immediately set to private. S3 block public access enabled at account level.", False),
            ("AI Analysis: Recommend implementing S3 Intelligent Tiering and enabling Macie for ongoing PII detection.", True),
        ],
    },
    {
        "title": "Slow queries on orders table — p99 latency > 5s",
        "description": (
            "The orders table is experiencing p99 query latency above 5 seconds during peak hours (6-9 PM). "
            "Table has 48M rows. EXPLAIN ANALYZE shows sequential scans on order_date column. "
            "Missing index suspected."
        ),
        "category": "Database",
        "priority": TicketPriority.MEDIUM,
        "severity": TicketSeverity.S3,
        "status": TicketStatus.IN_PROGRESS,
        "affected_service": "order-service",
        "comments": [
            ("Running EXPLAIN ANALYZE. Confirmed — full sequential scan on orders WHERE order_date > NOW() - INTERVAL '7 days'.", False),
            ("AI Analysis: CREATE INDEX CONCURRENTLY idx_orders_date ON orders(order_date DESC) will fix this without table lock.", True),
        ],
    },
    {
        "title": "CDN cache purge failing for media assets",
        "description": (
            "After product image updates, CDN cache purge requests are returning 422. "
            "Customers are seeing stale product images for up to 24 hours. "
            "Cloudflare API v4 integration may have broken after the API key rotation."
        ),
        "category": "CDN",
        "priority": TicketPriority.MEDIUM,
        "severity": TicketSeverity.S3,
        "status": TicketStatus.OPEN,
        "affected_service": "media-service",
        "comments": [
            ("Cloudflare API key was rotated but the zone_id in config still points to old zone.", False),
        ],
    },
    {
        "title": "CI/CD pipeline failures — Docker build timeouts",
        "description": (
            "GitHub Actions Docker build jobs are timing out after 45 minutes. "
            "The issue appears to be npm install downloading dependencies on each build "
            "instead of using the layer cache."
        ),
        "category": "DevOps",
        "priority": TicketPriority.LOW,
        "severity": TicketSeverity.S4,
        "status": TicketStatus.RESOLVED,
        "affected_service": "ci-cd",
        "comments": [
            ("package-lock.json was not being committed, causing npm install to regenerate on every build.", False),
            ("Added package-lock.json to repo and updated Dockerfile to copy it before npm install for cache reuse.", False),
        ],
    },
    {
        "title": "Elasticsearch disk usage at 92% — alerting index",
        "description": (
            "Elasticsearch alerting index is at 92% disk utilization on all 3 data nodes. "
            "ILM policy is not rolling over indices as expected. Risk of cluster entering "
            "read-only mode in ~6 hours."
        ),
        "category": "Infrastructure",
        "priority": TicketPriority.HIGH,
        "severity": TicketSeverity.S2,
        "status": TicketStatus.INVESTIGATING,
        "affected_service": "elasticsearch",
        "comments": [
            ("ILM policy min_age was set to 90d but should be 7d. Force-rolling index now.", False),
            ("AI Analysis: Recommend Snapshot + Delete policy for indices older than 30 days. Policy template prepared.", True),
        ],
    },
    {
        "title": "User sessions not invalidating on password change",
        "description": (
            "When a user changes their password, existing active sessions (JWT tokens) "
            "remain valid until natural expiry (24h). This is a security regression "
            "introduced in auth-service v2.3.0."
        ),
        "category": "Auth",
        "priority": TicketPriority.HIGH,
        "severity": TicketSeverity.S2,
        "status": TicketStatus.OPEN,
        "affected_service": "auth-service",
        "comments": [
            ("Need to implement token versioning or a JWT revocation list in Redis on password change.", False),
            ("AI Analysis: Add jti (JWT ID) claim and maintain a Redis revocation set. TTL matches token expiry.", True),
        ],
    },
    {
        "title": "Webhook delivery retries exhausted — GitHub integration",
        "description": (
            "GitHub webhook events for repository pushes are not being delivered to our "
            "integration endpoint. GitHub reports 5 consecutive failures and has stopped retrying. "
            "Deploy notifications are broken."
        ),
        "category": "Integrations",
        "priority": TicketPriority.MEDIUM,
        "severity": TicketSeverity.S3,
        "status": TicketStatus.CLOSED,
        "affected_service": "integrations-service",
        "comments": [
            ("Integration endpoint was rejecting events due to signature verification failing after secret rotation.", False),
            ("GitHub webhook secret updated to match new HMAC key. Manual re-delivery confirmed working.", False),
        ],
    },
    {
        "title": "Feature flag service unresponsive — 30% of fleet",
        "description": (
            "LaunchDarkly SDK is timing out on approximately 30% of application instances. "
            "Falling back to default flag values, which disables premium features for affected users. "
            "SDK initialization seems to hang on startup."
        ),
        "category": "Feature Flags",
        "priority": TicketPriority.MEDIUM,
        "severity": TicketSeverity.S3,
        "status": TicketStatus.OPEN,
        "affected_service": "feature-flags",
        "comments": [
            ("SDK is trying to reach stream.launchdarkly.com but egress firewall rule is blocking it on 3 nodes.", False),
            ("AI Analysis: Update firewall rules to allow egress to *.launchdarkly.com:443. Network policy patch ready.", True),
        ],
    },
]


# ─── Idempotent upsert helpers ────────────────────────────────────────────────

async def _upsert_org(db: AsyncSession) -> tuple[uuid.UUID, bool]:
    """Return (org_id, created). Reuses existing org if slug already exists."""
    org_id = _did("org:demo-corp")

    # Check by slug first (the uniqueness constraint that was failing)
    result = await db.execute(
        select(Organization).where(Organization.slug == "demo-corp")
    )
    existing = result.scalar_one_or_none()
    if existing:
        print(f"  ↩  Organization already exists: {existing.name} (id={existing.id})")
        return existing.id, False

    org = Organization(
        id=org_id,
        name="Demo Corp",
        slug="demo-corp",
    )
    db.add(org)
    print(f"  ✓  Organization created: Demo Corp (demo-corp)")
    return org_id, True


async def _upsert_user(
    db: AsyncSession,
    org_id: uuid.UUID,
    email: str,
    full_name: str,
    role: UserRole,
    plain_password: str,
) -> tuple[uuid.UUID, bool]:
    """Return (user_id, created). Skip if email already exists."""
    user_id = _did(f"user:{email}")

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        print(f"  ↩  User already exists: {email}")
        return existing.id, False

    user = User(
        id=user_id,
        org_id=org_id,
        email=email,
        full_name=full_name,
        hashed_password=_hash(plain_password),
        role=role,
        is_active=True,
    )
    db.add(user)
    print(f"  ✓  User created [{role.value:8s}]: {email}")
    return user_id, True


async def _upsert_ticket(
    db: AsyncSession,
    org_id: uuid.UUID,
    requester_id: uuid.UUID,
    index: int,
    tdata: dict,
) -> tuple[uuid.UUID, bool]:
    """Return (ticket_id, created). Skip if deterministic ID already exists."""
    ticket_id = _did(f"ticket:{tdata['title']}")

    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    if result.scalar_one_or_none() is not None:
        label = tdata["title"][:52] + "…" if len(tdata["title"]) > 52 else tdata["title"]
        print(f"  ↩  Ticket already exists: {label}")
        return ticket_id, False

    comments_raw = tdata.pop("comments")

    ticket = Ticket(
        id=ticket_id,
        org_id=org_id,
        requester_id=requester_id,
        created_at=_ago(days=index // 3, hours=(index % 3) * 8),
        updated_at=_ago(days=index // 5, hours=(index % 5) * 3),
        **tdata,
    )
    db.add(ticket)

    for j, (body, is_ai) in enumerate(comments_raw):
        comment_id = _did(f"comment:{tdata['title']}:{j}")
        result2 = await db.execute(select(TicketComment).where(TicketComment.id == comment_id))
        if result2.scalar_one_or_none() is None:
            db.add(TicketComment(
                id=comment_id,
                ticket_id=ticket_id,
                author_id=requester_id,
                body=body,
                is_ai_generated=is_ai,
                created_at=_ago(days=index // 3, hours=(index % 3) * 8 - j - 1),
            ))

    # Audit entry
    audit_id = _did(f"audit:ticket.created:{ticket_id}")
    result3 = await db.execute(select(AuditLog).where(AuditLog.id == audit_id))
    if result3.scalar_one_or_none() is None:
        db.add(AuditLog(
            id=audit_id,
            org_id=org_id,
            actor_id=requester_id,
            actor_type=ActorType.USER,
            event_type="ticket.created",
            resource_type="ticket",
            resource_id=ticket_id,
            details={"title": ticket.title, "priority": ticket.priority.value, "seeded": True},
        ))

    label = tdata["title"][:52] + "…" if len(tdata["title"]) > 52 else tdata["title"]
    print(f"  ✓  Ticket [{str(tdata['priority'].value):8s}] {label}")
    return ticket_id, True


async def _upsert_approval(
    db: AsyncSession,
    org_id: uuid.UUID,
    ticket_id: uuid.UUID,
    requester_id: uuid.UUID,
) -> None:
    """Seed one PENDING high-risk approval request for testing."""
    approval_id = _did(f"approval:{ticket_id}")
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    if result.scalar_one_or_none() is not None:
        print(f"  ↩  Approval already exists for ticket {ticket_id}")
        return

    approval = ApprovalRequest(
        id=approval_id,
        org_id=org_id,
        ticket_id=ticket_id,
        ai_run_id=None,
        proposed_action="restart_production_service",
        action_args={"service_name": "api-gateway"},
        reason="API Gateway returning 500 errors. Restarting service is the standard mitigation.",
        evidence=["Grafana logs show 500 errors", "NullPointerException found in traces"],
        confidence=0.92,
        risk_level=RiskLevel.HIGH,
        status=ApprovalStatus.PENDING,
        requested_by_id=requester_id,
    )
    db.add(approval)
    print(f"  ✓  Approval request created for ticket {ticket_id}")


# ─── Knowledge document seed data ────────────────────────────────────────────

KNOWLEDGE_DOCS = [
    {
        "key": "doc-redis-runbook",
        "title": "Redis Cache Operations Runbook.md",
        "source_type": DocumentSourceType.MARKDOWN,
        "content": """# Redis Cache Operations Runbook

## Overview
This runbook covers common Redis operational tasks for the OpsPilot platform.

## Diagnosing High Cache Miss Rate
1. Connect to the Redis instance: `redis-cli -h redis.internal -p 6379`
2. Check the hit/miss ratio: `INFO stats | grep keyspace`
3. Inspect memory usage: `INFO memory`
4. If max memory is reached, eviction may be causing misses. Adjust `maxmemory-policy` to `allkeys-lru`.
5. Check slow queries: `SLOWLOG GET 10`

## Flushing Stale Cache
- **Targeted flush**: `DEL recommendation:user:*` (use SCAN in production, not KEYS)
- **Full flush (emergency only)**: `FLUSHDB ASYNC`
- After flush, warm the cache by replaying recent requests.

## Scaling Redis
- Monitor with `redis-cli INFO replication`
- Add replicas for read scaling
- Use Redis Cluster for horizontal sharding above 100 GB

## Common Error Codes
- `NOAUTH`: Authentication required — set `requirepass` in config
- `OOM command not allowed`: Memory limit hit — scale up or flush
- `READONLY`: Writing to a replica — redirect to primary
""",
    },
    {
        "key": "doc-incident-response",
        "title": "Incident Response Playbook.md",
        "source_type": DocumentSourceType.MARKDOWN,
        "content": """# Incident Response Playbook

## Severity Levels
- **S1 Critical**: Revenue impact, full outage — respond in 15 min
- **S2 High**: Degraded service, partial outage — respond in 1 hr
- **S3 Medium**: Performance issue, workaround available — respond in 4 hrs
- **S4 Low**: Cosmetic or minor issue — respond in 24 hrs

## Response Steps

### 1. Detect & Acknowledge
- Alerts flow from Grafana → PagerDuty → Slack #incidents
- Acknowledge within SLA or escalate

### 2. Triage
- Identify affected service and blast radius
- Check recent deployments: `kubectl rollout history deployment/<name>`
- Check error rates: Grafana → Service Overview dashboard

### 3. Contain
- Roll back if a deployment caused the incident: `kubectl rollout undo deployment/<name>`
- Enable feature flags to disable broken features
- Scale up replicas if under load: `kubectl scale deployment/<name> --replicas=5`

### 4. Communicate
- Post status update to #incidents every 30 minutes
- Update status page at status.opspilot.io

### 5. Resolve & Post-mortem
- Confirm metrics return to baseline
- Schedule blameless post-mortem within 48 hrs
- Document root cause and action items in Confluence

## Escalation Matrix
| Service | Primary On-Call | Secondary |
|---|---|---|
| API Gateway | platform-team | backend-team |
| Database | dba-team | platform-team |
| Payments | payments-team | finance-eng |
""",
    },
    {
        "key": "doc-kubernetes-ops",
        "title": "Kubernetes Operations Guide.md",
        "source_type": DocumentSourceType.MARKDOWN,
        "content": """# Kubernetes Operations Guide

## Debugging OOMKilled Pods
1. Find killed pods: `kubectl get pods --all-namespaces | grep OOMKilled`
2. Check memory limits: `kubectl describe pod <pod-name>`
3. View memory usage: `kubectl top pod <pod-name>`
4. Increase memory limits in the deployment manifest
5. Investigate memory leak with heap profiling if limits are already generous

## Checking Node Health
```bash
kubectl get nodes -o wide
kubectl describe node <node-name> | grep -A5 Conditions
kubectl top nodes
```

## Draining a Node for Maintenance
```bash
# Cordon (stop new scheduling)
kubectl cordon <node-name>
# Drain (evict existing pods gracefully)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
# After maintenance, uncordon
kubectl uncordon <node-name>
```

## Common Resource Quotas
- API services: 512Mi–1Gi memory, 250m–500m CPU
- Workers: 256Mi–512Mi memory, 100m–250m CPU
- Always set both `requests` and `limits`

## Pod Restart Policy
- `Always` (default): suitable for long-running services
- `OnFailure`: suitable for batch jobs
- `Never`: suitable for one-shot tasks

## Horizontal Pod Autoscaling
```bash
kubectl autoscale deployment <name> --cpu-percent=70 --min=2 --max=10
kubectl get hpa
```
""",
    },
]


async def _upsert_knowledge_docs(
    db: AsyncSession,
    org_id: uuid.UUID,
    uploaded_by: uuid.UUID,
) -> None:
    """Idempotently seed 3 markdown knowledge documents with embeddings."""
    embedder = get_embedder()

    for doc_data in KNOWLEDGE_DOCS:
        doc_id = _did(doc_data["key"])

        # Check if already exists
        existing = await db.get(KnowledgeDocument, doc_id)
        if existing:
            print(f"  ↩  Knowledge doc already exists: {doc_data['title']}")
            continue

        # Create document record
        doc = KnowledgeDocument(
            id=doc_id,
            org_id=org_id,
            title=doc_data["title"],
            source_type=doc_data["source_type"],
            source_path=None,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
            uploaded_by=uploaded_by,
        )
        db.add(doc)
        await db.flush()

        # Chunk the content
        raw_pages = [RawPage(page_number=1, text=doc_data["content"], metadata={"page": 1})]
        chunks = chunk_pages(raw_pages, doc_id, source_title=doc_data["title"])

        # Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = await embedder.embed_many(texts)

        # Insert chunks via raw SQL — omit embedding column so DB defaults to NULL,
        # then UPDATE each chunk with its vector embedding separately.
        import json as _json
        from sqlalchemy import text as sa_text

        chunk_ids = []
        for c in chunks:
            chunk_id = _did(f"{doc_data['key']}-chunk-{c.chunk_index}")
            chunk_ids.append(chunk_id)
            await db.execute(
                sa_text(
                    "INSERT INTO knowledge_chunks "
                    "(id, document_id, org_id, chunk_index, content, chunk_metadata) "
                    "VALUES (:id, :doc_id, :org_id, :idx, :content, CAST(:meta AS jsonb)) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "org_id": org_id,
                    "idx": c.chunk_index,
                    "content": c.content,
                    "meta": _json.dumps(c.chunk_metadata),
                },
            )

        # Update embedding vectors — embed the vector literal directly in SQL
        # because asyncpg rejects :param::vector named-param+cast combos.
        for chunk_id, vec in zip(chunk_ids, embeddings):
            vec_str = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
            await db.execute(
                sa_text(
                    f"UPDATE knowledge_chunks SET embedding = '{vec_str}'::vector"
                    f" WHERE id = :id"
                ),
                {"id": chunk_id},
            )

        doc.status = DocumentStatus.READY
        doc.chunk_count = len(chunk_ids)
        print(f"  ✓  Knowledge doc seeded: {doc_data['title']} ({len(chunk_ids)} chunks)")


async def _upsert_ai_runs(db: AsyncSession, org_id: uuid.UUID) -> None:
    import random
    import json
    from app.db.models.ai_run import AIRun, RiskLevel

    models = ["gpt-4o", "gpt-4-turbo", "claude-3-5-sonnet", "unknown-model"]
    
    # 5 evaluation cases for classification testing
    classification_cases = [
        {"accuracy": 1.0, "status": "EXPECTED", "score": 1.0},
        {"accuracy": 0.66, "status": "WARNING", "score": 0.66},
        {"accuracy": 0.33, "status": "FAIL", "score": 0.33},
        {"accuracy": 1.0, "status": "EXPECTED", "score": 1.0},
        {"accuracy": 1.0, "status": "EXPECTED", "score": 1.0},
    ]

    count = 0
    for i in range(55):
        run_id = _did(f"ai-run-{i}")
        result = await db.execute(select(AIRun).where(AIRun.id == run_id))
        if result.scalar_one_or_none() is not None:
            continue

        model = random.choice(models)
        input_tokens = random.randint(500, 5000)
        output_tokens = random.randint(100, 1000)
        
        # Calculate fake cost for known models
        cost = None
        if model == "gpt-4o":
            cost = (input_tokens / 1000000) * 5.0 + (output_tokens / 1000000) * 15.0
        elif model == "gpt-4-turbo":
            cost = (input_tokens / 1000000) * 10.0 + (output_tokens / 1000000) * 30.0
        elif model == "claude-3-5-sonnet":
            cost = (input_tokens / 1000000) * 3.0 + (output_tokens / 1000000) * 15.0
            
        latency = random.randint(1000, 8000)
        confidence = random.uniform(0.5, 0.99)
        risk = random.choice(list(RiskLevel))
        
        eval_results = []
        
        if i < 5:
            # Classification cases
            case = classification_cases[i]
            eval_results.append({
                "metric_name": "classification_accuracy",
                "score": case["score"],
                "status": case["status"],
                "explanation": f"Rule-based deterministic classification match."
            })
        else:
            # Normal runs
            eval_results.append({
                "metric_name": "retrieval_relevance",
                "score": random.uniform(0.6, 1.0),
                "status": random.choice(["GOOD", "WARNING", "INSUFFICIENT"]),
                "explanation": "Rule-based relevance check"
            })
            eval_results.append({
                "metric_name": "groundedness",
                "score": random.choice([0.0, 1.0]),
                "status": random.choice(["PASS", "FAIL"]),
                "explanation": "Structural check: cited source exists in retrieval context."
            })
            eval_results.append({
                "metric_name": "confidence_sanity",
                "score": 1.0 if confidence > 0.8 else 0.0,
                "status": random.choice(["GOOD", "CRITICAL"]),
                "explanation": "Matrix-based confidence check."
            })

        run = AIRun(
            id=run_id,
            org_id=org_id,
            model_used=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency,
            confidence=confidence,
            risk_level=risk,
            evaluation_results=eval_results,
            is_synthetic=True,
            created_at=_ago(days=random.randint(0, 30), hours=random.randint(0, 23))
        )
        db.add(run)
        count += 1
        
    if count > 0:
        print(f"  ✓  AI Runs seeded: {count} historical runs")
    else:
        print(f"  ↩  AI Runs already exist")


# ─── Main seeder ──────────────────────────────────────────────────────────────

async def seed(db: AsyncSession) -> None:
    print("🌱 OpsPilot — idempotent demo data seeder\n")

    # ── Organization ──────────────────────────────────────────────────────────
    org_id, _ = await _upsert_org(db)

    # Flush org so FK constraints are satisfied for users
    await db.flush()

    # ── Users ─────────────────────────────────────────────────────────────────
    print()
    admin_id, _ = await _upsert_user(db, org_id, "admin@demo-corp.io",   "Alex Admin",    UserRole.ADMIN,   "AdminPass1")
    manager_id, _ = await _upsert_user(db, org_id, "manager@demo-corp.io", "Morgan Manager", UserRole.MANAGER, "ManagerPass1")
    agent_id, _ = await _upsert_user(db, org_id, "agent@demo-corp.io",   "Sam Agent",     UserRole.AGENT,   "AgentPass1")

    await db.flush()

    # ── AI Runs ───────────────────────────────────────────────────────────────
    await _upsert_ai_runs(db, org_id)
    await db.commit()

    # ── Tickets + Comments + Audit ────────────────────────────────────────────
    print(f"\n  Processing {len(TICKET_DATA)} tickets…\n")
    requester_cycle = [admin_id, manager_id, agent_id]

    for i, tdata in enumerate(TICKET_DATA):
        # Pop comments before passing tdata to Ticket constructor
        tdata_copy = dict(tdata)  # shallow copy so original list stays intact
        ticket_id, _ = await _upsert_ticket(db, org_id, requester_cycle[i % 3], i, tdata_copy)
        if i == 0:
            await _upsert_approval(db, org_id, ticket_id, admin_id)

    await db.commit()

    # ── Knowledge documents ───────────────────────────────────────────────────
    print(f"\n  Seeding knowledge documents…\n")
    await _upsert_knowledge_docs(db, org_id, admin_id)
    await db.commit()

    print(f"\n✅ Seed complete — all records in place (new rows created or existing rows skipped).")
    print(f"\n📋 Login credentials:")
    print(f"   Admin:   admin@demo-corp.io   / AdminPass1")
    print(f"   Manager: manager@demo-corp.io / ManagerPass1")
    print(f"   Agent:   agent@demo-corp.io   / AgentPass1")
    print(f"   Frontend: http://localhost:3000")
    print(f"   API docs: http://localhost:8000/api/v1/docs")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
