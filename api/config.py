import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://skor_user:skor_password@localhost:5432/skor_shield"
    )
    
    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", 8000))
    
    # Model
    model_path: str = os.getenv("MODEL_PATH", "models/xgboost_model.pkl")
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
