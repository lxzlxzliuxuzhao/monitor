# app/services/container.py
import os
from kubernetes import client, config
from typing import List
from app.models.schemas import ContainerInfo


class ContainerService:
    def __init__(self):
        if self._in_k8s():
            config.load_incluster_config()
        else:
            config.load_kube_config()

        self.v1 = client.CoreV1Api()

    def _in_k8s(self):
        return os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")

    def get_all_containers(self) -> List[ContainerInfo]:
        containers_info = []
        try:
            pods = self.v1.list_pod_for_all_namespaces(watch=False)
            for pod in pods.items:
                for container in pod.spec.containers:
                    containers_info.append(
                        ContainerInfo(
                            namespace=pod.metadata.namespace,
                            pod_name=pod.metadata.name,
                            container_name=container.name,
                            image=container.image,
                            status=pod.status.phase
                        )
                    )
        except Exception as e:
            print(f"Error fetching containers: {e}")
        return containers_info