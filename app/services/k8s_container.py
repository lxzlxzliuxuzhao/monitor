from fastapi import HTTPException
from kubernetes import client, config
from pydantic import BaseModel, validator
from typing import Optional, List, Union
from fastapi.responses import JSONResponse

# 定义数据模型 - 修复 command 字段处理
class ResourceConfig(BaseModel):
    cpu: Optional[str] = None
    memory: Optional[str] = None

class InitContainer(BaseModel):
    name: Optional[str] = None
    image: Optional[str] = None
    command: Optional[Union[List[str], str]] = None  # 接受字符串或列表
    
    @validator('command', pre=True)
    def handle_command(cls, v):
        """处理命令字段的各种输入格式"""
        if v == "":  # 空字符串转为空列表
            return []
        if isinstance(v, str):  # 单个字符串转为列表
            return [v]
        return v

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

# 加载 Kubernetes 配置
config.load_kube_config(config_file="/etc/kubernetes/admin.conf")
v1 = client.CoreV1Api()

def create_k8s_pod(request: ContainerRequest):
    try:
        # 基础验证 - 只验证必须字段
        if not request.name or not request.image:
            raise HTTPException(status_code=400, detail="名称和镜像不能为空")

        # 配置主容器 - 简化处理
        env_list = None
        if request.env:
            # 只添加有效的环境变量
            env_list = [
                client.V1EnvVar(name=e.name, value=e.value) 
                for e in request.env 
                if e.name and e.value  # 过滤空值
            ]
            if not env_list:  # 如果过滤后为空，设为None
                env_list = None

        # 处理资源限制 - 只设置有效值
        resources = None
        if request.resources and (request.resources.cpu or request.resources.memory):
            limits = {}
            if request.resources.cpu:
                limits["cpu"] = request.resources.cpu
            if request.resources.memory:
                limits["memory"] = request.resources.memory
            resources = client.V1ResourceRequirements(limits=limits)

        # 创建容器配置
        container = client.V1Container(
            name=request.name,
            image=request.image,
            env=env_list,
            security_context=client.V1SecurityContext(
                privileged=request.privileged
            ) if request.privileged else None,
            resources=resources
        )

        # 配置初始化容器 - 只添加有效容器
        init_containers = None
        if request.init_containers:
            valid_containers = []
            for ic in request.init_containers:
                # 只处理有名称和镜像的容器
                if ic.name and ic.image:
                    # 确保命令是列表格式
                    command = ic.command
                    if command is None:
                        command = []
                    elif isinstance(command, str):
                        command = [command]
                    
                    valid_containers.append(client.V1Container(
                        name=ic.name,
                        image=ic.image,
                        command=command
                    ))
            
            if valid_containers:  # 如果有有效容器才设置
                init_containers = valid_containers

        # 配置 Pod 规范
        pod_spec = client.V1PodSpec(
            containers=[container],
            init_containers=init_containers,
            host_network=request.host_network
        )

        # 创建 Pod 对象
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(name=request.name),
            spec=pod_spec
        )

        # 创建 Pod
        v1.create_namespaced_pod(namespace="default", body=pod)
        return JSONResponse(status_code=200, content={"message": f"Pod {request.name} 创建成功"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Pod 失败: {str(e)}")
        
def delete_k8s_pod(pod_name: str):
    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")
        return JSONResponse(status_code=200, content={"message": f"Pod {pod_name} 删除成功"})
    except client.ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Pod {pod_name} 不存在")
        raise HTTPException(status_code=500, detail=f"删除 Pod 失败: {str(e)}")