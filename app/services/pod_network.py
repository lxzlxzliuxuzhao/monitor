from kubernetes import client, config
from fastapi import HTTPException
from app.models.schemas import Pod_Network_Info
import dns.resolver
import time
from typing import List, Optional
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PodService:
    def __init__(self):
        try:
            config.load_incluster_config()  # 集群内运行
        except config.ConfigException:
            config.load_kube_config()  # 集群外运行
        self.core_api = client.CoreV1Api()
        self.networking_api = client.NetworkingV1Api()

    def get_pod_info(self, pod_name: str, namespace: str = "default") -> Pod_Network_Info:
        try:
            pod = self.core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
            status = pod.status.phase
            ip = pod.status.pod_ip
            dns_latency = self.measure_dns_latency("google.com")
            strategy = self.get_network_policy(pod_name, namespace)

            return Pod_Network_Info(
                pod_name=pod_name,
                namespace=namespace,
                status=status,
                ip=ip,
                DNS_latency=dns_latency,
                strategy=strategy
            )
        except client.ApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))

    def listPodsInfo(self, namespace: str = "default") -> list[Pod_Network_Info]:
        try:
            pods = self.core_api.list_namespaced_pod(namespace=namespace)
            pod_info_list = []
            for pod in pods.items:
                status = pod.status.phase
                ip = pod.status.pod_ip
                dns_latency = self.measure_dns_latency("google.com")
                strategy = self.get_network_policy(pod.metadata.name, namespace)

                pod_info = Pod_Network_Info(
                    pod_name=pod.metadata.name,
                    namespace=namespace,
                    status=status,
                    ip=ip,
                    DNS_latency=dns_latency,
                    strategy=strategy
                )
                pod_info_list.append(pod_info)
            return pod_info_list
        except client.ApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))

    def listAllPodsInfo(self) -> List[Pod_Network_Info]:
        try:
            pods = self.core_api.list_pod_for_all_namespaces()
            pod_info_list = []
            for pod in pods.items:
                namespace = pod.metadata.namespace
                status = pod.status.phase
                ip = pod.status.pod_ip
                dns_latency = self.measure_dns_latency("google.com")
                strategy = self.get_network_policy(pod.metadata.name, namespace)

                pod_info = Pod_Network_Info(
                    pod_name=pod.metadata.name,
                    namespace=namespace,
                    status=status,
                    ip=ip,
                    DNS_latency=dns_latency,
                    strategy=strategy
                )
                pod_info_list.append(pod_info)
            return pod_info_list
        except client.ApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))

    def measure_dns_latency(self, domain: str) -> Optional[float]:
        try:
            start_time = time.time()
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ["8.8.8.8"]  # 使用 Google DNS，可调整
            resolver.resolve(domain, "A")
            return time.time() - start_time
        except Exception as e:
            logger.error(f"DNS latency measurement failed: {str(e)}")
            return None

    def get_network_policy(self, pod_name: str, namespace: str) -> Optional[str]:
        try:
            pod = self.core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
            pod_labels = pod.metadata.labels or {}
            logger.debug(f"Pod {pod_name} in namespace {namespace} has labels: {pod_labels}")

            policies = self.networking_api.list_namespaced_network_policy(namespace=namespace)
            for policy in policies.items:
                selector = policy.spec.pod_selector.match_labels or {}
                if not selector:
                    logger.debug(f"Pod {pod_name} matches NetworkPolicy {policy.metadata.name} (empty selector)")
                    return policy.metadata.name
                matches = all(k in pod_labels and pod_labels[k] == v for k, v in selector.items())
                if matches:
                    logger.debug(f"Pod {pod_name} matches NetworkPolicy {policy.metadata.name}")
                    return policy.metadata.name
            logger.debug(f"No matching NetworkPolicy found for pod {pod_name}")
            return "None"
        except client.ApiException as e:
            logger.error(f"Error querying NetworkPolicy for pod {pod_name}: {str(e)}")
            return "None"