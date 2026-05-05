from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://leaderboard:leaderboard@localhost:5432/leaderboard"
    secret_key: str = "change-me"
    admin_username: str = "admin"
    admin_password: str = "admin"
    data_dir: Path = Path("./data")
    default_locale: str = "uz"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def groundtruth_dir(self) -> Path:
        return self.data_dir / "groundtruth"

    @property
    def submissions_dir(self) -> Path:
        return self.data_dir / "submissions"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"


settings = Settings()

for d in (settings.groundtruth_dir, settings.submissions_dir, settings.assets_dir):
    d.mkdir(parents=True, exist_ok=True)
