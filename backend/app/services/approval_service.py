import logging
import time
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.policy.engine import PolicyEngine
from app.ai.policy.rules import PolicyDecision
from app.ai.tools.registry import tool_registry
from app.db.models.ai_run import AIRun
from app.db.models.ai_run import RiskLevel
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.audit_log import ActorType
from app.db.models.ticket import Ticket
from app.db.models.tool_execution import ToolExecution
from app.db.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class ApprovalService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    async def create_approval_request(self, payload: Any, current_user: User) -> ApprovalRequest:
        """Create a PENDING approval request from a human-submitted AI recommendation."""
        ticket = await self._db.get(Ticket, payload.ticket_id)
        if not ticket or ticket.org_id != current_user.org_id:
            raise HTTPException(status_code=404, detail="Ticket not found.")

        if payload.ai_run_id:
            ai_run = await self._db.get(AIRun, payload.ai_run_id)
            if not ai_run or ai_run.org_id != current_user.org_id:
                raise HTTPException(status_code=404, detail="AI run not found.")

        try:
            risk = RiskLevel(payload.risk_level.lower())
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid risk_level.")
        if risk == RiskLevel.BLOCKED:
            raise HTTPException(status_code=422, detail="Blocked actions cannot be submitted for approval.")

        # Avoid duplicate pending requests for the same run + action
        if payload.ai_run_id:
            dup = await self._db.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.org_id == current_user.org_id,
                    ApprovalRequest.ai_run_id == payload.ai_run_id,
                    ApprovalRequest.proposed_action == payload.recommended_action,
                    ApprovalRequest.status == ApprovalStatus.PENDING,
                )
            )
            existing = dup.scalars().first()
            if existing:
                return existing

        approval = ApprovalRequest(
            id=uuid.uuid4(),
            org_id=current_user.org_id,
            ticket_id=payload.ticket_id,
            ai_run_id=payload.ai_run_id,
            proposed_action=payload.recommended_action,
            action_args={},
            reason=payload.reason or f"AI recommended action requires human approval ({risk.value} risk).",
            evidence=payload.evidence,
            confidence=payload.confidence,
            risk_level=risk,
            status=ApprovalStatus.PENDING,
            requested_by_id=current_user.id,
        )
        self._db.add(approval)
        await self._db.flush()

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="approval.created",
            resource_type="approval_request",
            resource_id=approval.id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={"proposed_action": payload.recommended_action, "status": "pending", "manual": True},
        )
        await self._db.commit()
        await self._db.refresh(approval)
        return approval

    async def evaluate_and_route_proposal(
        self,
        ticket_id: uuid.UUID,
        ai_run_id: uuid.UUID,
        proposed_action: str,
        action_args: dict[str, Any],
        current_user: User,
    ) -> ApprovalRequest | None:
        """
        Evaluate a proposed action using the PolicyEngine.
        If BLOCKED, reject immediately.
        If REQUIRE_APPROVAL, create a PENDING ApprovalRequest.
        If AUTO_EXECUTE, create an APPROVED ApprovalRequest and execute it immediately.
        """
        # Evaluate policy
        policy_result = PolicyEngine.evaluate(proposed_action, action_args, {})

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="policy.evaluated",
            resource_type="ticket",
            resource_id=ticket_id,
            actor_id=current_user.id,
            actor_type=ActorType.SYSTEM,
            details={"decision": policy_result.decision.value, "risk": policy_result.risk_level.value, "reason": policy_result.reason}
        )

        if policy_result.decision == PolicyDecision.REJECT:
            logger.warning("Action %s blocked by policy: %s", proposed_action, policy_result.reason)
            return None

        # Create approval record
        approval = ApprovalRequest(
            id=uuid.uuid4(),
            org_id=current_user.org_id,
            ticket_id=ticket_id,
            ai_run_id=ai_run_id,
            proposed_action=proposed_action,
            action_args=action_args,
            reason=policy_result.reason,
            evidence=[],
            confidence=1.0,  # Or passed from agent
            risk_level=policy_result.risk_level.value,
            status=ApprovalStatus.PENDING,
            requested_by_id=current_user.id,
        )
        self._db.add(approval)
        await self._db.flush()

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="approval.created",
            resource_type="approval_request",
            resource_id=approval.id,
            actor_id=current_user.id,
            actor_type=ActorType.SYSTEM,
            details={"proposed_action": proposed_action, "status": approval.status}
        )

        if policy_result.decision == PolicyDecision.AUTO_EXECUTE:
            # Auto-approve
            approval.status = ApprovalStatus.APPROVED
            approval.reviewed_by_id = current_user.id
            approval.review_note = "Auto-executed by Policy Engine (LOW risk)"
            await self._db.flush()
            # Execute immediately
            await self._execute_approval(approval.id, current_user, auto=True)

        return approval

    async def approve_request(self, approval_id: uuid.UUID, current_user: User, note: str = "") -> dict[str, Any]:
        """Human approval of a PENDING request. Prevents stale execution via FOR UPDATE lock."""
        # 1. Fetch with FOR UPDATE to prevent race conditions
        result = await self._db.execute(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.org_id == current_user.org_id
            )
            .with_for_update()
        )
        approval = result.scalar_one_or_none()

        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found.")

        # 2. Re-check status (Stale Approval Race Condition defense)
        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval is no longer PENDING (current status: {approval.status})."
            )

        # 3. RBAC: Prevent self-approval
        if approval.requested_by_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot approve an action that you requested/triggered."
            )

        # 4. Update status
        approval.status = ApprovalStatus.APPROVED
        approval.reviewed_by_id = current_user.id
        approval.review_note = note
        
        await self._audit.log(
            org_id=current_user.org_id,
            event_type="approval.approved",
            resource_type="approval_request",
            resource_id=approval.id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={"note": note}
        )
        
        await self._db.flush()

        # 5. Execute
        execution_result = await self._execute_approval(approval.id, current_user, auto=False)
        await self._db.commit()
        return execution_result

    async def reject_request(self, approval_id: uuid.UUID, current_user: User, note: str = "") -> None:
        """Reject a PENDING request."""
        result = await self._db.execute(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.org_id == current_user.org_id
            )
            .with_for_update()
        )
        approval = result.scalar_one_or_none()

        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found.")
            
        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval is no longer PENDING (current status: {approval.status})."
            )

        approval.status = ApprovalStatus.REJECTED
        approval.reviewed_by_id = current_user.id
        approval.review_note = note

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="approval.rejected",
            resource_type="approval_request",
            resource_id=approval.id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={"note": note}
        )
        await self._db.commit()

    async def _execute_approval(self, approval_id: uuid.UUID, current_user: User, auto: bool = False) -> dict[str, Any]:
        """Internal execution flow (assumes lock is held)."""
        approval = await self._db.get(ApprovalRequest, approval_id)
        
        # We re-fetch the ticket to ensure it's not closed
        ticket = await self._db.get(Ticket, approval.ticket_id)
        if ticket.status.value in ("closed", "resolved"):
            approval.status = ApprovalStatus.FAILED
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot execute action: ticket is already closed/resolved."
            )

        start_ms = int(time.monotonic() * 1000)
        tool = tool_registry.get_tool(approval.proposed_action)
        
        # Re-validate args via registry is automatic inside execute_tool,
        # but we also wrap it to catch ToolExecutionError.
        
        execution = ToolExecution(
            id=uuid.uuid4(),
            org_id=current_user.org_id,
            ai_run_id=approval.ai_run_id,
            approval_id=approval.id,
            tool_name=approval.proposed_action,
            args=approval.action_args,
            is_simulated=tool.is_simulated if tool else True
        )
        self._db.add(execution)
        await self._db.flush()

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="tool.execution_started",
            resource_type="tool_execution",
            resource_id=execution.id,
            actor_id=current_user.id if not auto else None,
            actor_type=ActorType.USER if not auto else ActorType.SYSTEM,
            details={"tool": approval.proposed_action, "auto_executed": auto}
        )
        
        try:
            if tool is None:
                # Free-text AI recommendation with no registered tool: record the
                # human approval and acknowledge it as a simulated/manual action.
                result = {
                    "simulated": True,
                    "message": "Recommendation approved by a human reviewer; no automated tool is registered, so it was recorded as a manual action.",
                }
            else:
                result = await tool_registry.execute_tool(approval.proposed_action, approval.action_args)
            execution.success = True
            execution.result = result
            approval.status = ApprovalStatus.EXECUTED
        except Exception as e:
            execution.success = False
            execution.error_message = str(e)
            approval.status = ApprovalStatus.FAILED
            logger.error("Tool execution failed: %s", e)

        latency_ms = int(time.monotonic() * 1000) - start_ms

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="tool.execution_succeeded" if execution.success else "tool.execution_failed",
            resource_type="tool_execution",
            resource_id=execution.id,
            actor_id=current_user.id if not auto else None,
            actor_type=ActorType.USER if not auto else ActorType.SYSTEM,
            details={
                "tool": approval.proposed_action,
                "latency_ms": latency_ms,
                "auto_executed": auto
            }
        )
        
        return {
            "success": execution.success,
            "result": execution.result,
            "error": execution.error_message
        }

    async def list_approvals(self, current_user: User, status_filter: str | None = None) -> list[ApprovalRequest]:
        query = select(ApprovalRequest).where(ApprovalRequest.org_id == current_user.org_id)
        if status_filter:
            try:
                status_enum = ApprovalStatus(status_filter.lower())
                query = query.where(ApprovalRequest.status == status_enum)
            except ValueError:
                pass
        query = query.order_by(ApprovalRequest.created_at.desc())
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def get_approval(self, approval_id: uuid.UUID, current_user: User) -> ApprovalRequest:
        result = await self._db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.org_id == current_user.org_id
            )
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        return approval
