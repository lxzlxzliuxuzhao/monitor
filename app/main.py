from fastapi import FastAPI
from app.api.endpoints import cpu, storage, network, gpu, summary

app = FastAPI()

app.include_router(cpu.router, prefix="/api/cpu")
app.include_router(storage.router, prefix="/api/storage")
app.include_router(network.router, prefix="/api/net")
app.include_router(gpu.router, prefix="/api/gpu")
app.include_router(summary.router, prefix="/api/summary")

@app.get("/")
def root():
    return {"msg": "K8s 资源监控 API 正常运行"}
