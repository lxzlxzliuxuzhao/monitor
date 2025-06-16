# 核心FastAPI导入
from fastapi import HTTPException
from fastapi.responses import JSONResponse

# Kubernetes客户端导入
import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# 其他依赖
from pydantic import BaseModel
from typing import Optional, List, Union
import logging
from datetime import datetime
import json
import time


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
logger = logging.getLogger("volume-manager")

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
            #run_as_non_root=True,  # 新增安全限制
            #read_only_root_filesystem=True  # 新增安全限制
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
    host_path: str  # 现在实际使用 host_path
) -> bool:
    """
    重构版本：使用 host_path 创建本地 PV，并添加到 Deployment
    
    关键变化：
    1. 使用 host_path 参数创建本地 PV
    2. 保持 PVC 命名规范为 {namespace}-{volume_name}-pvc
    3. 添加节点亲和性确保挂载到正确节点
    """
    try:
        # 1. 获取部署所在节点
        node_name = get_deployment_node(namespace, deployment_name)
        logger.info(f"🎯 部署 '{deployment_name}' 运行在节点 '{node_name}'")
        
        # 2. 在目标节点创建目录
        create_host_directory(node_name, host_path)
        logger.info(f"📂 在节点 '{node_name}' 创建目录 '{host_path}'")
        
        # 3. 创建 PersistentVolume
        create_local_pv(
            namespace=namespace,
            volume_name=volume_name,
            host_path=host_path,
            node_name=node_name
        )
        
        # 4. 创建 PersistentVolumeClaim
        create_pvc(
            namespace=namespace,
            volume_name=volume_name
        )
        
        # 5. 更新 Deployment 添加卷挂载
        update_deployment_with_volume(
            namespace=namespace,
            deployment_name=deployment_name,
            volume_name=volume_name,
            mount_path=mount_path
        )
        
        logger.info(f"✅ 成功为 {deployment_name} 添加本地存储卷 {mount_path}")
        return True
        
    except ApiException as e:
        error_info = json.loads(e.body) if e.body else str(e)
        logger.error(f"❌ Kubernetes API 错误: {e.status}\n{error_info}")
        return False
    except Exception as e:
        logger.exception(f"❌ 添加存储失败: {str(e)}")
        return False

def get_deployment_node(namespace: str, deployment_name: str) -> str:
    """获取部署运行的节点名称"""
    # 获取部署
    deployment = apps_v1.read_namespaced_deployment(
        name=deployment_name,
        namespace=namespace
    )
    
    # 获取部署的标签选择器
    if not deployment.spec.selector.match_labels:
        raise ValueError("Deployment 缺少标签选择器")
    
    label_selector = ",".join(
        [f"{k}={v}" for k, v in deployment.spec.selector.match_labels.items()]
    )
    
    # 获取关联的 Pod
    pods = core_v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=label_selector
    )
    
    if not pods.items:
        raise RuntimeError(f"未找到关联的 Pod")
    
    return pods.items[0].spec.node_name

def create_host_directory(node_name: str, host_path: str):
    """在目标节点上创建物理目录"""
    try:
        # 使用 Python SSH 库更可靠
        from paramiko import SSHClient, AutoAddPolicy
        
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy())
        
        # 假设使用 root 用户，实际中应使用服务账户
        client.connect(node_name, username="root")
        
        # 创建目录并设置权限
        commands = [
            f"mkdir -p {host_path}",
            f"chmod 777 {host_path}"
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = client.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error = stderr.read().decode().strip()
                raise RuntimeError(f"Failed to create host path: {error}")
                
        client.close()
    
    except ImportError:
        # 回退到系统 SSH（需要预先配置免密登录）
        import subprocess
        cmd = f"ssh {node_name} 'mkdir -p {host_path} && chmod 777 {host_path}'"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"SSH命令失败: {result.stderr.decode()}")

def create_local_pv(namespace: str, volume_name: str, host_path: str, node_name: str):
    """创建本地 PersistentVolume"""
    pv_name = f"{namespace}-{volume_name}-pv"
    
    # 检查 PV 是否已存在
    try:
        existing_pv = core_v1.read_persistent_volume(pv_name)
        logger.warning(f"⚠️ PV '{pv_name}' 已存在，跳过创建")
        return
    except ApiException as e:
        if e.status != 404:  # 不是"Not Found"错误
            raise
    
    pv = client.V1PersistentVolume(
        metadata=client.V1ObjectMeta(
            name=pv_name,
            labels={
                "type": "local",
                "app": volume_name,
                "namespace": namespace
            }
        ),
        spec=client.V1PersistentVolumeSpec(
            capacity={"storage": "10Gi"},  # 默认10GiB
            access_modes=["ReadWriteOnce"],
            persistent_volume_reclaim_policy="Retain",
            storage_class_name="",
            local=client.V1LocalVolumeSource(path=host_path),
            node_affinity=client.V1VolumeNodeAffinity(
                required=client.V1NodeSelector(
                    node_selector_terms=[
                        client.V1NodeSelectorTerm(
                            match_expressions=[
                                client.V1NodeSelectorRequirement(
                                    key="kubernetes.io/hostname",
                                    operator="In",
                                    values=[node_name]
                                )
                            ]
                        )
                    ]
                )
            )
        )
    )
    
    core_v1.create_persistent_volume(pv)
    logger.info(f"🔄 创建 PV '{pv_name}' 指向 {host_path}")

