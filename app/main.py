from fastapi import FastAPI
from app.api import auto_load_routers

app = FastAPI()
app.include_router(auto_load_routers())

@app.get("/")
def root():
    return {"msg": "K8s 资源监控 API 正常运行"}
