
from pathlib import Path

from pydantic import SecretStr
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DEVELOPMENT_SECRET_KEY = "CHANGE_THIS_DEVELOPMENT_SECRET"


class Settings(BaseSettings):
    APP_NAME: str = "OxMaint"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    DATABASE_URL: str = (
        "postgresql+psycopg://oxmaint_user:CHANGE_ME@localhost:5432/oxmaint_db"
    )

    SECRET_KEY: str = DEVELOPMENT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if not self.DEBUG and (
            self.SECRET_KEY == DEVELOPMENT_SECRET_KEY
            or self.SECRET_KEY == "REPLACE_WITH_A_RANDOM_SECRET"
            or len(self.SECRET_KEY) < 32
        ):
            raise ValueError(
                "Set SECRET_KEY to a random value of at least 32 characters "
                "when DEBUG is disabled."
            )

        return self


settings = Settings()
