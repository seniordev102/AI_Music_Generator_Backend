import asyncio
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.cost.service import CostPerActionService, CostPerActionType
from app.api.credit_management.service import CreditManagementService
from app.api.oracle.sra.actions.custom_variant_image_gen import (
    generate_custom_variant_of_the_image,
)
from app.api.oracle.sra.actions.doc_based_image_gen import (
    generate_sra_image_based_on_documents,
)
from app.api.oracle.sra.actions.generate_uplifting_message import (
    generate_uplifting_message_based_on_image,
)
from app.api.oracle.sra.actions.image_based_image_gen import (
    generate_sra_image_based_on_uploaded_image,
)
from app.api.oracle.sra.actions.reply_to_user_query import reply_to_user_query
from app.api.oracle.sra.actions.resonance_art_gen import generate_resonance_art
from app.api.oracle.sra.utils.analyze_user_prompt import analyze_user_prompt
from app.api.oracle.sra.utils.common import SRA_CHAT_ERROR, emit_websocket_event
from app.database import db_session
from app.logger.logger import logger


class SRAWebSocketService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        self.cost_per_action_service = CostPerActionService(self.session)
        self.credit_management_service = CreditManagementService(self.session)

    async def response_to_sra_user_query(
        self,
        user_prompt: str,
        aspect_ratio: str,
        art_style: str,
        art_style_description: str,
        session_id: str,
        message_id: str,
        email: str,
        sid: str,
    ):
        try:

            # get cost per action
            cost_per_action = await self.cost_per_action_service.get_cost_per_action(
                CostPerActionType.RESONANCE_ART_QUERY,
            )

            # deduct credits from user
            description = f"SRA query by {email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
            await self.credit_management_service.deduct_credits(
                user_email=email,
                amount=cost_per_action.cost,
                api_endpoint=cost_per_action.endpoint,
                description=description,
            )
            # first send response to the user query
            user_query_task = reply_to_user_query(
                user_prompt=user_prompt,
                session_id=session_id,
                message_id=message_id,
                email=email,
                sid=sid,
            )

            prediction_task = analyze_user_prompt(
                user_prompt=user_prompt,
                aspect_ratio=aspect_ratio,
                art_style=art_style,
                art_style_description=art_style_description,
                session_id=session_id,
                message_id=message_id,
            )

            _, prediction = await asyncio.gather(user_query_task, prediction_task)

            if prediction and prediction.get("is_image_based_on_uploaded_document"):

                logger.debug("Generating image based on uploaded document")

                # get cost per action
                cost_per_action = (
                    await self.cost_per_action_service.get_cost_per_action(
                        CostPerActionType.RESONANCE_ART_IMAGE_GENERATION,
                    )
                )

                # deduct credits from user
                description = f"SRA image generation based on uploaded document by {email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
                await self.credit_management_service.deduct_credits(
                    user_email=email,
                    amount=cost_per_action.cost,
                    api_endpoint=cost_per_action.endpoint,
                    description=description,
                )

                image_url = await generate_sra_image_based_on_documents(
                    session_id=session_id,
                    message_id=message_id,
                    user_prompt=user_prompt,
                    aspect_ratio=aspect_ratio,
                    art_style=art_style,
                    art_style_description=art_style_description,
                    sid=sid,
                )

                await asyncio.sleep(0)

                # generate an uplifting message based on the image
                await generate_uplifting_message_based_on_image(
                    email=email,
                    message_id=message_id,
                    session_id=session_id,
                    image_url=image_url,
                    sid=sid,
                )

                return

            if prediction and prediction.get("is_image_based_on_uploaded_image"):

                logger.debug("Generating image based on uploaded image")

                # get cost per action
                cost_per_action = (
                    await self.cost_per_action_service.get_cost_per_action(
                        CostPerActionType.RESONANCE_ART_IMAGE_GENERATION,
                    )
                )

                # deduct credits from user
                description = f"SRA image generation based on uploaded image by {email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
                await self.credit_management_service.deduct_credits(
                    user_email=email,
                    amount=cost_per_action.cost,
                    api_endpoint=cost_per_action.endpoint,
                    description=description,
                )

                image_url = await generate_sra_image_based_on_uploaded_image(
                    session_id=session_id,
                    message_id=message_id,
                    user_prompt=user_prompt,
                    aspect_ratio=aspect_ratio,
                    art_style=art_style,
                    art_style_description=art_style_description,
                    sid=sid,
                )

                await asyncio.sleep(0)

                # generate an uplifting message based on the image
                await generate_uplifting_message_based_on_image(
                    email=email,
                    message_id=message_id,
                    session_id=session_id,
                    image_url=image_url,
                    sid=sid,
                )

                return

            if prediction and prediction.get("is_image_variant"):

                logger.debug("Generating image variant of the image")

                # get cost per action
                cost_per_action = (
                    await self.cost_per_action_service.get_cost_per_action(
                        CostPerActionType.RESONANCE_ART_IMAGE_GENERATION,
                    )
                )

                # deduct credits from user
                description = f"SRA image generation based on image variant by {email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
                await self.credit_management_service.deduct_credits(
                    user_email=email,
                    amount=cost_per_action.cost,
                    api_endpoint=cost_per_action.endpoint,
                    description=description,
                )

                # sending start event for image generation
                image_url = await generate_custom_variant_of_the_image(
                    session_id=session_id,
                    message_id=message_id,
                    user_prompt=user_prompt,
                    aspect_ratio=aspect_ratio,
                    art_style=art_style,
                    art_style_description=art_style_description,
                    sid=sid,
                )

                await asyncio.sleep(0)

                # generate an uplifting message based on the image
                await generate_uplifting_message_based_on_image(
                    email=email,
                    message_id=message_id,
                    session_id=session_id,
                    image_url=image_url,
                    sid=sid,
                )

                return

            if prediction and prediction.get("is_custom_variant"):

                logger.debug("Generating custom variant of the image")

                # get cost per action
                cost_per_action = (
                    await self.cost_per_action_service.get_cost_per_action(
                        CostPerActionType.RESONANCE_ART_IMAGE_GENERATION,
                    )
                )

                # deduct credits from user
                description = f"SRA image generation based on custom variant by {email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
                await self.credit_management_service.deduct_credits(
                    user_email=email,
                    amount=cost_per_action.cost,
                    api_endpoint=cost_per_action.endpoint,
                    description=description,
                )
                # sending start event for image generation
                image_url = await generate_custom_variant_of_the_image(
                    session_id=session_id,
                    message_id=message_id,
                    user_prompt=user_prompt,
                    aspect_ratio=aspect_ratio,
                    art_style=art_style,
                    art_style_description=art_style_description,
                    sid=sid,
                )

                await asyncio.sleep(0)

                # generate an uplifting message based on the image
                await generate_uplifting_message_based_on_image(
                    email=email,
                    message_id=message_id,
                    session_id=session_id,
                    image_url=image_url,
                    sid=sid,
                )

                return

            if prediction and prediction.get("is_image_generation"):

                logger.debug("Generating resonance art")

                # get cost per action
                cost_per_action = (
                    await self.cost_per_action_service.get_cost_per_action(
                        CostPerActionType.RESONANCE_ART_IMAGE_GENERATION,
                    )
                )

                # deduct credits from user
                description = f"SRA image generation by {email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
                await self.credit_management_service.deduct_credits(
                    user_email=email,
                    amount=cost_per_action.cost,
                    api_endpoint=cost_per_action.endpoint,
                    description=description,
                )

                # sending start event for image generation
                image_url = await generate_resonance_art(
                    session_id=session_id,
                    message_id=message_id,
                    user_prompt=user_prompt,
                    aspect_ratio=aspect_ratio,
                    art_style=art_style,
                    art_style_description=art_style_description,
                    sid=sid,
                )

                await asyncio.sleep(0)

                # generate an uplifting message based on the image
                await generate_uplifting_message_based_on_image(
                    email=email,
                    message_id=message_id,
                    session_id=session_id,
                    image_url=image_url,
                    sid=sid,
                )

                return

        except Exception as e:
            logger.error(f"Error occurred while responding to SRA user query: {str(e)}")
            await emit_websocket_event(
                event_name=SRA_CHAT_ERROR,
                data={
                    "error_code": "general_error",
                    "session_id": session_id,
                    "message_id": message_id,
                    "payload": str(e),
                },
                sid=sid,
            )
