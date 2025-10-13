from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    aws_profile: str | None
    aws_region: str
    bucket_name: str
    key_prefix: str
    timezone_offset_hours: int


def load_config() -> AppConfig:
    return AppConfig(
        aws_profile=os.getenv("AWS_PROFILE") or "",
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        bucket_name=os.getenv("BUCKET_NAME", "loan-deferment-idp-event-triggered-tlek"),
        key_prefix=os.getenv("KEY_PREFIX", "requests/"),
        timezone_offset_hours=int(os.getenv("TZ_OFFSET_HOURS", "5")),
    )
