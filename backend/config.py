"""应用配置管理 — 从 .env 文件加载，支持动态更新"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    yunwu_api_key: str = ""
    yunwu_base_url: str = "https://yunwu.ai"
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: str = "data"
    image_save_dir: str = "data/images"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def reload_settings():
    """重新加载 .env 文件中的配置"""
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    settings.yunwu_api_key = os.getenv("YUNWU_API_KEY", "")
    settings.yunwu_base_url = os.getenv("YUNWU_BASE_URL", "https://yunwu.ai")


def save_settings_to_env(api_key: str = "", base_url: str = ""):
    """保存配置到 .env 文件并立即生效"""
    env_path = ".env"

    existing = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    existing[key.strip()] = val.strip()

    if api_key:
        existing["YUNWU_API_KEY"] = api_key
    if base_url:
        existing["YUNWU_BASE_URL"] = base_url
    existing["HOST"] = settings.host
    existing["PORT"] = str(settings.port)

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# 云雾API 配置\n")
        f.write(f"YUNWU_API_KEY={existing.get('YUNWU_API_KEY', '')}\n")
        f.write(f"YUNWU_BASE_URL={existing.get('YUNWU_BASE_URL', 'https://yunwu.ai')}\n")
        f.write("\n# 服务配置\n")
        f.write(f"HOST={existing.get('HOST', '0.0.0.0')}\n")
        f.write(f"PORT={existing.get('PORT', '8000')}\n")

    # 动态更新当前配置
    if api_key:
        settings.yunwu_api_key = api_key
    if base_url:
        settings.yunwu_base_url = base_url
