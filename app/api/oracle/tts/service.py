from elevenlabs import ElevenLabs

from app.config import settings
from app.logger.logger import logger


class TextToSpeechService:
    def __init__(self) -> None:
        self.client = ElevenLabs(api_key=settings.ELEVEN_LAB_API_KEY)

    async def generate_audio_stream(self, text: str):
        try:
            audio_stream = self.client.generate(
                text=text,
                voice="XB0fDUnXU5powFXDhCwa",
                stream=True,
                voice_settings={
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0,
                    "use_speaker_boost": True,
                },
                output_format="mp3_44100",
                model="eleven_turbo_v2_5",
                optimize_streaming_latency=3,
            )
            return audio_stream
        except Exception as e:
            logger.error(f"Error generating audio stream: {e}")
            raise
