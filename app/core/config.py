from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROM_URL: str = "http://localhost:19090"

    class Config:
        env_file = ".env"

settings = Settings()
