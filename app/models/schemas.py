# app/models/schemas.py
from pydantic import BaseModel
from typing import List

class ContainerInfo(BaseModel):
    name: str
    image: str
    ready: str
    status: str
    restarts: str

class PodInfo(BaseModel):
    name: str
    namespace: str
    pod_name: str
    ready: str
    restarts: str
    age: str
    IP: str
    node: str
    nominated_node: str
    readiness_gates: str
    containers_list: List[ContainerInfo]