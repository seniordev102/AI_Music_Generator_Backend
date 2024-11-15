import json
import os
import tempfile
import warnings
from typing import Dict, Optional, Tuple

import librosa
import numpy as np
import soundfile as sf

from app.logger.logger import logger


class AudioAnalyzerService:
    def __init__(self):
        self.SEGMENT_LENGTH = 10  # seconds
        self.SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

    async def analyze(self, file_content: bytes, file_name: str) -> Dict:
        """Analyze audio file and extract features."""
        temp_file = None
        try:
            # Validate file content
            if not file_content:
                logger.error("Empty file content provided")
                return self._get_error_data("Empty file content")

            logger.debug(f"Received file content of size: {len(file_content)} bytes")

            # Create temp file with proper extension
            file_ext = os.path.splitext(file_name)[1].lower()
            with tempfile.NamedTemporaryFile(
                suffix=file_ext, delete=False, mode="wb"
            ) as temp_file:
                temp_file.write(file_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure all data is written to disk

                temp_file_path = temp_file.name
                logger.debug(
                    f"Created temporary file: {temp_file_path} with size {os.path.getsize(temp_file_path)} bytes"
                )

            # Load audio file
            y, sr = self._load_audio(temp_file_path)
            if y is None or sr is None:
                logger.error(f"Failed to load audio file: {file_name}")
                return self._get_error_data("Failed to load audio file")

            # Calculate duration
            length_sec = librosa.get_duration(y=y, sr=sr)
            logger.debug(f"Audio duration: {length_sec} seconds, Sample rate: {sr}Hz")

            # Initialize result data
            result_data = {
                "audio_features": [],
                "total_duration_seconds": float(length_sec),
                "sample_rate": int(sr),
                "file_format": file_ext[1:],
                "channels": 1 if len(y.shape) == 1 else y.shape[1],
                "error": "",  # Empty error string indicates success
            }

            # Process segments
            segment_count = int(np.ceil(length_sec / self.SEGMENT_LENGTH))
            logger.debug(f"Processing {segment_count} segments")

            for start in range(0, int(length_sec), self.SEGMENT_LENGTH):
                end = min(start + self.SEGMENT_LENGTH, int(length_sec))
                segment = y[int(start * sr) : int(end * sr)]

                features = self._analyze_segment(segment, sr)
                if features:
                    features.update(
                        {"segment_start": int(start), "segment_end": int(end)}
                    )
                    result_data["audio_features"].append(features)

            logger.debug(
                f"Successfully analyzed {len(result_data['audio_features'])} segments"
            )

            # Log the result data before returning
            logger.debug(
                f"Analysis result summary: duration={result_data['total_duration_seconds']}, sample_rate={result_data['sample_rate']}, segments={len(result_data['audio_features'])}"
            )

            return result_data

        except Exception as e:
            logger.error(f"Error in audio analysis: {str(e)}", exc_info=True)
            return self._get_error_data(str(e))

        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                    logger.debug("Cleaned up temporary file")
                except Exception as e:
                    logger.error(f"Error cleaning up temp file: {str(e)}")

    def _load_audio(self, file_path: str) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """Load audio file using multiple backends."""
        logger.debug(f"Attempting to load audio file: {file_path}")

        # First, verify the file
        try:
            file_size = os.path.getsize(file_path)
            logger.debug(f"File size before loading: {file_size} bytes")
            if file_size == 0:
                logger.error("File is empty")
                return None, None
        except Exception as e:
            logger.error(f"Error checking file: {str(e)}")
            return None, None

        try:
            # Try soundfile first
            logger.debug("Attempting to load with soundfile")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                data, sr = sf.read(file_path)
                if len(data.shape) > 1:  # Convert stereo to mono
                    data = np.mean(data, axis=1)
                logger.debug(f"Successfully loaded with soundfile: {sr}Hz")
                return data, sr

        except Exception as sf_error:
            logger.debug(f"Soundfile load failed: {str(sf_error)}")
            try:
                # Fallback to librosa
                logger.debug("Falling back to librosa")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    y, sr = librosa.load(file_path, sr=None, mono=True)
                    if y is not None and sr is not None:
                        logger.debug(f"Successfully loaded with librosa: {sr}Hz")
                        return y, sr
                    else:
                        logger.error("Librosa load returned None values")
                        return None, None

            except Exception as librosa_error:
                logger.error(
                    f"Librosa load failed: {str(librosa_error)}", exc_info=True
                )
                return None, None

    def _analyze_segment(self, segment: np.ndarray, sr: int) -> Optional[Dict]:
        """Analyze a single segment of audio."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                # Basic features
                tempo, _ = librosa.beat.beat_track(y=segment, sr=sr)
                rms = librosa.feature.rms(y=segment)[0]

                # Spectral features
                spectral_centroid = librosa.feature.spectral_centroid(y=segment, sr=sr)[
                    0
                ]
                spectral_bandwidth = librosa.feature.spectral_bandwidth(
                    y=segment, sr=sr
                )[0]
                spectral_rolloff = librosa.feature.spectral_rolloff(y=segment, sr=sr)[0]
                zero_crossing_rate = librosa.feature.zero_crossing_rate(segment)[0]

                return {
                    "tempo": self._to_float(tempo),
                    "mean_rms": self._to_float(np.mean(rms)),
                    "max_rms": self._to_float(np.max(rms)),
                    "spectral_centroid": self._to_float(np.mean(spectral_centroid)),
                    "spectral_bandwidth": self._to_float(np.mean(spectral_bandwidth)),
                    "spectral_rolloff": self._to_float(np.mean(spectral_rolloff)),
                    "zero_crossing_rate": self._to_float(np.mean(zero_crossing_rate)),
                }

        except Exception as e:
            logger.error(f"Error analyzing segment: {str(e)}")
            return None

    def _get_error_data(self, error_message: str) -> Dict:
        """Return a standardized error response."""
        error_data = {
            "error": error_message,
            "audio_features": [],
            "total_duration_seconds": 0,
            "sample_rate": 0,
            "file_format": None,
            "channels": 0,
        }
        logger.debug(f"Returning error data: {error_message}")
        return error_data

    @staticmethod
    def _to_float(value: np.ndarray) -> float:
        """Safely convert numpy value to float."""
        try:
            if isinstance(value, np.ndarray):
                return float(np.mean(value))
            return float(value)
        except Exception:
            return 0.0
