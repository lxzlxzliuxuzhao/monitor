# app/api/endpoints/container.py
from fastapi import APIRouter
from typing import List, Dict
from app.services.container import ContainerService
from app.models.schemas import PodInfo, DeploymentInfo

router = APIRouter(prefix="/containers", tags=["Containers"])

service = ContainerService()

@router.get("/", response_model=List[PodInfo])
def list_containers():
    return service.get_all_containers()

@router.get("/deployments", response_model=List[DeploymentInfo])
def list_deployments():
    return service.get_all_deployments()

@router.get("/counts", response_model=Dict[str, int])
def get_counts():
    """
    获取所有命名空间中非 KubeVirt 容器总数和 KubeVirt 虚拟机总数。
    
    Returns:
        Dict[str, int]: 包含容器总数和虚拟机总数的字典，例如 {"total_containers": 123, "total_vms": 10}
    """
    total_containers = service.count_containers()
    total_vms = service.count_kubevirt_vms()
    return {
        "total_containers": total_containers,
        "total_vms": total_vms
    }
