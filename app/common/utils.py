import io

from PIL import Image


async def resize_image(
    file_content: bytes, file_name: str, file_content_type: str, height: int, width: int
):

    # Open the image using Pillow
    image_stream = io.BytesIO(file_content)
    pillow_image = Image.open(image_stream)
    pillow_image.thumbnail((height, width))

    image_byte_array = io.BytesIO()
    pillow_image.save(image_byte_array, format="png", optimize=True, quality=80)
    image_bytes = image_byte_array.getvalue()
    new_file_name = f"{file_name.split('.')[0]}_thumbnail.png"

    return {
        "image_content": image_bytes,
        "file_name": new_file_name,
        "file_content_type": file_content_type,
    }


# async def resize_image(
#         upload_file: UploadFile,
#         height: int,
#         width: int
#     ) -> StarletteUploadFile:

#     upload_file.file.seek(0)
#     file_content = await upload_file.read()
#     # Open the image using Pillow
#     image_stream = io.BytesIO(file_content)
#     pillow_image = Image.open(image_stream)
#     pillow_image.thumbnail((height, width))

#     image_byte_array = io.BytesIO()
#     pillow_image.save(image_byte_array, format='png', optimize=True, quality=80)
#     # image_bytes = image_byte_array.getvalue()
#     new_file_name = f"{upload_file.filename.split('.')[0]}_thumbnail.png"

#     new_upload_file = StarletteUploadFile(
#         filename=new_file_name,
#         file=image_byte_array, # You might want to use 'image/png' since you're saving it as PNG
#     )

#     return new_upload_file
