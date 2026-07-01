from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # petit modèle par défaut (coût maîtrisé)
    sentry_dsn: str = ""
    database_url: str = "sqlite:///./data/valo.db"
    environment: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
