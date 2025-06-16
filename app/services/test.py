from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel
from typing import Optional, List, Dict, Union
import logging

logger = logging.getLogger(__name__)

# 初始化 Kubernetes 客户端
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

# 创建 API 客户端实例
core_v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
storage_v1 = client.StorageV1Api()

# ------------
# 数据模型 (保持原型)
# ------------
class ResourceConfig(BaseModel):
    cpu: Optional[str] = None
    memory: Optional[str] = None

class InitContainer(BaseModel):
    name: Optional[str] = None
    image: Optional[str] = None
    command: Optional[Union[List[str], str]] = None

class EnvVar(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None

class ContainerRequest(BaseModel):
    name: str
    image: str
    resources: Optional[ResourceConfig] = None
    init_containers: Optional[List[InitContainer]] = None
    privileged: Optional[bool] = False
    env: Optional[List[EnvVar]] = None
    host_network: Optional[bool] = False
    
    @validator('privileged', 'host_network', pre=True)
    def handle_bool_fields(cls, v):
        """处理布尔字段的空字符串输入"""
        if v == "" or v is None:
            return False
        return v
    
    @validator('init_containers', 'env', pre=True)
    def handle_empty_lists(cls, v):
        """处理空列表输入"""
        if v == "":
            return None
        return v

# ------------
# 重构后的函数实现 (保持函数名)
# ------------

def create_k8s_pod(request: ContainerRequest):
    """
    重构说明：
    1. 不再创建裸 Pod，改为创建 Deployment
    2. 添加安全上下文限制
    3. 保留所有原始输入字段
    """
    try:
        # 基础验证保持不变
        if not request.name or not request.image:
            raise HTTPException(status_code=400, detail="名称和镜像不能为空")
        
        # 安全上下文 - 添加生产环境限制
        security_context = client.V1SecurityContext(
            privileged=request.privileged,
            allow_privilege_escalation=False,  # 新增安全限制
            run_as_non_root=True,  # 新增安全限制
            read_only_root_filesystem=True  # 新增安全限制
        )

        # 环境变量处理保持不变
        env_list = None
        if request.env:
            env_list = [
                client.V1EnvVar(name=e.name, value=e.value) 
                for e in request.env 
                if e.name and e.value
            ]

        # 资源处理保持不变
        resources = None
        if request.resources and (request.resources.cpu or request.resources.memory):
            limits = {}
            if request.resources.cpu: limits["cpu"] = request.resources.cpu
            if request.resources.memory: limits["memory"] = request.resources.memory
            resources = client.V1ResourceRequirements(limits=limits)

        # 主容器配置保持不变，但增加安全上下文
        container = client.V1Container(
            name=request.name,
            image=request.image,
            env=env_list,
            security_context=security_context,  # 使用新的安全上下文
            resources=resources
        )

        # 初始化容器处理保持不变
        init_containers = None
        if request.init_containers:
            init_containers = []
            for ic in request.init_containers:
                if ic.name and ic.image:
                    command = ic.command or []
                    if isinstance(command, str):
                        command = [command]
                    
                    init_containers.append(client.V1Container(
                        name=ic.name,
                        image=ic.image,
                        command=command
                    ))

        # 创建 Deployment 而不是裸 Pod！
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(name=request.name),
            spec=client.V1DeploymentSpec(
                replicas=1,  # 默认1个副本
                selector=client.V1LabelSelector(
                    match_labels={"app": request.name}  # 添加标签选择器
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={"app": request.name}  # 添加Pod标签
                    ),
                    spec=client.V1PodSpec(
                        containers=[container],
                        init_containers=init_containers,
                        host_network=request.host_network
                    )
                )
            )
        )

        # 创建 Deployment
        apps_v1.create_namespaced_deployment(
            namespace="default", 
            body=deployment
        )
        
        return JSONResponse(
            status_code=200,
            content={"message": f"应用 {request.name} 已通过Deployment部署"}
        )
        
    except ApiException as e:
        detail = f"API错误: {e.status}\n{e.body}" if e.body else f"API错误: {e.status}"
        raise HTTPException(status_code=e.status, detail=detail)
    except Exception as e:
        logger.exception("应用部署失败")
        raise HTTPException(status_code=500, detail=str(e))

def delete_k8s_pod(pod_name: str):
    """
    重构说明：
    1. 不再删除裸 Pod，改为删除 Deployment
    2. 添加级联删除选项
    3. 保持原始函数签名不变
    """
    try:
        # 删除整个 Deployment (而不仅是单个Pod)
        # 添加级联删除选项确保相关资源被清理
        delete_options = client.V1DeleteOptions(
            propagation_policy="Foreground"  # 确保关联资源被删除
        )
        
        apps_v1.delete_namespaced_deployment(
            name=pod_name,  # 这里实际是 Deployment 名称
            namespace="default",
            body=delete_options
        )
        
        return JSONResponse(
            status_code=200,
            content={"message": f"应用 {pod_name} 正在删除中，相关资源将被清理"}
        )
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"应用 {pod_name} 不存在")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

def add_volume_to_deployment(
    namespace: str, 
    deployment_name: str, 
    volume_name: str, 
    mount_path: str, 
    host_path: str
) -> bool:
    """
    重构说明：
    1. 不再使用 hostPath，改为使用 PVC
    2. 添加 PVC 自动创建
    3. 保持原始函数签名不变
    """
    try:
        # 1. 创建 PVC 而不是使用 hostPath
        pvc = client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(
                name=volume_name,
                labels={"app": deployment_name}
            ),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": "1Gi"}  # 默认分配1GB
                )
            )
        )
        
        core_v1.create_namespaced_persistent_volume_claim(
            namespace=namespace,
            body=pvc
        )
        logger.info(f"创建PVC {volume_name} 用于部署 {deployment_name}")

        # 2. 获取 Deployment
        deployment = apps_v1.read_namespaced_deployment(
            name=deployment_name, 
            namespace=namespace
        )

        # 3. 创建 PVC 卷
        pvc_volume = client.V1Volume(
            name=volume_name,
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=volume_name
            )
        )

        # 添加卷到 Deployment
        if deployment.spec.template.spec.volumes is None:
            deployment.spec.template.spec.volumes = []
        deployment.spec.template.spec.volumes.append(pvc_volume)

        # 4. 为所有容器添加挂载点
        volume_mount = client.V1VolumeMount(
            name=volume_name,
            mount_path=mount_path
        )``
        
        for container in deployment.spec.template.spec.containers:
            if container.volume_mounts is None:
                container.volume_mounts = []
            container.volume_mounts.append(volume_mount)

        # 5. 更新 Deployment
        apps_v1.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=deployment
        )
        
        logger.info(f"成功为 {deployment_name} 添加PVC存储 {mount_path}")
        return True

    except ApiException as e:
        logger.error(f"Kubernetes API错误: {e.status}\n{e.body}")
        return False
    except Exception as e:
        logger.exception("添加存储失败")
        return False