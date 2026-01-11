"""EventForwarder - Bridge events from adapter to external sender.

This utility simplifies integration with existing systems like FastAPI
WebSocket handlers by consuming events from a QueueAdapter and forwarding
them through a custom sender function.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    from .adapters.queue import QueueAdapter
    from .schema import UIEvent

logger = logging.getLogger(__name__)


class EventForwarder:
    """Forward events from a QueueAdapter to an external sender.
    
    This is useful when integrating hooks-ui-bridge with existing
    server infrastructure (e.g., FastAPI WebSocket endpoints).
    
    Example:
        # In amplifier-desktop sidecar
        from amplifier_module_hooks_ui_bridge import UIBridge, QueueAdapter, EventForwarder
        
        bridge = UIBridge(config={"event_mode": "native"})
        adapter = QueueAdapter()
        bridge.set_adapter(adapter)
        
        # In WebSocket handler
        async def send_to_client(event_dict: dict):
            event_dict["conversationId"] = conversation_id
            await websocket.send_json(event_dict)
        
        forwarder = EventForwarder(adapter, send_to_client)
        task = asyncio.create_task(forwarder.run())
        
        # When done
        forwarder.stop()
        await task
    
    Attributes:
        adapter: The QueueAdapter to consume events from
        sender: Async function that sends event dict to destination
        transform: Optional function to transform event dict before sending
    """
    
    def __init__(
        self,
        adapter: QueueAdapter,
        sender: Callable[[dict[str, Any]], Awaitable[None]],
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        """Initialize the forwarder.
        
        Args:
            adapter: QueueAdapter to consume events from
            sender: Async function to send event dicts (e.g., websocket.send_json)
            transform: Optional sync function to transform event dict before sending
                      (e.g., add conversationId, rename fields)
        """
        self.adapter = adapter
        self.sender = sender
        self.transform = transform
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def run(self) -> None:
        """Start consuming events and forwarding them.
        
        This runs until stop() is called or the adapter is closed.
        Typically run as a background task: asyncio.create_task(forwarder.run())
        """
        self._running = True
        logger.debug("EventForwarder started")
        
        try:
            while self._running:
                try:
                    # Get event from adapter's queue with timeout
                    # Timeout allows checking _running flag periodically
                    event = await asyncio.wait_for(
                        self.adapter.event_queue.get(),
                        timeout=0.5
                    )
                    
                    # Convert to dict
                    event_dict = event.to_dict()
                    
                    # Apply transform if provided
                    if self.transform:
                        event_dict = self.transform(event_dict)
                    
                    # Send through sender
                    await self.sender(event_dict)
                    
                except asyncio.TimeoutError:
                    # Check if we should stop
                    continue
                except asyncio.CancelledError:
                    logger.debug("EventForwarder cancelled")
                    break
                except Exception as e:
                    logger.error(f"EventForwarder error: {e}")
                    # Continue running despite errors
                    
        finally:
            self._running = False
            logger.debug("EventForwarder stopped")
    
    def stop(self) -> None:
        """Signal the forwarder to stop.
        
        After calling stop(), the run() loop will exit on its next iteration.
        """
        self._running = False
    
    @property
    def is_running(self) -> bool:
        """Check if the forwarder is currently running."""
        return self._running


class BatchEventForwarder(EventForwarder):
    """Forward events in batches for improved efficiency.
    
    Collects events for a short duration before sending them all at once.
    Useful when the transport benefits from batching (e.g., reducing WebSocket frames).
    
    Example:
        forwarder = BatchEventForwarder(
            adapter,
            sender=websocket.send_json,
            batch_size=10,
            batch_timeout=0.05  # 50ms
        )
    """
    
    def __init__(
        self,
        adapter: QueueAdapter,
        sender: Callable[[dict[str, Any]], Awaitable[None]],
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        batch_size: int = 10,
        batch_timeout: float = 0.05,
    ):
        """Initialize the batch forwarder.
        
        Args:
            adapter: QueueAdapter to consume events from
            sender: Async function to send event dicts
            transform: Optional function to transform each event dict
            batch_size: Max events per batch before sending
            batch_timeout: Max time (seconds) to wait before sending partial batch
        """
        super().__init__(adapter, sender, transform)
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
    
    async def run(self) -> None:
        """Start consuming events and forwarding them in batches."""
        self._running = True
        logger.debug("BatchEventForwarder started")
        batch: list[dict[str, Any]] = []
        last_send = asyncio.get_event_loop().time()
        
        try:
            while self._running:
                try:
                    # Short timeout to enable batching
                    event = await asyncio.wait_for(
                        self.adapter.event_queue.get(),
                        timeout=self.batch_timeout
                    )
                    
                    event_dict = event.to_dict()
                    if self.transform:
                        event_dict = self.transform(event_dict)
                    
                    batch.append(event_dict)
                    
                    # Send if batch is full
                    if len(batch) >= self.batch_size:
                        await self._send_batch(batch)
                        batch = []
                        last_send = asyncio.get_event_loop().time()
                        
                except asyncio.TimeoutError:
                    # Send partial batch if timeout elapsed
                    now = asyncio.get_event_loop().time()
                    if batch and (now - last_send) >= self.batch_timeout:
                        await self._send_batch(batch)
                        batch = []
                        last_send = now
                except asyncio.CancelledError:
                    # Send remaining batch before exiting
                    if batch:
                        await self._send_batch(batch)
                    break
                except Exception as e:
                    logger.error(f"BatchEventForwarder error: {e}")
                    
        finally:
            # Send any remaining events
            if batch:
                try:
                    await self._send_batch(batch)
                except Exception:
                    pass
            self._running = False
            logger.debug("BatchEventForwarder stopped")
    
    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        """Send a batch of events."""
        for event_dict in batch:
            await self.sender(event_dict)
