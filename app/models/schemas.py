# app/models/schemas.py
from pydantic import BaseModel
from typing import List

class ContainerInfo(BaseModel):
    namespace: str
    pod_name: str
    container_name: str
    image: str
    status: str