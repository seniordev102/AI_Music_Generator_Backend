import asyncio

from langchain.schema.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.api.oracle.sra.utils.common import (
    SRA_IMAGE_GENERATION_END,
    SRA_IMAGE_GENERATION_ERROR,
    SRA_IMAGE_GENERATION_START,
    emit_websocket_event,
    get_most_recent_sra_document,
    save_generated_image_to_db,
)
from app.api.oracle.sra.utils.generate_art import generate_art
from app.logger.logger import logger


async def generate_sra_image_based_on_uploaded_image(
    session_id: str,
    message_id: str,
    user_prompt: str,
    aspect_ratio: str,
    art_style: str,
    art_style_description: str,
    sid: str,
):

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
    recent_uploaded_document = await get_most_recent_sra_document(session_id=session_id)
    if recent_uploaded_document is None:
        await emit_websocket_event(
            event_name=SRA_IMAGE_GENERATION_ERROR,
            data={
                "error_code": "general_error",
                "session_id": session_id,
                "message_id": message_id,
                "payload": "Sorry, we couldn't find any reference document to generate a custom variant",
            },
            sid=sid,
        )

    else:
        # check if the document type is an image type
        if recent_uploaded_document.file_type.lower().startswith("image"):

            # describe the image using open api
            chat = ChatOpenAI(model="gpt-4o", temperature=0.1)
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"Describe this image a prompt to generate a similar image like this please only provide a prompt {user_prompt}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": recent_uploaded_document.file_url},
                    },
                ]
            )
            response = chat.invoke([message])
            image_prompt = response.content

            # generate the image based on the prompt
            new_image = await generate_art(
                user_prompt=image_prompt,
                aspect_ratio=aspect_ratio,
                art_style=art_style,
                art_style_description=art_style_description,
            )

            # save the generated image to the database
            await save_generated_image_to_db(
                session_id=session_id,
                message_id=message_id,
                image_url_s3=new_image,
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

        else:
            await emit_websocket_event(
                event_name=SRA_IMAGE_GENERATION_ERROR,
                data={
                    "error_code": "general_error",
                    "session_id": session_id,
                    "message_id": message_id,
                    "payload": "Sorry, we couldn't find any reference images to generate a custom variant make sure image format is jpg, jpeg, png",
                },
                sid=sid,
            )
            return
