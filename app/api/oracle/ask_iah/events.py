from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventType(Enum):
    MESSAGE = "message"
    COMPLETE = "complete"
    ERROR = "error"
    METADATA = "metadata"
    PROCESSING = "processing"


@dataclass
class StreamEvent:
    event_type: EventType
    data: dict

    def to_dict(self) -> dict:
        return {"event": self.event_type.value, "data": self.data}


class EventEmitter:
    @staticmethod
    def message(content: str, session_id: str, message_id: str) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.MESSAGE,
            data={
                "content": content,
                "session_id": session_id,
                "message_id": message_id,
            },
        )

    @staticmethod
    def complete(session_id: str, message_id: str) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.COMPLETE,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "status": "completed",
            },
        )

    @staticmethod
    def error(
        error: str, session_id: str, message_id: str, error_code: Optional[str]
    ) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.ERROR,
            data={
                "error": error,
                "session_id": session_id,
                "message_id": message_id,
                "error_code": error_code,
            },
        )

    @staticmethod
    def metadata(metadata: dict, session_id: str, message_id: str) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.METADATA,
            data={
                "metadata": metadata,
                "session_id": session_id,
                "message_id": message_id,
            },
        )

    @staticmethod
    def processing(
        message: str, session_id: str, message_id: str, is_processing: bool
    ) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.PROCESSING,
            data={
                "message": message,
                "session_id": session_id,
                "message_id": message_id,
                "is_processing": is_processing,
            },
        )
