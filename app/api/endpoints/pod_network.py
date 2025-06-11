from fastapi import APIRouter, Depends
from app.models.schemas import Pod_Network_Info
from app.services.pod_network import PodService

router = APIRouter(prefix="/pods", tags=["Pods"])

def get_pod_service():
    return PodService()

@router.get("/{namespace}/{pod_name}", response_model=Pod_Network_Info)
async def get_pod_info(pod_name: str, namespace: str = "default", service: PodService = Depends(get_pod_service)):
    return service.get_pod_info(pod_name, namespace)

@router.get("/{namespace}", response_model=list[Pod_Network_Info])
async def listPodsInfo(namespace: str = "default", service: PodService = Depends(get_pod_service)):
    return service.listPodsInfo(namespace)

@router.get("/", response_model=list[Pod_Network_Info])
async def listAllPodsInfo(service: PodService = Depends(get_pod_service)):
    return service.listAllPodsInfo()