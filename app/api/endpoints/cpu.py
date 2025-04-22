from fastapi import APIRouter
from app.core.prometheus import query_prometheus
from app.models.responses import format_cpu_response

router = APIRouter()

@router.get("/")
def get_cpu_usage():
    query = 'rate(container_cpu_usage_seconds_total[1m])'
    return format_cpu_response(query_prometheus(query))
