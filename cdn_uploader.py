import mimetypes
import os

import boto3
from botocore.client import Config

MINIO_ENV_PATH = os.path.expanduser("~/.config/sonagi/minio.env")


def load_minio_config() -> dict:
    """MinIO 자격증명은 코드가 아니라 MINIO_ENV_PATH(600) 에서 읽는다. 환경변수가 우선."""
    cfg = {"MINIO_ENDPOINT": "https://cdn.sonagi.space"}
    try:
        with open(MINIO_ENV_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                cfg[key.strip()] = value.strip().strip("'\"")
    except OSError:
        pass
    for key in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


MINIO = load_minio_config()

# Configuration
MINIO_URL = MINIO["MINIO_ENDPOINT"]
ACCESS_KEY = MINIO.get("MINIO_ACCESS_KEY", "")
SECRET_KEY = MINIO.get("MINIO_SECRET_KEY", "")

# Initialize S3 client for MinIO
s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_URL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def upload_to_cdn(file_path: str, bucket: str = "references", object_name: str = None):
    file_name = os.path.basename(file_path)
    if object_name is None:
        object_name = file_name

    # Auto-detect Content-Type (HTML, MP4, JSON, etc.)
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    print(f"Uploading {object_name} with Content-Type: {content_type}")

    # Upload with explicitly forced Content-Type
    s3.upload_file(file_path, bucket, object_name, ExtraArgs={"ContentType": content_type})

    return f"{MINIO_URL}/{bucket}/{object_name}"


if __name__ == "__main__":
    # Example usage
    # print(upload_to_cdn("interactive_prototype.html"))
    # print(upload_to_cdn("flow_recording.mp4"))
    pass
