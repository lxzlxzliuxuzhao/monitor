from fastapi import FastAPI
from app.api import auto_load_routers
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.include_router(auto_load_routers())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"msg": "K8s 资源监控 API 正常运行"}
