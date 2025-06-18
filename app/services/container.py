import os
from datetime import datetime
from kubernetes import client, config
from kubernetes.client import CustomObjectsApi
from typing import List
import traceback

class ContainerInfo:
    """
    容器信息类,用于存储和表示Kubernetes容器的相关信息。
    """
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.image = kwargs.get('image', '')
        self.ready = kwargs.get('ready', 'False')
        self.status = kwargs.get('status', 'Unknown')
        self.restarts = kwargs.get('restarts', '0')

class PodInfo:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.namespace = kwargs.get('namespace', '')
        self.pod_name = kwargs.get('pod_name', '')
        self.ready = kwargs.get('ready', '0/0')
        self.restarts = kwargs.get('restarts', '0')
        self.age = kwargs.get('age', '<none>')
        self.IP = kwargs.get('IP', '<none>')
        self.node = kwargs.get('node', '<none>')
        self.nominated_node = kwargs.get('nominated_node', '<none>')
        self.readiness_gates = kwargs.get('readiness_gates', '<none>')
        self.containers_list = kwargs.get('containers_list', [])

    def __repr__(self):
        return f"<Container {self.name} in {self.namespace}>"

class DeploymentInfo:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.namespace = kwargs.get('namespace', '')
        self.ready = kwargs.get('ready', '0/0')
        self.up_to_date = kwargs.get('up_to_date', '0')
        self.available = kwargs.get('available', '0')
        self.age = kwargs.get('age', '<none>')
        self.mounts = kwargs.get('mounts', []) 
        self.container_mounts = kwargs.get('container_mounts', []) 
        
    def __repr__(self):
        return f"<Deployment {self.name} in {self.namespace}>"

