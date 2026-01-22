from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class SelectionSettings(BaseSettings):
    alpha: float = 10.0
    digest_size: int = 5
    default_last_notified: Literal["random", "zero"] = "zero"


class Settings(BaseSettings):
    selection: SelectionSettings = SelectionSettings()
    db_url: str = "sqlite:///./dump/daily_dose.db"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

settings = Settings()