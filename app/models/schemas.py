# app/models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict

class ContainerInfo(BaseModel):
    """
    容器信息模型
    """
    name: str
    image: str
    ready: str
    status: str
    restarts: str

class PodInfo(BaseModel):
    """
    Pod信息模型
    """
    name: str
    namespace: str
    pod_name: str
    ready: str
    restarts: str
    age: str
    IP: str
    node: str
    nominated_node: str
    readiness_gates: str
    containers_list: List[ContainerInfo]

class VMInfo(BaseModel):
    """
    虚拟机信息模型
    """
    name: str
    namespace: str
    status: str
    ip: Optional[str]
    cpu: Optional[int]
    memory: Optional[str]
    created_at: Optional[str]
    template: Optional[str]
    labels: Optional[dict]

class VMListResponse(BaseModel):
    """
    虚拟机列表响应模型
    """
    vms: List[VMInfo]

class NetworkInterface(BaseModel):
    """
    网络接口配置
    """
    name: str = Field("net1", description="网络接口名称")
    type: str = Field("masquerade", description="接口类型: masquerade/bridge/sriov")
    network: str = Field("default", description="关联的网络名称")
    mac_address: Optional[str] = Field(None, description="MAC地址(自动生成)")
    ip_address: Optional[str] = Field(None, description="静态IP地址")

class StorageDisk(BaseModel):
    """
    存储磁盘配置
    """
    name: str = Field("disk1", description="磁盘名称")
    size: str = Field("10Gi", description="磁盘大小")
    storage_class: str = Field("standard", description="存储类名称")
    bootable: bool = Field(False, description="是否作为启动盘")

class VMCreateRequest(BaseModel):
    name: str = Field(..., description="虚拟机名称")
    namespace: str = Field("default", description="命名空间")
    cpu: int = Field(1, description="CPU核心数")
    memory: str = Field("1Gi", description="内存大小")
    image: str = Field("kubevirt/cirros-container-disk-demo", description="系统镜像")
    autostart: bool = Field(False, description="是否自动启动")
    
    network_interfaces: List[NetworkInterface] = Field(
        [NetworkInterface()], 
        description="网络接口配置"
    )
    storage_disks: List[StorageDisk] = Field(
        [StorageDisk(name="rootdisk", size="10Gi", bootable=True)], 
        description="存储磁盘配置"
    )
    image_pull_secret: Optional[str] = Field(
        None, 
        description="镜像拉取密钥名称"
    )
    node_selector: Dict[str, str] = Field(
        {}, 
        description="节点选择标签"
    )
    cloud_init_user_data: Optional[str] = Field(
        None, 
        description="cloud-init用户数据"
    )
    
    # 验证器
    @validator('memory')
    def validate_memory(cls, v):
        if not v.endswith(('Mi', 'Gi')):
            raise ValueError("内存格式错误，使用例如'512Mi'或'2Gi'")
        return v
    
    @validator('storage_disks')
    def validate_boot_disk(cls, v):
        boot_disks = [disk for disk in v if disk.bootable]
        if len(boot_disks) == 0:
            raise ValueError("至少需要一个启动盘")
        if len(boot_disks) > 1:
            raise ValueError("只能有一个启动盘")
        return v

class VMCreateResponse(BaseModel):
    name: str
    namespace: str
    status: str
    message: Optional[str] = None
    vm_ip: Optional[str] = None

class Pod_Network_Info(BaseModel):
    pod_name: str
    namespace: str
    status: str
    ip: Optional[str] = None
    DNS_latency: Optional[float] = None
    strategy: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "pod_name": "my-pod",
                "namespace": "default",
                "status": "Running",
                "ip": "192.168.1.10",
                "DNS_latency": 0.025,
                "strategy": "RollingUpdate"
            }
        }

class VolumeMountRequest(BaseModel):
    namespace: str = "default"
    deployment_name: str
    volume_name: str
    mount_path: str  # 容器内挂载路径，例如 /new-dir
    host_path: str   # 节点上目录路径，例如 /path/on/host

class NetworkPolicyRule(BaseModel):
    """网络策略规则模型
    
    属性:
        direction: 流量方向 ('ingress' 或 'egress')
        protocol: 网络协议 ('TCP' 或 'UDP')
        ports: 端口号列表
        source_pod_labels: 源Pod标签选择器
        source_namespace_labels: 源命名空间标签选择器
        description: 规则描述 (可选)
    """
    direction: str
    protocol: str
    ports: List[int]
    source_pod_labels: Optional[Dict[str, str]] = None
    source_namespace_labels: Optional[Dict[str, str]] = None
    description: Optional[str] = None

class DeploymentNetworkPolicyCreate(BaseModel):
    """为Deployment创建网络策略的请求模型
    
    属性:
        deployment_name: Deployment名称
        namespace: 命名空间 (默认为'default')
        rules: 网络策略规则列表
    """
    deployment_name: str
    namespace: str = "default"
    rules: List[NetworkPolicyRule]

