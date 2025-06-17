from fastapi import APIRouter, HTTPException
from app.services.deployment_mount_service import DeploymentMountService
from app.models.schemas import DeploymentMountStats

router = APIRouter()

@router.get(
    "/deployments/{deployment_name}/mounts",
    response_model=DeploymentMountStats,
    summary="获取 Deployment 的挂载统计信息"
)
async def get_deployment_mounts(
    deployment_name: str, 
    namespace: str = "default"
) -> DeploymentMountStats:
    """
    获取指定 Deployment 的挂载详细信息
    
    参数:
        - deployment_name: Deployment 名称
        - namespace: 命名空间 (默认为 'default')
        
    返回:
        - 容器挂载信息
        - 卷类型统计
        - 挂载点详细信息
    """
    try:
        service = DeploymentMountService()
        return service.get_deployment_mount_stats(deployment_name, namespace)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取挂载信息失败: {str(e)}"
        )