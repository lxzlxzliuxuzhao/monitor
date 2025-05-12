from app.core.prometheus import query_prometheus

# 可根据需要调整标签过滤策略，如 by(cluster) 或 node

def get_server_overview():
    return {
        "cloud_size": 5,
        "edge_size": 12,
        "device_size": 27,
        "cpu_size": query_number("sum(machine_cpu_cores)"),
        "gpu_size": query_number("count(nvidia_gpu_duty_cycle)"),
        "ram_size": query_number("sum(node_memory_MemTotal_bytes)"),
        "disk_size": query_number("sum(node_filesystem_size_bytes)"),
    }

def get_network_status():
    # ⚠️ 示例静态数据，后期需用 ping-exporter / blackbox-exporter 替换
    return {
        "size": 3,
        "device_network": [
            {"device_name": "node-a", "network_type": "5G", "latency": 12.3},
            {"device_name": "node-b", "network_type": "Ethernet", "latency": 3.8},
            {"device_name": "node-c", "network_type": "WiFi", "latency": 22.1},
        ]
    }

def get_compute_usage():
    return {
        "total": {
            "cpu_usage": query_number("sum(rate(container_cpu_usage_seconds_total[1m]))"),
            "ram_usage": query_number("sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)"),
            "gpu_usage": query_number("avg(DCGM_FI_DEV_GPU_UTIL)"),
        },
        "clusters": []  # TODO: 后续支持按标签分集群统计
    }

def get_storage_usage():
    return {
        "storage_info": [
            {
                "name": "local-disk",
                "total_size": query_number("sum(node_filesystem_size_bytes)"),
                "used_size": query_number("sum(node_filesystem_size_bytes - node_filesystem_free_bytes)"),
            }
        ]
    }

def query_number(promql: str) -> float:
    try:
        result = query_prometheus(promql)
        return float(result[0]['value'][1]) if result else 0.0
    except:
        return 0.0
