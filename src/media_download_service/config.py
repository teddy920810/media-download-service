from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    internal_service_token: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket: str
    r2_endpoint: str
    replicate_api_token: str | None = None


def get_settings() -> Settings:
    required = {
        "INTERNAL_SERVICE_TOKEN": os.getenv("INTERNAL_SERVICE_TOKEN"),
        "R2_ACCOUNT_ID": os.getenv("R2_ACCOUNT_ID"),
        "R2_ACCESS_KEY_ID": os.getenv("R2_ACCESS_KEY_ID"),
        "R2_SECRET_ACCESS_KEY": os.getenv("R2_SECRET_ACCESS_KEY"),
        "R2_BUCKET": os.getenv("R2_BUCKET"),
        "R2_ENDPOINT": os.getenv("R2_ENDPOINT"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required service configuration: {', '.join(missing)}")
    return Settings(
        internal_service_token=required["INTERNAL_SERVICE_TOKEN"] or "",
        r2_account_id=required["R2_ACCOUNT_ID"] or "",
        r2_access_key_id=required["R2_ACCESS_KEY_ID"] or "",
        r2_secret_access_key=required["R2_SECRET_ACCESS_KEY"] or "",
        r2_bucket=required["R2_BUCKET"] or "",
        r2_endpoint=required["R2_ENDPOINT"] or "",
        replicate_api_token=os.getenv("REPLICATE_API_TOKEN") or None,
    )