class NetworkPolicyRuleResponse(BaseModel):
    """网络策略规则响应模型

    属性:
        direction: 流量方向 ('ingress' 或 'egress')
        protocol: 网络协议 ('TCP' 或 'UDP')
        ports: 端口号列表
        source_pod_labels: 源Pod标签选择器
        source_namespace_labels: 源命名空间标签选择器
        description: 规则描述 (可选)
    """
    direction: str
    protocol: str
    ports: List[int]
    source_pod_labels: Optional[Dict[str, str]] = None
    source_namespace_labels: Optional[Dict[str, str]] = None
    description: Optional[str] = None

class DeploymentNetworkPolicyResponse(BaseModel):
    """网络策略创建响应模型
    
    属性:
        policy_name: 创建的策略名称
        deployment_name: 关联的Deployment名称
        namespace: 命名空间
        pod_selector: Pod选择器标签
        ingress_rules: 入站规则
        egress_rules: 出站规则
    """
    policy_name: str
    deployment_name: str
    namespace: str
    pod_selector: Dict[str, str]
    ingress_rules: List[NetworkPolicyRuleResponse]
    egress_rules: List[NetworkPolicyRuleResponse]

class VolumeMountInfo(BaseModel):
    """卷挂载详细信息"""
    name: str
    mount_path: str
    read_only: Optional[bool] = False
    sub_path: Optional[str] = None
    mount_propagation: Optional[str] = None

class VolumeInfo(BaseModel):
    """卷详细信息"""
    name: str
    type: str = "unknown"  # configMap, secret, persistentVolumeClaim, hostPath, emptyDir 等
    config_map_name: Optional[str] = None
    secret_name: Optional[str] = None
    pvc_name: Optional[str] = None
    host_path: Optional[str] = None
    storage_class: Optional[str] = None
    size: Optional[str] = None  # 存储大小

class ContainerMountInfo(BaseModel):
    """容器挂载信息"""
    container_name: str
    volume_mounts: List[VolumeMountInfo] = []
    volumes: List[VolumeInfo] = []

class DeploymentMountStats(BaseModel):
    """Deployment 挂载统计信息"""
    deployment_name: str
    namespace: str
    containers: List[ContainerMountInfo] = []
    total_volumes: int = 0
    volume_types: Dict[str, int] = {}  # 卷类型统计
    total_mounts: int = 0

class VolumeMountInfo(BaseModel):
    """容器挂载点详细信息"""
    container: str = Field(..., description="容器名称")
    mount_path: str = Field(..., description="挂载路径")
    read_only: bool = Field(False, description="是否只读")
    sub_path: Optional[str] = Field(None, description="子路径")
    name: str = Field(..., description="引用的Volume名称")

class VolumeInfo(BaseModel):
    """Volume定义信息"""
    name: str = Field(..., description="Volume名称")
    type: str = Field(..., description="类型(configmap/secret/pvc等)")
    details: Optional[Dict] = Field(None, description="类型相关配置")

class DeploymentInfo(BaseModel):
    """
    Deployment信息模型（包含挂载信息）
    """
    name: str = Field(..., description="Deployment名称")
    namespace: str = Field(..., description="命名空间")
    ready: str = Field(..., description="就绪副本数/期望副本数，格式如 '1/3'")
    up_to_date: str = Field(..., description="符合最新模板的副本数")
    available: str = Field(..., description="可用副本数")
    age: str = Field(..., description="创建时间")
    volumes: List[VolumeInfo] = Field(default_factory=list, description="Volume定义列表")
    volume_mounts: List[VolumeMountInfo] = Field(default_factory=list, description="容器挂载点列表")

    @validator('ready')
    def validate_ready_format(cls, v):
        if not isinstance(v, str):
            raise ValueError('ready字段必须是字符串')
        if '/' not in v:
            raise ValueError('ready字段格式应为"就绪数/总数"，如"1/3"')
        return v

    @validator('volumes', 'volume_mounts', pre=True)
    def validate_empty_lists(cls, v):
        return v or []  # 确保None值转为空列表

    class Config:
        schema_extra = {
            "example": {
                "name": "nginx-deployment",
                "namespace": "default",
                "ready": "3/3",
                "up_to_date": "3",
                "available": "3",
                "age": "2d",
                "volumes": [
                    {
                        "name": "config-volume",
                        "type": "configmap",
                        "details": {
                            "name": "app-config",
                            "items": [{"key": "config.yaml", "path": "config.yaml"}]
                        }
                    }
                ],
                "volume_mounts": [
                    {
                        "container": "nginx",
                        "name": "config-volume",
                        "mount_path": "/etc/config",
                        "read_only": True,
                        "sub_path": ""
                    }
                ]
            }
        }