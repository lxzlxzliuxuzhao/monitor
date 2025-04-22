import requests
from app.core.config import settings

def query_prometheus(query: str):
    url = f"{settings.PROM_URL}/api/v1/query"
    response = requests.get(url, params={"query": query})
    return response.json()["data"]["result"]
