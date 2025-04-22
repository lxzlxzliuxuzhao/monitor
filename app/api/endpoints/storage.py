from fastapi import APIRouter
from app.core.prometheus import query_prometheus
from app.models.responses import format_simple_metric

router = APIRouter()

@router.get("/")
def get_storage():
    mem_query = 'node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes'
    disk_query = 'node_filesystem_avail_bytes'
    return {
        "memory_used_bytes": format_simple_metric(query_prometheus(mem_query), "memory_used"),
        "disk_available_bytes": format_simple_metric(query_prometheus(disk_query), "disk_free")
    }
