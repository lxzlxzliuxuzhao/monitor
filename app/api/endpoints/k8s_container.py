from fastapi import APIRouter, HTTPException
from kubernetes import client
from app.models.schemas import VolumeMountRequest
from app.services.k8s_container import create_k8s_pod, delete_k8s_pod, ContainerRequest, add_volume_to_deployment

router = APIRouter()

@router.post("/k8s_containers")
async def create_container(request: ContainerRequest):
    return create_k8s_pod(request)

@router.post("/delete_k8s_containers/{pod_name}")
async def delete_container(pod_name: str):
    return delete_k8s_pod(pod_name)

@router.post("/add-volume")
async def add_volume_mount(request: VolumeMountRequest):
    """
    为指定 Deployment 添加新卷挂载。
    """
    try:
        success = add_volume_to_deployment(
            namespace=request.namespace,
            deployment_name=request.deployment_name,
            volume_name=request.volume_name,
            mount_path=request.mount_path,
            host_path=request.host_path
        )
        if success:
            return {"message": f"Successfully updated Deployment {request.deployment_name} with volume mount {request.mount_path}"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add volume mount: volume or mount already exists")
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Kubernetes API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")