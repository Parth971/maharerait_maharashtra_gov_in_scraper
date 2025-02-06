from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    captcha_solver_api_key: str = Field(default="", description="2captcha API key")
    parallel: int = Field(default=1, description="Number of parallel browsers")
    output_dir: Path = Field(
        default=BASE_DIR / "output", description="Output directory"
    )
    headless: bool = Field(default=True, description="Run in headless mode")
    logs_directory: Path = Field(default=BASE_DIR / "logs")
    debug: bool = Field(default=False)
    max_captcha_attempts: int = Field(
        default=5, description="Maximum number of captcha attempts"
    )
    cache_file_path: Path = Field(
        default=BASE_DIR / ".cache/map.json", description="Cache file path"
    )
    input_file_path: Path = Field(
        default=BASE_DIR / "sample.xlsx", description="Input file path"
    )
    input_column_name: str = Field(
        default="Registration Number", description="Input column name"
    )

    class Config:
        env_file = ".env"


settings = Settings()