def create_pvc(namespace: str, volume_name: str):
    """创建 PersistentVolumeClaim"""
    pvc_name = f"{namespace}-{volume_name}-pvc"
    pv_name = f"{namespace}-{volume_name}-pv"
    
    # 检查 PVC 是否已存在
    try:
        existing_pvc = core_v1.read_namespaced_persistent_volume_claim(
            name=pvc_name,
            namespace=namespace
        )
        logger.warning(f"⚠️ PVC '{pvc_name}' 已存在，跳过创建")
        return
    except ApiException as e:
        if e.status != 404:  # 不是"Not Found"错误
            raise
    
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=pvc_name),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1ResourceRequirements(
                requests={"storage": "10Gi"}  # 必须与 PV 容量匹配
            ),
            storage_class_name="",
            selector=client.V1LabelSelector(
                match_labels={
                    "type": "local",
                    "app": volume_name,
                    "namespace": namespace
                }
            )
        )
    )
    
    core_v1.create_namespaced_persistent_volume_claim(
        namespace=namespace,
        body=pvc
    )
    
    # 等待 PVC 绑定
    logger.info(f"⏳ 等待 PVC '{pvc_name}' 绑定到 PV '{pv_name}'...")
    wait_for_pvc_bound(namespace, pvc_name)
    logger.info(f"✅ PVC '{pvc_name}' 已绑定")

def wait_for_pvc_bound(namespace: str, pvc_name: str, timeout=30):
    """等待 PVC 状态变为 Bound"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        pvc = core_v1.read_namespaced_persistent_volume_claim(
            name=pvc_name,
            namespace=namespace
        )
        
        if pvc.status.phase == "Bound":
            return
            
        time.sleep(1)
    
    raise TimeoutError(f"PVC 没有在 {timeout} 秒内绑定")

def update_deployment_with_volume(
    namespace: str,
    deployment_name: str,
    volume_name: str,
    mount_path: str
):
    """更新 Deployment 添加卷挂载"""
    pvc_name = f"{namespace}-{volume_name}-pvc"
    
    # 获取当前部署
    deployment = apps_v1.read_namespaced_deployment(
        name=deployment_name,
        namespace=namespace
    )
    
    # 添加卷定义
    volume = client.V1Volume(
        name=volume_name,
        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
            claim_name=pvc_name
        )
    )
    
    if not deployment.spec.template.spec.volumes:
        deployment.spec.template.spec.volumes = []
    
    # 检查卷是否已存在
    volume_exists = any(v.name == volume_name for v in deployment.spec.template.spec.volumes)
    if not volume_exists:
        deployment.spec.template.spec.volumes.append(volume)
        logger.info(f"➕ 添加卷 '{volume_name}' 到 Deployment")
    
    # 添加卷挂载
    volume_mount = client.V1VolumeMount(
        name=volume_name,
        mount_path=mount_path
    )
    
    containers_updated = False
    
    for container in deployment.spec.template.spec.containers:
        if not container.volume_mounts:
            container.volume_mounts = []
        
        # 检查挂载点是否已存在
        mount_exists = any(mount.mount_path == mount_path for mount in container.volume_mounts)
        if not mount_exists:
            container.volume_mounts.append(volume_mount)
            containers_updated = True
            logger.info(f"📌 容器 '{container.name}' 添加挂载点 {mount_path}")
    
    # 如果没有需要更新的内容，直接返回
    if not (volume_exists or containers_updated):
        logger.info("⏭️ 无需更新 Deployment，卷和挂载点已存在")
        return
    
    # 更新部署
    apps_v1.patch_namespaced_deployment(
        name=deployment_name,
        namespace=namespace,
        body=deployment
    )
    
    # 添加重启注解
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat() + "Z"
                    }
                }
            }
        }
    }
    
    apps_v1.patch_namespaced_deployment(
        name=deployment_name,
        namespace=namespace,
        body=patch
    )
    
    logger.info("🔄 触发滚动更新")