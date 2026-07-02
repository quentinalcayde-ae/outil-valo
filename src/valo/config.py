from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    # Découverte en 2 temps : un modèle fort raisonne (quels comps/transactions),
    # un petit modèle rapide met en forme le JSON strict.
    discovery_model: str = "gpt-4o-mini"       # DISCOVERY_MODEL (raisonnement)
    fast_formatting_model: str = "gpt-4o-mini"  # FAST_FORMATTING_MODEL (mise en forme JSON)
    sentry_dsn: str = ""
    database_url: str = "sqlite:///./data/valo.db"
    environment: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
