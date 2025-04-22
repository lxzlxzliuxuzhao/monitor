from fastapi import APIRouter
from app.core.prometheus import query_prometheus

router = APIRouter()

metrics = {
    "cpu_total": "sum(rate(container_cpu_usage_seconds_total[1m]))",
    "cpu_capacity": "sum(machine_cpu_cores)",
    "cpu_percent": "sum(rate(container_cpu_usage_seconds_total[1m])) / sum(machine_cpu_cores)",
    "memory_used": "sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)",
    "memory_total": "sum(node_memory_MemTotal_bytes)",
    "memory_percent": "(sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)) / sum(node_memory_MemTotal_bytes)",
    "disk_avail": "sum(node_filesystem_avail_bytes)",
    "disk_total": "sum(node_filesystem_size_bytes)"
}

@router.get("/{metric}/")
def get_summary(metric: str):
    if metric not in metrics:
        return {"error": "Metric not supported"}
    result = query_prometheus(metrics[metric])
    try:
        value = float(result[0]['value'][1]) if result else 0.0
    except:
        value = 0.0
    return {metric: value}
