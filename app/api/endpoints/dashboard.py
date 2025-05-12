from fastapi import APIRouter
from app.services.dashboard import (
    get_server_overview,
    get_network_status,
    get_compute_usage,
    get_storage_usage,
)

router = APIRouter(prefix="/dashboard")

@router.get("/server-overview")
def server_overview():
    return get_server_overview()

@router.get("/network")
def network():
    return get_network_status()

@router.get("/compute")
def compute():
    return get_compute_usage()

@router.get("/storage")
def storage():
    return get_storage_usage()
