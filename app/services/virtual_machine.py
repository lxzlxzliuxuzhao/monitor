from kubernetes import client, config
from kubernetes.watch import Watch
from typing import Optional, List, Dict, Union
from app.models.schemas import VMInfo
import datetime
import time
from app.models.schemas import NetworkInterface, StorageDisk

def get_vm_pod_ip(namespace: str, vm_name: str):
    v1 = client.CoreV1Api()
    label_selector = f"kubevirt.io/domain={vm_name}"
    pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
    for pod in pods.items:
        if pod.status.phase == "Running":
            return pod.status.pod_ip
    return None

def list_virtual_machines(namespace: str = "default") -> List[VMInfo]:
    config.load_kube_config()
    api = client.CustomObjectsApi()
    
    vms = api.list_namespaced_custom_object(
        group="kubevirt.io",
        version="v1",
        namespace=namespace,
        plural="virtualmachines"
    )

    result = []
    for item in vms.get("items", []):
        metadata = item["metadata"]
        spec = item.get("spec", {})
        status = item.get("status", {})

        name = metadata.get("name")
        labels = metadata.get("labels", {})
        creation_timestamp = metadata.get("creationTimestamp")
        cpu = spec.get("template", {}).get("spec", {}).get("domain", {}).get("cpu", {}).get("cores", None)
        memory = spec.get("template", {}).get("spec", {}).get("domain", {}).get("resources", {}).get("requests", {}).get("memory", None)
        ip = get_vm_pod_ip(namespace, name)
        vm_status = status.get("printableStatus", "Unknown")
        template = labels.get("kubevirt.io/template")

        result.append(VMInfo(
            name=name,
            namespace=namespace,
            status=vm_status,
            ip=ip,
            cpu=cpu,
            memory=memory,
            created_at=creation_timestamp,
            template=template,
            labels=labels
        ))

    return result

def create_virtual_machine(
    name: str,
    namespace: str,
    cpu: int,
    memory: str,
    image: str,
    network_interfaces: List[NetworkInterface],
    storage_disks: List[StorageDisk],
    image_pull_secret: Optional[str] = None,
    node_selector: Optional[Dict[str, str]] = None,
    autostart: bool = False,
    cloud_init_user_data: Optional[str] = None
) -> dict:
    """
    创建增强版虚拟机，支持持久化存储和高级网络
    """
    config.load_kube_config()
    api = client.CustomObjectsApi()
    core_api = client.CoreV1Api()

    # ===== 存储配置 =====
    volumes = []
    disks = []
    
    # 处理系统镜像
    boot_disk = next((disk for disk in storage_disks if disk.bootable), None)
    if not boot_disk:
        raise ValueError("未找到启动盘配置")
    
    volumes.append({
        "name": boot_disk.name,
        "containerDisk": {
            "image": image,
            "imagePullSecret": image_pull_secret
        } if image_pull_secret else {"image": image}
    })
    disks.append({
        "name": boot_disk.name,
        "bootOrder": 1,
        "disk": {"bus": "virtio"}
    })
    
    # 处理数据磁盘
    for disk in storage_disks:
        if not disk.bootable:  # 数据盘
            pvc_name = f"{name}-{disk.name}"
            
            # 创建PVC
            pvc_manifest = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": pvc_name,
                    "namespace": namespace
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": disk.storage_class,
                    "resources": {
                        "requests": {"storage": disk.size}
                    }
                }
            }
            core_api.create_namespaced_persistent_volume_claim(
                namespace=namespace, 
                body=pvc_manifest
            )
            
            volumes.append({
                "name": disk.name,
                "persistentVolumeClaim": {"claimName": pvc_name}
            })
            disks.append({
                "name": disk.name,
                "disk": {"bus": "virtio"}
            })
    
    # ===== 网络配置 =====
    interfaces = []
    networks = []
    
    for i, net_if in enumerate(network_interfaces, start=1):
        # 默认MAC地址生成规则
        if not net_if.mac_address:
            net_prefix = "02:00:00:%02x:%02x:%02x" % (
                i // 256, i % 256, namespace_hash(namespace) % 256
            )
            net_if.mac_address = net_prefix
            
        interfaces.append({
            "name": net_if.name,
            "macAddress": net_if.mac_address,
            net_if.type: {}
        })
        
        networks.append({
            "name": net_if.name,
            "pod" if net_if.network == "default" else "multus": {
                "networkName": net_if.network
            }
        })
    
    # ===== 资源限制 =====
    # 计算内存限制（请求内存的1.5倍）
    if memory.endswith('Mi'):
        base = int(memory[:-2])
        limit = f"{int(base * 1.5)}Mi"
    elif memory.endswith('Gi'):
        base = int(memory[:-2])
        limit = f"{base * 1.5:.1f}Gi"
    else:
        limit = memory
    
    # ===== 虚拟机模板 =====
    template_spec = {
        "domain": {
            "cpu": {"cores": cpu},
            "devices": {
                "disks": disks,
                "interfaces": interfaces
            },
            "resources": {
                "requests": {"memory": memory, "cpu": str(cpu)},
                "limits": {"memory": limit}
            }
        },
        "networks": networks,
        "volumes": volumes
    }
    
    # 添加节点选择器
    if node_selector:
        template_spec["nodeSelector"] = node_selector
    
    # 添加cloud-init配置
    if cloud_init_user_data:
        volumes.append({
            "name": "cloudinitdisk",
            "cloudInitNoCloud": {
                "userData": cloud_init_user_data
            }
        })
        disks.append({
            "name": "cloudinitdisk",
            "disk": {"bus": "virtio"}
        })
    
    # ===== 虚拟机定义 =====
    vm_manifest = {
        "apiVersion": "kubevirt.io/v1",
        "kind": "VirtualMachine",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "annotations": {
                "kubevirt.io/latest-observed-api-version": "v1"
            }
        },
        "spec": {
            "runStrategy": "Always" if autostart else "Halted",
            "template": {
                "metadata": {
                    "labels": {"kubevirt.io/domain": name}
                },
                "spec": template_spec
            }
        }
    }
    
    # 创建虚拟机
    vm = api.create_namespaced_custom_object(
        group="kubevirt.io",
        version="v1",
        namespace=namespace,
        plural="virtualmachines",
        body=vm_manifest
    )
    
    # 监控启动状态
    vm_ip = None
    if autostart:
        vm_ip = _monitor_vm_startup(api, name, namespace)
    
    return {"vm": vm, "ip": vm_ip}

