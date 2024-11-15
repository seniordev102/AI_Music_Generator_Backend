import asyncio
import logging
from queue import Queue
from typing import Any, Optional


class WebSocketEmitter:
    def __init__(self, socket_manager):
        self.socket_manager = socket_manager
        self.queue = asyncio.Queue()
        self.logger = logging.getLogger(__name__)

    async def start(self):
        asyncio.create_task(self._process_events())

    async def _process_events(self):
        while True:
            event = await self.queue.get()
            if event is None:  # None is our signal to stop
                break
            await self._emit_event(event["name"], event["payload"], event["sid"])
            self.queue.task_done()

    async def _emit_event(
        self, event_name: str, payload: Any, sid: Optional[str] = None
    ):
        try:
            await self.socket_manager.emit(event=event_name, data=payload, room=sid)
            self.logger.info(f"Emitted event {event_name}")
        except Exception as e:
            self.logger.error(f"Error emitting event {event_name}: {str(e)}")

    async def emit_event(
        self, event_name: str, payload: Any, sid: Optional[str] = None
    ):
        await self.queue.put({"name": event_name, "payload": payload, "sid": sid})
        self.logger.info(f"Queued event {event_name}")

    async def stop(self):
        await self.queue.put(None)
        await self.queue.join()
