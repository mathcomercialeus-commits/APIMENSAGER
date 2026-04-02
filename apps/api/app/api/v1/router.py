from fastapi import APIRouter

from app.api.v1.endpoints import auth, automations, billing, channels, companies, crm, health, iam, meta, ops, runtime, stores


api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_v1_router.include_router(stores.router, prefix="/stores", tags=["stores"])
api_v1_router.include_router(iam.router, prefix="/iam", tags=["iam"])
api_v1_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_v1_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_v1_router.include_router(crm.router, prefix="/crm", tags=["crm"])
api_v1_router.include_router(automations.router, prefix="/automations", tags=["automations"])
api_v1_router.include_router(meta.router, prefix="/meta", tags=["meta"])
api_v1_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_v1_router.include_router(runtime.router, prefix="/runtime", tags=["runtime"])
