"""Observability Service for AI Agent KPIs and Traces."""

import uuid
from typing import Dict, Any, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ai_run import AIRun


class ObservabilityService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_kpis(self, org_id: uuid.UUID) -> Dict[str, Any]:
        """Calculates aggregated KPIs directly in PostgreSQL using SQL-level aggregation."""
        from sqlalchemy import text
        
        stmt = text("""
            SELECT 
                count(*) as total_runs,
                sum(case when decision is not null then 1 else 0 end) as successful_runs,
                avg(latency_ms) as avg_latency,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) as p50_latency,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
                sum(coalesce(input_tokens, 0) + coalesce(output_tokens, 0)) as total_tokens,
                sum(coalesce(estimated_cost_usd, 0.0)) as total_cost,
                sum(case when risk_level = 'blocked' then 1 else 0 end) as blocked_count,
                (SELECT count(*) FROM approval_requests WHERE org_id = :org_id) as total_approvals,
                (SELECT count(*) FROM approval_requests WHERE org_id = :org_id AND status = 'approved') as approved_count,
                (SELECT count(*) FROM approval_requests WHERE org_id = :org_id AND status = 'rejected') as rejected_count,
                (SELECT count(*) FROM tool_executions WHERE org_id = :org_id) as total_tools,
                (SELECT count(*) FROM tool_executions WHERE org_id = :org_id AND success = true) as successful_tools
            FROM ai_runs
            WHERE org_id = :org_id AND is_synthetic = false
        """)
        
        result = await self._db.execute(stmt, {"org_id": str(org_id)})
        row = result.first()
        
        if not row or row.total_runs == 0:
            return {
                "total_runs": 0,
                "success_rate": None,
                "avg_latency": None,
                "p50_latency": None,
                "p95_latency": None,
                "total_tokens": 0,
                "total_cost": 0.0,
                "approval_rate": None,
                "rejection_rate": None,
                "tool_success_rate": None,
                "blocked_count": 0,
            }
            
        total_runs = row.total_runs or 0
        successful_runs = row.successful_runs or 0
        success_rate = (successful_runs / total_runs) if total_runs > 0 else None
        
        total_approvals = row.total_approvals or 0
        approved_count = row.approved_count or 0
        rejected_count = row.rejected_count or 0
        
        total_tools = row.total_tools or 0
        successful_tools = row.successful_tools or 0

        return {
            "total_runs": total_runs,
            "success_rate": success_rate,
            "avg_latency": float(row.avg_latency) if row.avg_latency else None,
            "p50_latency": float(row.p50_latency) if row.p50_latency else None,
            "p95_latency": float(row.p95_latency) if row.p95_latency else None,
            "total_tokens": int(row.total_tokens) if row.total_tokens else 0,
            "total_cost": float(row.total_cost) if row.total_cost else 0.0,
            "approval_rate": (approved_count / total_approvals) if total_approvals > 0 else None,
            "rejection_rate": (rejected_count / total_approvals) if total_approvals > 0 else None,
            "tool_success_rate": (successful_tools / total_tools) if total_tools > 0 else None,
            "blocked_count": int(row.blocked_count) if row.blocked_count else 0,
        }

    async def list_runs(
        self, org_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> Sequence[AIRun]:
        """Lists paginated AI runs for an organization."""
        stmt = (
            select(AIRun)
            .where(AIRun.org_id == org_id)
            .where(AIRun.is_synthetic == False)
            .order_by(AIRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_run_trace(
        self, org_id: uuid.UUID, ai_run_id: uuid.UUID
    ) -> AIRun | None:
        """Fetches a full AI run trace with eager loaded relationships (preventing N+1 queries)."""
        stmt = (
            select(AIRun)
            .options(
                selectinload(AIRun.ticket),
                selectinload(AIRun.approval),
                selectinload(AIRun.tool_executions),
            )
            .where(AIRun.id == ai_run_id)
            .where(AIRun.org_id == org_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