class ContainerService:
    def __init__(self):
        self.v1 = None
        self.custom_api = None
        try:
            if self._in_k8s():
                print("Loading in-cluster Kubernetes config...")
                config.load_kube_config()
            else:
                print("Loading local Kubernetes config...")
                config.load_kube_config()
            
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()
            print("Kubernetes API client initialized successfully")
        except Exception as e:
            print(f"Error initializing Kubernetes client: {e}")
            traceback.print_exc()

    def _in_k8s(self):
        return os.path.exists("/root/.kube/config")

    @staticmethod
    def _calculate_age(creation_timestamp):
        """计算从创建时间到当前的时间差"""
        if not creation_timestamp:
            return "<none>"
        
        try:
            # 确保时区统一为UTC
            if creation_timestamp.tzinfo:
                now = datetime.utcnow().replace(tzinfo=creation_timestamp.tzinfo)
            else:
                now = datetime.utcnow()
                creation_timestamp = creation_timestamp.replace(tzinfo=None)
            
            delta = now - creation_timestamp
            days = delta.days
            seconds = delta.seconds
            
            if days > 0:
                return f"{days}d"
            elif seconds >= 3600:
                hours = seconds // 3600
                return f"{hours}h"
            elif seconds >= 60:
                minutes = seconds // 60
                return f"{minutes}m"
            else:
                return "0m"
        except Exception:
            return "<none>"

    def _get_container_status(self, container_status):
        """获取容器状态字符串"""
        if not container_status:
            return "Unknown"
        
        state = container_status.state
        if not state:
            return "Unknown"
        
        if state.running:
            return "Running"
        elif state.waiting:
            return state.waiting.reason or "Waiting"
        elif state.terminated:
            return state.terminated.reason or "Terminated"
        else:
            return "Unknown"

    def get_all_deployments(self) -> List[DeploymentInfo]:
        try:
            apps_v1 = client.AppsV1Api()
            deps = apps_v1.list_deployment_for_all_namespaces(watch=False)
            
            result = []
            for dep in deps.items:
                # 解析 Volume 定义
                volumes = []
                for volume in dep.spec.template.spec.volumes or []:  # 显式处理None
                    volume_info = {
                        "name": volume.name,
                        "type": None,
                        "details": {}
                    }
                    
                    if volume.config_map:
                        volume_info["type"] = "configmap"
                        volume_info["details"]["name"] = volume.config_map.name
                    elif volume.secret:
                        volume_info["type"] = "secret"
                        volume_info["details"]["secret_name"] = volume.secret.secret_name
                    elif volume.persistent_volume_claim:  # 新增PVC处理
                        volume_info["type"] = "pvc"
                        volume_info["details"]["claim_name"] = volume.persistent_volume_claim.claim_name
                    elif volume.empty_dir:
                        volume_info["type"] = "empty_dir"
                    elif volume.host_path:
                        volume_info["type"] = "host_path"
                        volume_info["details"]["path"] = volume.host_path.path
                    
                    volumes.append(volume_info)

                # 解析容器挂载点
                container_mounts = []
                for container in dep.spec.template.spec.containers or []:
                    for mount in container.volume_mounts or []:
                        container_mounts.append({
                            "container": container.name,
                            "name": mount.name,
                            "mount_path": mount.mount_path,
                            "read_only": getattr(mount, "read_only", False),
                            "sub_path": getattr(mount, "sub_path", "")
                        })

                result.append(
                    DeploymentInfo(
                        name=dep.metadata.name,
                        namespace=dep.metadata.namespace,
                        ready=f"{dep.status.ready_replicas or 0}/{dep.spec.replicas}",
                        up_to_date=str(dep.status.updated_replicas or 0),
                        available=str(dep.status.available_replicas or 0),
                        age=self._calculate_age(dep.metadata.creation_timestamp),
                        volumes=volumes,
                        volume_mounts=container_mounts
                    )
                )
            
            return result
        except Exception as e:
            print(f"Error: {str(e)}")
            return []

    def count_containers(self) -> int:
        """
        计算所有命名空间中非 KubeVirt Pod 的容器总数。
        
        Returns:
            int: 非 KubeVirt 容器的总数
        """
        if not self.v1:
            print("Kubernetes API client not initialized. Returning 0.")
            return 0
            
        total_containers = 0
        try:
            print("Counting non-KubeVirt containers across all pods...")
            continue_token = None
            while True:
                pods_chunk = self.v1.list_pod_for_all_namespaces(
                    limit=500,
                    _continue=continue_token,
                    watch=False
                )
                for pod in pods_chunk.items:
                    metadata = pod.metadata or client.V1ObjectMeta()
                    if 'kubevirt.io' in (metadata.labels or {}):
                        continue
                    spec = pod.spec or client.V1PodSpec()
                    containers = spec.containers or []
                    total_containers += len(containers)
                
                continue_token = pods_chunk.metadata._continue
                if not continue_token:
                    break

            print(f"Total non-KubeVirt containers found: {total_containers}")
            return total_containers

        except Exception as e:
            print(f"Error counting containers: {e}")
            traceback.print_exc()
            return 0

    def count_kubevirt_vms(self) -> int:
        """
        计算所有命名空间中 KubeVirt 虚拟机的总数。
        
        Returns:
            int: 虚拟机总数
        """
        if not hasattr(self, 'custom_api') or self.custom_api is None:
            print("Kubernetes Custom API client not initialized or KubeVirt not available. Returning 0.")
            return 0
            
        try:
            print("Counting KubeVirt VirtualMachineInstances...")
            total_vms = 0
            continue_token = None
            while True:
                vmi_list = self.custom_api.list_cluster_custom_object(
                    group="kubevirt.io",
                    version="v1",
                    plural="virtualmachineinstances",
                    limit=500,
                    _continue=continue_token
                )
                total_vms += len(vmi_list.get("items", []))
                continue_token = vmi_list.get("metadata", {}).get("_continue")
                if not continue_token:
                    break

            print(f"Total KubeVirt VirtualMachineInstances found: {total_vms}")
            return total_vms

        except Exception as e:
            print(f"Error counting KubeVirt VMs: {e}")
            traceback.print_exc()
            return 0