def namespace_hash(namespace: str) -> int:
    """生成命名空间的简单哈希值"""
    return sum(ord(c) for c in namespace) % 256

def _monitor_vm_startup(api, name: str, namespace: str, timeout: int = 300) -> str:
    """
    监控虚拟机启动并获取IP地址
    返回: 主IP地址
    """
    w = Watch()
    start_time = time.time()
    last_phase = ""
    vm_ip = None
    
    print(f"⏳ 开始监控虚拟机 {name} 启动状态...")
    
    for event in w.stream(
        api.list_namespaced_custom_object,
        group="kubevirt.io",
        version="v1",
        namespace=namespace,
        plural="virtualmachineinstances",
        timeout_seconds=timeout
    ):
        vmi = event['object']
        if vmi['metadata']['name'] != name:
            continue
            
        # 检查阶段变化
        phase = vmi['status'].get('phase', 'Pending')
        if phase != last_phase:
            print(f"🔧 虚拟机状态: {phase}")
            last_phase = phase
            
        # 检查IP地址
        interfaces = vmi['status'].get('interfaces', [])
        for iface in interfaces:
            if ip := iface.get('ipAddress'):
                vm_ip = ip
                print(f"📡 检测到IP地址: {vm_ip}")
        
        # 成功启动判断
        if phase == 'Running' and vm_ip:
            print("✅ 虚拟机启动成功!")
            return vm_ip
        
        # 错误检查
        conditions = vmi['status'].get('conditions', [])
        for cond in conditions:
            if cond['type'] == 'Failure' and cond['status'] == 'True':
                error_msg = cond.get('message', '未知错误')
                if 'ImagePullBackOff' in error_msg:
                    raise RuntimeError(f"❌ 镜像拉取失败: {error_msg}")
                elif 'Insufficient' in error_msg:
                    raise RuntimeError(f"❌ 资源不足: {error_msg}")
                else:
                    raise RuntimeError(f"❌ 虚拟机启动失败: {error_msg}")
        
        # 超时检查
        if time.time() - start_time > timeout:
            raise TimeoutError(f"⌛ 虚拟机启动超时（{timeout}秒）")
    
    raise RuntimeError("监控意外终止")
