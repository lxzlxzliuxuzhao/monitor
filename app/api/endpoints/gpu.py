from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_gpu():
    return {"msg": "GPU 接口由你实现，可以从 dcgm-exporter 的指标出发封装 PromQL 查询"}
