from fastapi import FastAPI
from app.api import auto_load_routers
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import layer_config

app = FastAPI()
app.include_router(auto_load_routers())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    config_path = "/root/cedfs_deploy/config/meta/meta-19.toml"
    layer_config.load_from_file(config_path)

@app.get("/")
def root():
    return {"msg": "K8s 资源监控 API 正常运行"}
