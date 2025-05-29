from fastapi import APIRouter
from app.services.k8s_container import create_k8s_pod, ContainerRequest  # 导入 ContainerRequest 模型

router = APIRouter()

@router.post("/k8s_containers")
async def create_container(request: ContainerRequest):
    return create_k8s_pod(request)