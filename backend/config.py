from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "PENCIL_"}

    comfyui_url: str = "http://127.0.0.1:18188"
    comfyui_timeout: int = 30
    comfyui_poll_interval: float = 1.0
    comfyui_poll_timeout: float = 120.0

    host: str = "127.0.0.1"
    port: int = 8000

    default_prompt: str = "a colorful illustration, vibrant colors, detailed shading"
    default_steps: int = 4
    max_image_size: int = 10 * 1024 * 1024  # 10 MB

    workflow_template: str = "workflow_template.json"

    signup_enabled: bool = False
    git_commit: str = "dev"

    usage_salt: str = "dev-salt-change-in-production"
    usage_db: str = "data/usage.db"

    rate_limit_window: int = 60  # seconds
    rate_limit_max: int = 15  # max requests per window per IP


settings = Settings()
