import asyncio

from langchain.schema.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.api.oracle.sra.utils.common import (
    SRA_IMAGE_GENERATION_END,
    SRA_IMAGE_GENERATION_ERROR,
    SRA_IMAGE_GENERATION_START,
    emit_websocket_event,
    get_recent_generate_image_by_session_id,
    save_generated_image_to_db,
)
from app.api.oracle.sra.utils.generate_art import generate_art
from app.logger.logger import logger


async def generate_custom_variant_of_the_image(
    session_id: str,
    message_id: str,
    user_prompt: str,
    aspect_ratio: str,
    art_style: str,
    art_style_description: str,
    sid: str,
):
    try:
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_START,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": True,
            },
            sid=sid,
        )

        # Allow the event loop to process the emit
        await asyncio.sleep(0)

        # fetch the most recent chat by session and find the image url
        latest_generated_image = await get_recent_generate_image_by_session_id(
            session_id=session_id
        )

        if latest_generated_image is None:
            await emit_websocket_event(
                event_name=SRA_IMAGE_GENERATION_ERROR,
                data={
                    "error_code": "general_error",
                    "session_id": session_id,
                    "message_id": message_id,
                    "payload": "Sorry, we couldn't find any image to generate a custom variant",
                },
                sid=sid,
            )
        else:
            chat = ChatOpenAI(model="gpt-4o", temperature=0.1)
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"Describe this image a prompt to generate a similar image but with this user requested modification {user_prompt}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": latest_generated_image},
                    },
                ]
            )
            response = chat.invoke([message])

            new_prompt = response.content
            # describe the image and get the prompt
            new_image = await generate_art(
                user_prompt=new_prompt,
                aspect_ratio=aspect_ratio,
                art_style=art_style,
                art_style_description=art_style_description,
            )

            # save the generated image to the database
            await save_generated_image_to_db(
                session_id=session_id, message_id=message_id, image_url_s3=new_image
            )

            await emit_websocket_event(
                event_name=SRA_IMAGE_GENERATION_END,
                data={
                    "session_id": session_id,
                    "message_id": message_id,
                    "payload": new_image,
                },
                sid=sid,
            )

            return new_image

    except Exception as e:
        logger.error(f"Error occurred while generating custom variant: {str(e)}")
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
