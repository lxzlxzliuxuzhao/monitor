def format_cpu_response(raw_data):
    return [{
        "node": i["metric"].get("node"),
        "pod": i["metric"].get("pod"),
        "container": i["metric"].get("container"),
        "namespace": i["metric"].get("namespace"),
        "cpu_usage_cores_per_sec": float(i["value"][1]),
        "timestamp": float(i["value"][0])
    } for i in raw_data]

def format_simple_metric(raw_data, metric_name):
    return [{
        "node": i["metric"].get("instance", "unknown"),
        metric_name: float(i["value"][1]),
        "timestamp": float(i["value"][0])
    } for i in raw_data]
