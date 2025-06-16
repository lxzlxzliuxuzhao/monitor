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