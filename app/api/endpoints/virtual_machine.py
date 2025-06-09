from fastapi import APIRouter, HTTPException
from app.services import virtual_machine as vm_service
from app.models.schemas import VMCreateRequest, VMCreateResponse, VMListResponse
from app.services.virtual_machine import create_virtual_machine
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/virtual_machine", tags=["Virtual Machines"])

@router.get("/vms", response_model=VMListResponse)
def get_vms(namespace: str = "default"):
    vms = vm_service.list_virtual_machines(namespace)
    return {"vms": vms}

@router.post("/vm/create", response_model=VMCreateResponse)
def create_virtual_machine_api(req: VMCreateRequest):
    try:
        # 创建虚拟机
        result = create_virtual_machine(
            name=req.name,
            namespace=req.namespace,
            cpu=req.cpu,
            memory=req.memory,
            image=req.image,
            network_interfaces=req.network_interfaces,
            storage_disks=req.storage_disks,
            image_pull_secret=req.image_pull_secret,
            node_selector=req.node_selector,
            autostart=req.autostart,
            cloud_init_user_data=req.cloud_init_user_data
        )
        
        # 返回响应
        return VMCreateResponse(
            name=req.name,
            namespace=req.namespace,
            status="created",
            message="虚拟机创建成功",
            vm_ip=result.get("ip")
        )
        
    except Exception as e:
        logger.error(f"创建虚拟机失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"虚拟机创建失败: {str(e)}"
        )