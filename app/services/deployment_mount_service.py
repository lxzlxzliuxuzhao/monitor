from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app.core.config import settings
from app.models.schemas import DeploymentMountStats, ContainerMountInfo, VolumeMountInfo, VolumeInfo
from typing import Dict, List

class DeploymentMountService:
    """Deployment 挂载信息统计服务"""
    
    def __init__(self):
        self._init_k8s_client()
        
    def _init_k8s_client(self) -> None:
        """配置Kubernetes客户端连接
        
        根据配置决定使用集群内配置还是本地kubeconfig
        
        异常:
            RuntimeError: 当Kubernetes配置加载失败时抛出
        """
        try:
            config.load_incluster_config()  # 集群内运行
        except config.ConfigException:
            config.load_kube_config()  # 集群外运行

        # 初始化API客户端
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
    
    def get_deployment_mount_stats(
        self, 
        deployment_name: str, 
        namespace: str = "default"
    ) -> DeploymentMountStats:
        """获取 Deployment 的挂载统计信息"""
        try:
            # 获取 Deployment 对象
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            
            # 初始化响应对象
            stats = DeploymentMountStats(
                deployment_name=deployment_name,
                namespace=namespace
            )
            
            # 获取 Pod 模板
            pod_template = deployment.spec.template
            
            # 处理每个容器
            for container in pod_template.spec.containers:
                container_info = ContainerMountInfo(
                    container_name=container.name
                )
                
                # 处理容器挂载
                if container.volume_mounts:
                    for vm in container.volume_mounts:
                        container_info.volume_mounts.append(
                            VolumeMountInfo(
                                name=vm.name,
                                mount_path=vm.mount_path,
                                read_only=vm.read_only if vm.read_only else False,
                                sub_path=vm.sub_path if vm.sub_path else None,
                                mount_propagation=vm.mount_propagation if vm.mount_propagation else None
                            )
                        )
                        stats.total_mounts += 1
                
                stats.containers.append(container_info)
            
            # 处理卷定义
            if pod_template.spec.volumes:
                stats.total_volumes = len(pod_template.spec.volumes)
                volume_type_count = {}
                
                for volume in pod_template.spec.volumes:
                    vol_info = VolumeInfo(name=volume.name)
                    
                    # 识别卷类型
                    if volume.config_map:
                        vol_info.type = "configMap"
                        vol_info.config_map_name = volume.config_map.name
                        volume_type_count["configMap"] = volume_type_count.get("configMap", 0) + 1
                    elif volume.secret:
                        vol_info.type = "secret"
                        vol_info.secret_name = volume.secret.secret_name
                        volume_type_count["secret"] = volume_type_count.get("secret", 0) + 1
                    elif volume.persistent_volume_claim:
                        vol_info.type = "persistentVolumeClaim"
                        vol_info.pvc_name = volume.persistent_volume_claim.claim_name
                        volume_type_count["persistentVolumeClaim"] = volume_type_count.get("persistentVolumeClaim", 0) + 1
                        
                        # 获取 PVC 详细信息
                        try:
                            pvc = self.core_v1.read_namespaced_persistent_volume_claim(
                                name=vol_info.pvc_name,
                                namespace=namespace
                            )
                            if pvc.spec.resources.requests:
                                vol_info.size = pvc.spec.resources.requests.get("storage", "unknown")
                            if pvc.spec.storage_class_name:
                                vol_info.storage_class = pvc.spec.storage_class_name
                        except ApiException:
                            pass  # 忽略获取 PVC 详情的错误
                    elif volume.host_path:
                        vol_info.type = "hostPath"
                        vol_info.host_path = volume.host_path.path
                        volume_type_count["hostPath"] = volume_type_count.get("hostPath", 0) + 1
                    elif volume.empty_dir:
                        vol_info.type = "emptyDir"
                        volume_type_count["emptyDir"] = volume_type_count.get("emptyDir", 0) + 1
                    else:
                        vol_info.type = "unknown"
                        volume_type_count["unknown"] = volume_type_count.get("unknown", 0) + 1
                    
                    # 将卷信息添加到对应容器
                    for container_info in stats.containers:
                        # 检查此卷是否挂载到当前容器
                        if any(vm.name == volume.name for vm in container_info.volume_mounts):
                            container_info.volumes.append(vol_info)
                
                stats.volume_types = volume_type_count
            
            return stats
            
        except ApiException as e:
            if e.status == 404:
                raise ValueError(f"命名空间 '{namespace}' 中找不到 Deployment '{deployment_name}'")
            raise ValueError(f"Kubernetes API 错误: {e.reason}")