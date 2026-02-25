import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/sentra_db"
    )
    
    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", 8000))
    
    # Model
    model_path: str = os.getenv("MODEL_PATH", "models/fraud_model.pkl")
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "production")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Sentra credentials
    sentra_email: str = os.getenv("SENTRA_EMAIL", "")
    sentra_password: str = os.getenv("SENTRA_PASSWORD", "")
    sentra_api_url: str = os.getenv("SENTRA_API_URL", "")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

settings = Settings()
