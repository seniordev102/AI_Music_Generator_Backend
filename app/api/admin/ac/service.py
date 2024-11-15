import requests
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import db_session
from app.models import User


class ActiveCampaignService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def sync_all_contact_to_active_campaign(self):
        #  get all user counts
        all_user_records = await self.session.execute(select(User))
        all_users: list[User] = all_user_records.scalars().all()

        endpoint = f"{settings.ACTIVE_CAMPAIGN_API_URL}/api/3/contact/sync"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Api-Token": settings.ACTIVE_CAMPAIGN_API_KEY,
        }
        for user in all_users:
            # if only has the last name
            if len(user.name.split(" ")) == 1:
                first_name = user.name
                last_name = ""
            else:
                first_name = user.name.split(" ")[0]
                last_name = user.name.split(" ")[1]

            try:
                payload = {
                    "contact": {
                        "firstName": first_name,
                        "lastName": last_name,
                        "email": user.email,
                        "fieldValues": [{"field": "1", "value": user.invite_code}],
                    }
                }
                response = requests.post(endpoint, json=payload, headers=headers)
                print(
                    f"{user.email} has been synced to Active Campaign - status code: {response.status_code}"
                )
            except Exception as e:
                print(e)
                print(f"Failed to sync {user.email} to Active Campaign")

        return True

    async def get_all_active_campaign_contact_list(self):
        endpoint = f"{settings.ACTIVE_CAMPAIGN_API_URL}/api/3/contacts"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Api-Token": settings.ACTIVE_CAMPAIGN_API_KEY,
        }

        response = requests.get(endpoint, headers=headers)

        if response.status_code == 200:
            payload = response.json()
            meta = payload["meta"]
            return meta

    async def add_new_contact_to_ac(self, user: User):
        endpoint = f"{settings.ACTIVE_CAMPAIGN_API_URL}/api/3/contact/sync"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Api-Token": settings.ACTIVE_CAMPAIGN_API_KEY,
        }

        if len(user.name.split(" ")) == 1:
            first_name = user.name
            last_name = ""
        else:
            first_name = user.name.split(" ")[0]
            last_name = user.name.split(" ")[1]

        try:
            payload = {
                "contact": {
                    "firstName": first_name,
                    "lastName": last_name,
                    "email": user.email,
                    "fieldValues": [{"field": "1", "value": user.invite_code}],
                }
            }
            response = requests.post(endpoint, json=payload, headers=headers)
            contact_data = response.json()
            contact_id = contact_data["contact"]["id"]

            # sync the free trial tag
            IAH_FREE_EXPLORER_TAG_ID = 7
            await self.add_tag_to_contact(contact_id, IAH_FREE_EXPLORER_TAG_ID)
            print(
                f"{user.email} has been synced to Active Campaign - status code: {response.status_code}"
            )
        except Exception as e:
            print(e)
            print(f"Failed to sync {user.email} to Active Campaign")

    async def get_new_ac_contact_by_email(self, email: str):
        endpoint = f"{settings.ACTIVE_CAMPAIGN_API_URL}/api/3/contacts?search={email}"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Api-Token": settings.ACTIVE_CAMPAIGN_API_KEY,
        }
        response = requests.get(endpoint, headers=headers)

        if response.status_code == 200:
            payload = response.json()
            return payload
        else:
            return None

    async def add_tag_to_contact(self, contact_id: int, tag_id: int):
        try:
            endpoint = f"{settings.ACTIVE_CAMPAIGN_API_URL}/api/3/contactTags"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "Api-Token": settings.ACTIVE_CAMPAIGN_API_KEY,
            }

            payload = {
                "contactTag": {
                    "contact": contact_id,
                    "tag": tag_id,
                }
            }
            response = requests.post(endpoint, json=payload, headers=headers)
            if response.status_code == 200:
                print(f"Successfully added tag {tag_id} to contact {contact_id}")
        except Exception as e:
            print(f"Failed to add tag {tag_id} to contact {contact_id}")
