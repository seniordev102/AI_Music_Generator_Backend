import logging
import re

import boto3
import requests
from fastapi import UploadFile

from app.config import settings


class S3FileClient:
    s3_instance = None
    instance_type = "s3"
    bucket_name = settings.AWS_S3_BUCKET_NAME

    def __init__(self):
        self.s3_instance = boto3.client(
            self.instance_type,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION,
        )
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def upload_file_if_not_exists(
        self, folder_name, file_name, file_content, content_type
    ):

        # if file name has spaces and special characters, replace them with hyphen using regex
        sanitized_filename = re.sub(r"[^a-zA-Z0-9.]", "-", file_name)
        file_path = f"{folder_name}/{sanitized_filename}"

        # Uploads the file, overwriting if it already exists
        self.s3_instance.put_object(
            Bucket=self.bucket_name,
            Key=file_path,
            Body=file_content,
            ContentType=content_type,
        )

        # Return the file URL
        return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"

    def upload_file(self, file_name, file_content, content_type):

        # if file name has spaces and special characters, replace them with hyphen using regex
        sanitized_filename = re.sub(r"[^a-zA-Z0-9.]", "-", file_name)

        self.s3_instance.put_object(
            Bucket=self.bucket_name,
            Key=sanitized_filename,
            Body=file_content,
            ContentType=content_type,
        )
        return f"https://{self.bucket_name}.s3.amazonaws.com/{sanitized_filename}"

    async def http_to_s3_upload(self, upload_file: UploadFile) -> str:

        upload_file.file.seek(0)
        file_content: UploadFile = await upload_file.read()

        # if file name has spaces and special characters, replace them with hyphen using regex
        sanitized_filename = re.sub(r"[^a-zA-Z0-9.]", "-", upload_file.filename)

        self.s3_instance.put_object(
            Bucket=self.bucket_name,
            Key=sanitized_filename,
            Body=file_content,
            ContentType=upload_file.content_type,
        )
        return f"https://{self.bucket_name}.s3.amazonaws.com/{sanitized_filename}"

    async def upload_image_from_url(self, url, file_name, content_type):
        file_content = requests.get(url).content
        file_path = f"ai-album-art/{file_name}"
        self.s3_instance.put_object(
            Bucket=self.bucket_name,
            Key=file_path,
            Body=file_content,
            ContentType=content_type,
        )
        return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"

    def delete_file(self, file_name):
        self.s3_instance.delete_object(Bucket=self.bucket_name, Key=file_name)
        return True

    def get_file(self, file_name):
        return self.s3_instance.get_object(Bucket=self.bucket_name, Key=file_name)

    def upload_file_object_to_s3(self, file_name, img_byte_array, content_type):
        file_path = (
            f"ai-album-art/{file_name}"  # Assuming you want to keep this structure
        )
        self.s3_instance.upload_fileobj(
            Fileobj=img_byte_array,  # The byte stream to upload
            Bucket=self.bucket_name,
            Key=file_path,
            ExtraArgs={"ContentType": content_type},  # Setting content type
        )
        return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"

    def upload_file_from_local_image(self, file_name, file_content, content_type):
        file_path = f"ai-album-art/{file_name}"
        self.s3_instance.put_object(
            Bucket=self.bucket_name,
            Key=file_path,
            Body=file_content,
            ContentType=content_type,
        )
        return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"

    def upload_file_from_url_sync(
        self, url: str, folder_name: str, file_name: str, content_type: str
    ):
        try:
            self.logger.info(f"Uploading file to s3 from URL: {url}")
            file_content = requests.get(url).content
            file_path = f"{folder_name}/{file_name}"
            self.s3_instance.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
            )
            return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"
        except Exception as e:
            self.logger.error(f"Error uploading file to S3: {e}")
            return None

    def upload_file_from_buffer(
        self, file_name: str, folder_name: str, file_content: bytes, content_type: str
    ):
        try:
            self.logger.info(f"Uploading file to s3 from buffer: {file_name}")
            file_path = f"{folder_name}/{file_name}"
            self.s3_instance.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
            )
            return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"
        except Exception as e:
            self.logger.error(f"Error uploading file to S3: {e}")
            return None

    def upload_file_from_buffer_sync(
        self, file_content: bytes, folder_name: str, file_name: str, content_type: str
    ):
        try:
            file_path = f"{folder_name}/{file_name}"
            self.s3_instance.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
            )
            return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"
        except Exception as e:
            self.logger.error(f"Error uploading file to S3: {e}")
            return None
