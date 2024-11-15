from typing import Any, Dict

import boto3
from pydantic import EmailStr

from app.config import settings


class EmailSender:
    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION,
        )
        self.ses = self.session.client("ses")

    def load_template(self, template_path: str) -> str:
        try:
            with open(template_path, "r", encoding="utf-8") as file:
                template = file.read()
            return template
        except FileNotFoundError:
            print(f"Error: Could not find the template file at {template_path}")
            return ""
        except Exception as e:
            print(f"Error reading or processing the template: {str(e)}")
            return ""

    def process_template(
        self, template_content: str, placeholders: Dict[str, Any]
    ) -> str:
        for key, value in placeholders.items():
            template_content = template_content.replace(f"{{{key}}}", str(value))
        return template_content

    async def send_email_with_template(
        self,
        recipient: EmailStr,
        subject: str,
        template_path: str,
        placeholders: Dict[str, Any],
    ) -> bool:
        template_content = self.load_template(template_path)
        if not template_content:
            return False

        html_message = self.process_template(template_content, placeholders)

        try:
            response = self.ses.send_email(
                Source=settings.SMTP_EMAIL,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": html_message}},
                },
            )
            return response["ResponseMetadata"]["HTTPStatusCode"] == 200
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
