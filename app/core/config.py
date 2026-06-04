from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GOV_AQI_API_KEY: str | None = None
    GOV_AQI_API_URL: str | None = None
    LOG_LEVEL: str = "INFO"

settings = Settings()
