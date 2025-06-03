# app/api/endpoints/container.py
from fastapi import APIRouter
from typing import List
from app.services.container import ContainerService
from app.models.schemas import PodInfo

router = APIRouter(prefix="/containers", tags=["Containers"])

service = ContainerService()

@router.get("/", response_model=List[PodInfo])
def list_containers():
    return service.get_all_containers()