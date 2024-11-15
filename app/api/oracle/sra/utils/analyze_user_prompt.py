from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_openai import ChatOpenAI

from app.api.oracle.sra.utils.common import (
    get_chat_message_history_by_session_id,
    get_sra_files_by_session_id,
    load_prompt_from_file_path,
)
from app.logger.logger import logger


async def analyze_user_prompt(
    user_prompt: str,
    aspect_ratio: str,
    art_style: str,
    art_style_description: str,
    session_id: str,
    message_id: str,
) -> dict:

    try:

        logger.debug(f"Analyzing user prompt for user prompt {user_prompt}")
        llm = ChatOpenAI(model_name="gpt-4o", temperature=0.2)
        # get chat history for the session
        chat_history = await get_chat_message_history_by_session_id(
            session_id=session_id
        )

        sra_files = await get_sra_files_by_session_id(session_id=session_id)

        context = {
            "input": user_prompt,
            "chat_history": chat_history,
            "sra_files": sra_files,
            "aspect_ratio": aspect_ratio,
            "art_style": art_style,
            "art_style_description": art_style_description,
            "session_id": session_id,
            "message_id": message_id,
        }

        prompt = load_prompt_from_file_path(
            file_path="../prompts/sra_user_input_extract_prompt.yaml"
        )
        request_schema = {
            "name": "analyze_image_request",
            "description": "Analyze the user's image request",
            "parameters": {
                "type": "object",
                "properties": {
                    "is_general_query": {
                        "type": "boolean",
                        "description": "True if the user is asking a general question not related to image generation or editing.",
                    },
                    "is_image_generation": {
                        "type": "boolean",
                        "description": "True if the user is requesting to generate a new image.",
                    },
                    "is_image_variant": {
                        "type": "boolean",
                        "description": "True if the user is requesting a variant of an uploaded image without providing specific details.",
                    },
                    "is_custom_variant": {
                        "type": "boolean",
                        "description": "True if the user is requesting a custom variant of an uploaded image with specific modifications.",
                    },
                    "is_image_edit": {
                        "type": "boolean",
                        "description": "True if the user is requesting to edit a specific portion of an uploaded image (assuming a mask layer is provided).",
                    },
                    "is_image_based_on_uploaded_document": {
                        "type": "boolean",
                        "description": "True if the user is requesting an image based on an uploaded document.",
                    },
                    "is_image_based_on_uploaded_image": {
                        "type": "boolean",
                        "description": "True if the user is requesting an image based on an uploaded image.",
                    },
                    "is_need_more_clarity": {
                        "type": "boolean",
                        "description": "True if the user's request lacks sufficient details about how the image should look.",
                    },
                    "no_of_images": {
                        "type": "integer",
                        "description": "The number of images requested by the user. Default to 1 if not specified.",
                    },
                    "context_usage": {
                        "type": "object",
                        "properties": {
                            "uses_uploaded_image": {"type": "boolean"},
                            "uses_uploaded_document": {"type": "boolean"},
                            "uses_chat_history": {"type": "boolean"},
                        },
                        "description": "Indicates whether the request makes use of uploaded images, documents, or chat history.",
                    },
                },
                "required": [
                    "is_general_query",
                    "is_image_generation",
                    "is_image_variant",
                    "is_custom_variant",
                    "is_image_edit",
                    "is_need_more_clarity",
                    "is_image_based_on_uploaded_document",
                    "no_of_images",
                    "context_usage",
                ],
            },
        }

        output_parser = JsonOutputFunctionsParser()

        chain = prompt | llm.bind(functions=[request_schema]) | output_parser

        result = await chain.ainvoke({"context": context})

        logger.info(f"Analyzed user prompt: {result}")

        return result

    except Exception as e:
        logger.error(f"Error occurred while analyzing image request: {str(e)}")
        return None
