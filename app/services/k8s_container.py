from fastapi import HTTPException
from kubernetes import client, config
from pydantic import BaseModel
from typing import Optional, List

config.load_kube_config(config_file="/etc/kubernetes/admin.conf")
# 定义数据模型
class ResourceConfig(BaseModel):
    cpu: Optional[str] = None
    memory: Optional[str] = None

class InitContainer(BaseModel):
    name: str
    image: str
    command: Optional[List[str]] = None

class EnvVar(BaseModel):
    name: str
    value: str

class ContainerRequest(BaseModel):
    name: str
    image: str
    resources: Optional[ResourceConfig] = None
    init_containers: Optional[List[InitContainer]] = None
    privileged: Optional[bool] = False
    env: Optional[List[EnvVar]] = None
    host_network: Optional[bool] = False

# 加载 Kubernetes 配置
config.load_kube_config(config_file="/etc/kubernetes/admin.conf")
v1 = client.CoreV1Api()

def create_k8s_pod(request: ContainerRequest):
    try:
        # 配置主容器
        container = client.V1Container(
            name=request.name,
            image=request.image,
            env=[client.V1EnvVar(name=e.name, value=e.value) for e in request.env] if request.env else None,
            security_context=client.V1SecurityContext(privileged=request.privileged) if request.privileged else None,
            resources=client.V1ResourceRequirements(
                limits={"cpu": request.resources.cpu, "memory": request.resources.memory} if request.resources else None
            ) if request.resources else None
        )

        # 配置初始化容器
        init_containers = [
            client.V1Container(
                name=ic.name,
                image=ic.image,
                command=ic.command
            ) for ic in request.init_containers
        ] if request.init_containers else None

        # 配置 Pod 规范
        pod_spec = client.V1PodSpec(
            containers=[container],
            init_containers=init_containers,
            host_network=request.host_network if request.host_network else False
        )

        # 创建 Pod 对象
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(name=request.name),
            spec=pod_spec
        )

        # 创建 Pod
        v1.create_namespaced_pod(namespace="default", body=pod)
        return {"message": f"Pod {request.name} 创建成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Pod 失败: {str(e)}")