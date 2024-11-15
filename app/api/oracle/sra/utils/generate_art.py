import asyncio
import time
from io import BytesIO

import aiohttp
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI as LangChainOpenAI
from PIL import Image

from app.api.oracle.sra.utils.common import load_prompt_from_file_path
from app.common.s3_file_upload import S3FileClient
from app.logger.logger import logger


async def _summary_user_prompt(user_prompt: str) -> str:
    llm = ChatOpenAI(temperature=0.3, model="gpt-4o-mini")
    prompt = load_prompt_from_file_path(
        file_path="../prompts/user_prompt_summary_prompt.yaml"
    )
    chain = RunnableParallel({"user_prompt": RunnablePassthrough()}) | prompt | llm

    return chain.invoke(user_prompt)


async def generate_art(
    user_prompt: str,
    aspect_ratio: str,
    art_style: str,
    art_style_description: str,
) -> str:
    logger.debug(
        f"starting open ai image generation aspect ratio {aspect_ratio} art style {art_style}"
    )
    image_size, resize_resolution = _get_image_size_and_resolution(
        aspect_ratio=aspect_ratio
    )

    summarized_user_prompt = ""

    # check if the user prompt is more than 4000 characters
    if len(user_prompt) > 4000:
        summarized_user_prompt = await _summary_user_prompt(user_prompt)
        logger.debug(
            f"truncated user prompt to 4000 characters: {summarized_user_prompt}"
        )
    else:
        summarized_user_prompt = user_prompt

    image_prompt = f"""
                user prompt: {summarized_user_prompt}
                art style: {art_style}
                art style description: {art_style_description}
                Please generate an image based on the user prompt
            """

    llm = LangChainOpenAI(temperature=0.9)
    prompt = load_prompt_from_file_path(
        file_path="../prompts/image_generation_prompt.yaml"
    )
    chain = RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm

    dalle_wrapper = DallEAPIWrapper(model="dall-e-3", size=image_size)
    image_url = await asyncio.to_thread(dalle_wrapper.run, chain.invoke(image_prompt))

    if resize_resolution:
        image_url_s3 = await _process_and_upload_image(
            image_url=image_url, resize_resolution=resize_resolution
        )
    else:
        s3_client = S3FileClient()
        file_name = f"spectral_resonance_art_{int(time.time())}.png"

        logger.debug(f"uploading image to S3: {file_name}")
        image_url_s3 = await s3_client.upload_image_from_url(
            url=image_url, file_name=file_name, content_type="image/png"
        )
    return image_url_s3


def _get_image_size_and_resolution(aspect_ratio: str) -> tuple[str, str | None]:
    image_size = "1024x1024"
    resize_resolution = None

    if aspect_ratio == "1:1":
        image_size = "1024x1024"
        resize_resolution = None
    elif aspect_ratio == "16:9":
        image_size = "1792x1024"
        resize_resolution = None
    elif aspect_ratio == "3:4":
        image_size = "1024x1792"
        resize_resolution = "1024x1400"
    elif aspect_ratio == "4:3":
        image_size = "1792x1024"
        resize_resolution = "1792x1400"
    elif aspect_ratio == "9:16":
        image_size = "1024x1792"
        resize_resolution = None

    return image_size, resize_resolution


async def _process_and_upload_image(image_url, resize_resolution):
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            content = await response.read()

    img = await asyncio.to_thread(_process_image, BytesIO(content), resize_resolution)

    img_byte_arr = BytesIO()
    await asyncio.to_thread(img.save, img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    file_name = f"spectral_resonance_art_{int(time.time())}.png"
    s3_client = S3FileClient()

    logger.debug(f"processed and uploading image to S3: {file_name}")
    return await asyncio.to_thread(
        s3_client.upload_file_object_to_s3,
        file_name,
        img_byte_arr,
        "image/png",
    )


def _process_image(img_data, resize_resolution):
    with Image.open(img_data) as img:
        target_width, target_height = map(int, resize_resolution.split("x"))
        target_ratio = target_width / target_height
        original_width, original_height = img.size
        original_ratio = original_width / original_height

        if original_ratio > target_ratio:
            new_height = original_height
            new_width = int(target_ratio * new_height)
        else:
            new_width = original_width
            new_height = int(new_width / target_ratio)

        left = (original_width - new_width) // 2
        top = (original_height - new_height) // 2

        return img.crop((left, top, left + new_width, top + new_height))
