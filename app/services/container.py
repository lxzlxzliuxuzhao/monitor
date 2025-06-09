import os
from datetime import datetime
from kubernetes import client, config
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


class ContainerService:
    def __init__(self):
        try:
            if self._in_k8s():
                print("Loading in-cluster Kubernetes config...")
                config.load_kube_config()
            else:
                print("Loading local Kubernetes config...")
                config.load_kube_config()
            
            self.v1 = client.CoreV1Api()
            print("Kubernetes API client initialized successfully")
        except Exception as e:
            print(f"Error initializing Kubernetes client: {e}")
            traceback.print_exc()
            # 即使初始化失败也允许继续运行
            self.v1 = None

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

    def get_all_containers(self) -> List[ContainerInfo]:
        if not self.v1:
            print("Kubernetes API client not initialized. Returning empty list.")
            return []
        
        all_info = []
        try:
            print("Fetching pods from Kubernetes API...")
            # 使用分页获取所有pods
            continue_token = None
            while True:
                pods_chunk = self.v1.list_pod_for_all_namespaces(
                    limit=500, 
                    _continue=continue_token,
                    watch=False
                )
                for pod in pods_chunk.items:
                    # 安全获取可能为空的字段
                    metadata = pod.metadata or client.V1ObjectMeta()
                    spec = pod.spec or client.V1PodSpec()
                    status = pod.status or client.V1PodStatus()
                    
                    # 基础信息
                    namespace = metadata.namespace or "default"
                    pod_name = metadata.name or "<none>"
                    
                    # Pod级别信息
                    pod_ip = status.pod_ip or "<none>"
                    node_name = spec.node_name or "<none>"
                    nominated_node = status.nominated_node_name or "<none>"
                    age = self._calculate_age(metadata.creation_timestamp)
                    
                    # 创建容器状态映射
                    container_status_map = {}
                    for container_status in (status.container_statuses or []):
                        name = container_status.name
                        if not name:
                            continue
                            
                        container_status_map[name] = {
                            "ready": "True" if container_status.ready else "False",
                            "restarts": str(container_status.restart_count),
                            "status": self._get_container_status(container_status)
                        }
                    
                    # 处理readiness gates
                    readiness_gates = []
                    for gate in (spec.readiness_gates or []):
                        gate_type = gate.condition_type
                        if not gate_type:
                            continue
                            
                        for condition in (status.conditions or []):
                            if condition.type == gate_type:
                                readiness_gates.append(
                                    f"{gate_type}={condition.status}"
                                )
                                break
                    readiness_gates_str = ",".join(readiness_gates) if readiness_gates else "<none>"
                    
                    containers_list = []
                    ready_count = 0
                    restart_count = 0
                    # 处理每个容器
                    for container in (spec.containers or []):
                        container_name = container.name or "<none>"
                        
                        # 获取容器状态信息
                        status_info = container_status_map.get(container_name, {
                            "ready": "False",
                            "restarts": "0",
                            "status": "Unknown"
                        })

                        if status_info["ready"] == "True":
                            ready_count += 1
                        restart_count += int(status_info["restarts"])

                        containers_list.append(
                            ContainerInfo(
                                name=container_name,
                                image=container.image or "<none>",
                                ready=status_info["ready"],
                                status=status_info["status"],
                                restarts=status_info["restarts"],
                            )
                        )
                        
                    all_info.append(
                        PodInfo(
                            name=f"{pod_name}",
                            namespace=namespace,
                            pod_name=pod_name,
                            ready=f"{ready_count}/{len(spec.containers)}",
                            restarts=str(restart_count),
                            age=age,
                            IP=pod_ip,
                            node=node_name,
                            nominated_node=nominated_node,
                            readiness_gates=readiness_gates_str,
                            containers_list=containers_list
                        )
                    )
                
                continue_token = pods_chunk.metadata._continue
                if not continue_token:
                    break

            print(f"Successfully fetched {len(all_info)} pods")
            return all_info

        except Exception as e:
            print(f"Error fetching pods: {e}")
            traceback.print_exc()
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
