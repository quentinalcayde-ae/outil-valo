from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    sentry_dsn: str = ""
    database_url: str = "sqlite:///./data/valo.db"
    environment: str = "development"

    model_config = {"env_file": ".env"}


settings = Settings()
