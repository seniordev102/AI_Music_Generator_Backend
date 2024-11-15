import asyncio

from app.api.oracle.sra.utils.common import (
    SRA_IMAGE_GENERATION_END,
    SRA_IMAGE_GENERATION_ERROR,
    SRA_IMAGE_GENERATION_START,
    emit_websocket_event,
    save_generated_image_to_db,
)
from app.api.oracle.sra.utils.generate_art import generate_art
from app.logger.logger import logger


async def generate_resonance_art(
    session_id: str,
    message_id: str,
    user_prompt: str,
    aspect_ratio: str,
    art_style: str,
    art_style_description: str,
    sid: str,
):
    try:
        # send start event
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_START,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": True,
            },
            sid=sid,
        )

        # adding delay to allow the start event to be sent
        await asyncio.sleep(0)

        # generating the art
        image_url = await generate_art(
            user_prompt=user_prompt,
            aspect_ratio=aspect_ratio,
            art_style=art_style,
            art_style_description=art_style_description,
        )

        # save the generated image to the database
        await save_generated_image_to_db(
            session_id=session_id, message_id=message_id, image_url_s3=image_url
        )

        # send end event
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_END,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": image_url,
            },
            sid=sid,
        )

        return image_url

    except Exception as e:
        logger.error(f"Error occurred while generating resonance art: {str(e)}")

        # send error event
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_ERROR,
            data={
                "error_code": "general_error",
                "session_id": session_id,
                "message_id": message_id,
                "payload": "Something went wrong while processing your request please try again",
            },
            sid=sid,
        )
