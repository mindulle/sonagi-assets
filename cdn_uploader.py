import os
import mimetypes
import boto3
from botocore.client import Config

# Configuration
MINIO_URL = "https://cdn.sonagi.space"
ACCESS_KEY = "admin"       # Replace with actual credentials if different
SECRET_KEY = "anki123456"

# Initialize S3 client for MinIO
s3 = boto3.client('s3',
                  endpoint_url=MINIO_URL,
                  aws_access_key_id=ACCESS_KEY,
                  aws_secret_access_key=SECRET_KEY,
                  config=Config(signature_version='s3v4'),
                  region_name='us-east-1')

def upload_to_cdn(file_path: str, bucket: str = "references"):
    file_name = os.path.basename(file_path)
    
    # Auto-detect Content-Type (HTML, MP4, JSON, etc.)
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    print(f"Uploading {file_name} with Content-Type: {content_type}")
    
    # Upload with explicitly forced Content-Type
    s3.upload_file(
        file_path, 
        bucket, 
        file_name,
        ExtraArgs={'ContentType': content_type}
    )
    
    return f"{MINIO_URL}/{bucket}/{file_name}"

if __name__ == "__main__":
    # Example usage
    # print(upload_to_cdn("interactive_prototype.html"))
    # print(upload_to_cdn("flow_recording.mp4"))
    pass
