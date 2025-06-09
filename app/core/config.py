from pydantic_settings import BaseSettings
import toml
from typing import Dict

class LayerConfig:
    def __init__(self):
        self.layer_map: Dict[str, str] = {}

    def load_from_file(self, path: str):
        try:
            data = toml.load(path)
            self.layer_map.clear()

            self_info = data.get("meta", {}).get("route", {}).get("self", {})
            if "ipv4" in self_info and "layer" in self_info:
                self.layer_map[self_info["ipv4"]] = self_info["layer"]

            others = data.get("meta", {}).get("route", {}).get("other", [])
            for other in others:
                if "ipv4" in other and "layer" in other:
                    self.layer_map[other["ipv4"]] = other["layer"]

            print(f"[INFO] LAYER_MAP loaded: {self.layer_map}")
        except Exception as e:
            print(f"[ERROR] Failed to load layer config from {path}: {e}")

layer_config = LayerConfig()

class Settings(BaseSettings):
    PROM_URL: str = "http://localhost:19090"

    class Config:
        env_file = ".env"

settings = Settings()
