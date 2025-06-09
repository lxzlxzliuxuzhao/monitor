from app.core.prometheus import query_prometheus
from app.core.config import layer_config

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
            "cpu_usage": query_number('avg(1 - rate(node_cpu_seconds_total{mode="idle"}[1m]))'),
            "ram_usage": query_number("sum(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)"),
            "gpu_usage": query_number("avg(DCGM_FI_DEV_GPU_UTIL)"),
        },
        "clusters": query_node_compute_usage()
    }

def get_storage_usage():
    total_query = 'sum by(instance) (node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})'
    used_query = 'sum by(instance) (node_filesystem_size_bytes{fstype!~"tmpfs|overlay"} - node_filesystem_free_bytes{fstype!~"tmpfs|overlay"})'

    total_results = query_prometheus(total_query)
    used_results = query_prometheus(used_query)

    # Prometheus instance 到 node name 的映射
    mapping_results = query_prometheus('kube_node_info')
    instance_to_node = {
        result['metric']['instance']: result['metric'].get('node', 'unknown')
        for result in mapping_results
    }

    print("Instance to Node Mapping:")
    print(instance_to_node)

    storage_map = {}

    for r in total_results:
        instance = r['metric'].get('instance')
        node = instance_to_node.get(instance, instance)

        ip = instance.split(":")[0]
        layer = layer_config.layer_map.get(ip, "unknown")

        storage_map[node] = {
            "name": node,
            "total_size": float(r['value'][1]),
            "used_size": 0.0,
            "layer": layer,
        }

    for r in used_results:
        instance = r['metric'].get('instance')
        node = instance_to_node.get(instance, instance)

        ip = instance.split(":")[0]
        layer = layer_config.layer_map.get(ip, "unknown")

        if node in storage_map:
            storage_map[node]["used_size"] = float(r['value'][1])
        else:
            storage_map[node] = {
                "name": node,
                "total_size": 0.0,
                "used_size": float(r['value'][1]),
                "layer": layer,
            }

    return {
        "storage_info": list(storage_map.values())
    }

def query_number(promql: str) -> float:
    try:
        result = query_prometheus(promql)
        return float(result[0]['value'][1]) if result else 0.0
    except:
        return 0.0

def query_node_compute_usage():
    # Step 1: 获取 instance -> node name 映射关系
    mapping_query = 'kube_node_info'
    mapping_results = query_prometheus(mapping_query)
    instance_to_node = {
        result['metric']['instance']: result['metric'].get('node', 'unknown')
        for result in mapping_results
    }

    # Step 2: 查询每个 instance 的 CPU 使用率
    cpu_query = '''
        1 - avg by (instance) (
            rate(node_cpu_seconds_total{mode="idle"}[1m])
        )
    '''
    cpu_results = query_prometheus(cpu_query)

    # Step 3: 查询每个 instance 的内存使用率
    mem_query = '''
        1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
    '''
    mem_results = query_prometheus(f'avg by (instance) ({mem_query})')

    # Step 4: 查询每个 instance 的 GPU 使用率（可选，依赖 DCGM exporter）
    gpu_query = '''
        avg by (instance) (DCGM_FI_DEV_GPU_UTIL)
    '''
    gpu_results = query_prometheus(gpu_query)

    # Step 5: 整理结果
    node_stats = {}

    # CPU usage
    for result in cpu_results:
        instance = result['metric'].get('instance', 'unknown')
        node = instance_to_node.get(instance, instance)
        node_stats[node] = {
            'cpu_usage': float(result['value'][1])
        }

    # RAM usage
    for result in mem_results:
        instance = result['metric'].get('instance', 'unknown')
        node = instance_to_node.get(instance, instance)
        node_stats.setdefault(node, {})['ram_usage'] = float(result['value'][1])

    # GPU usage
    for result in gpu_results:
        instance = result['metric'].get('instance', 'unknown')
        node = instance_to_node.get(instance, instance)
        node_stats.setdefault(node, {})['gpu_usage'] = float(result['value'][1])

    # 格式化为列表输出
    return [
        {
            "name": node,
            "cpu_usage": stats.get("cpu_usage", 0.0),
            "ram_usage": stats.get("ram_usage", 0.0),
            "gpu_usage": stats.get("gpu_usage", 0.0),
        }
        for node, stats in node_stats.items()
    ]