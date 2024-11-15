import uuid

from langchain.schema.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.api.oracle.sra.utils.common import (
    SRA_CHAT_END,
    SRA_CHAT_ERROR,
    SRA_CHAT_RESPONSE,
    SRA_NEW_CHAT_START,
    emit_websocket_event,
    load_prompt_from_file_path,
    save_sra_chat_response_to_db,
)
from app.logger.logger import logger


async def generate_uplifting_message_based_on_image(
    email: str,
    session_id: str,
    message_id: str,
    image_url: str,
    sid: str,
):
    try:

        logger.debug("Generating uplifting message based on image")
        # send start event
        await emit_websocket_event(
            event_name=SRA_NEW_CHAT_START,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": True,
            },
            sid=sid,
        )

        # load iah system prompt
        loaded_prompt = load_prompt_from_file_path(
            file_path="../prompts/sra_iah_system_prompt.yaml"
        )

        system_message = SystemMessage(content=loaded_prompt.template)

        chat = ChatOpenAI(model="gpt-4o", temperature=0.3, streaming=True)
        human_message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"""
                    Using provided image generate an empowering positive message to the user, 
                    when generating the message consider the system prompt and provided image details as well,
                    Please don't include quotes in the response message.
                    """,
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
            ]
        )

        message = [system_message, human_message]

        full_response = ""
        async for chunk in chat.astream(message):
            if chunk.content:
                full_response += chunk.content
                # send streaming response event
                await emit_websocket_event(
                    event_name=SRA_CHAT_RESPONSE,
                    data={
                        "session_id": session_id,
                        "message_id": message_id,
                        "payload": chunk.content,
                    },
                    sid=sid,
                )

        # send end event
        await emit_websocket_event(
            event_name=SRA_CHAT_END,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "payload": False,
            },
            sid=sid,
        )

        # Save the complete response to the database
        await save_sra_chat_response_to_db(
            email=email,
            session_id=session_id,
            message_id=message_id,
            response=full_response,
        )

    except Exception as e:
        logger.error(f"Error occurred while generating SRA uplifting message: {str(e)}")

        # send error event
        await emit_websocket_event(
            event_name=SRA_CHAT_ERROR,
            data={
                "error_code": "general_error",
                "session_id": session_id,
                "message_id": message_id,
                "payload": "Something went wrong while processing your request please try again",
            },
            sid=sid,
        )
