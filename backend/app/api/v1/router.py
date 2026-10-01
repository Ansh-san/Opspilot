from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.tickets import router as tickets_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(tickets_router)
api_router.include_router(knowledge_router)
api_router.include_router(agents_router)

from app.api.v1.audit import router as audit_router

api_router.include_router(audit_router)

from app.api.v1.approvals import router as approvals_router

api_router.include_router(approvals_router)

from app.api.v1.observability import router as observability_router

api_router.include_router(observability_router)

from app.api.v1.evaluations import router as evaluations_router

api_router.include_router(evaluations_router)

# Phase 5+ routers will be added here:
# from app.api.v1.evaluations import router as evaluations_router
# from app.api.v1.settings import router as settings_router
