from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse

from app.api.oracle.tts.service import TextToSpeechService
from app.common.http_response_model import CommonResponse
from app.logger.logger import logger

router = APIRouter()


@router.get("/generate", name="Generate audio based on provided text")
async def get_tracks(
    response: Response,
    text: str = Query(),
):

    try:
        tts_service = TextToSpeechService()
        audio_stream = await tts_service.generate_audio_stream(text=text)

        def audio_generator():
            try:
                for chunk in audio_stream:
                    yield chunk
            except Exception as e:
                logger.error(f"Error streaming audio: {e}")

        return StreamingResponse(
            audio_generator(),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
