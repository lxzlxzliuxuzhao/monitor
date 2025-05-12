import importlib
import pkgutil
from fastapi import APIRouter

def auto_load_routers() -> APIRouter:
    router = APIRouter()
    package = "app.api.endpoints"
    for _, module_name, _ in pkgutil.iter_modules(["app/api/endpoints"]):
        module = importlib.import_module(f"{package}.{module_name}")
        if hasattr(module, "router"):
            router.include_router(module.router)
    return router
