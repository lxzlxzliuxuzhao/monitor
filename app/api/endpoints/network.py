from fastapi import APIRouter
from app.core.prometheus import query_prometheus
from app.models.responses import format_simple_metric

router = APIRouter()

@router.get("/")
def get_network():
    in_query = 'rate(node_network_receive_bytes_total[1m])'
    out_query = 'rate(node_network_transmit_bytes_total[1m])'
    return {
        "network_in_bytes_per_sec": format_simple_metric(query_prometheus(in_query), "in"),
        "network_out_bytes_per_sec": format_simple_metric(query_prometheus(out_query), "out")
    }
