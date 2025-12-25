"""Tauri IPC adapter for desktop/mobile sidecar communication.

This adapter uses stdin/stdout JSON lines for communication with
Tauri 2.0 applications. Events are written to stdout, commands
are read from stdin.

Tauri sidecar setup (Rust):
    let sidecar = app.shell().sidecar("amplifier")?;
    let (mut rx, child) = sidecar.spawn()?;
    
    // Read events from stdout
    while let Some(event) = rx.recv().await {
        if let CommandEvent::Stdout(line) = event {
            let ui_event: UIEvent = serde_json::from_str(&line)?;
            app.emit("amplifier-event", ui_event)?;
        }
    }
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import TYPE_CHECKING, AsyncIterator

from .base import UIAdapter

if TYPE_CHECKING:
    from ..schema import UICommand, UIEvent


class TauriIPCAdapter(UIAdapter):
    """Adapter for Tauri 2.0 sidecar communication via stdin/stdout.
    
    Events are written to stdout as JSON lines (one JSON object per line).
    Commands are read from stdin as JSON lines.
    
    This allows Tauri to spawn the Python process as a sidecar and
    communicate via standard I/O pipes.
    
    Usage:
        # In profile.toml
        [hooks.config.transport]
        type = "tauri"
    
    Attributes:
        _running: Whether the adapter is active
        _reader_task: Background task reading stdin
    """
    
    def __init__(self):
        """Initialize the Tauri IPC adapter."""
        self._running = False
        self._reader_task: asyncio.Task | None = None
        self._command_queue: asyncio.Queue[UICommand] = asyncio.Queue()
    
    async def connect(self) -> None:
        """Start listening for commands on stdin."""
        self._running = True
        self._reader_task = asyncio.create_task(self._read_stdin())
    
    async def disconnect(self) -> None:
        """Stop listening and clean up."""
        self._running = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
    
    async def emit(self, event: UIEvent) -> None:
        """Write event to stdout as JSON line.
        
        Tauri reads this from the sidecar's stdout.
        
        Args:
            event: UIEvent to emit
        """
        line = event.to_json()
        # Write to stdout with newline, flush immediately
        print(line, flush=True)
    
    async def receive(self) -> AsyncIterator[UICommand]:
        """Receive commands from stdin.
        
        Yields:
            UICommand objects as they arrive from Tauri
        """
        while self._running:
            try:
                command = await asyncio.wait_for(
                    self._command_queue.get(),
                    timeout=0.1
                )
                yield command
            except asyncio.TimeoutError:
                continue
    
    async def _read_stdin(self) -> None:
        """Background task to read commands from stdin."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        
        try:
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        except (OSError, NotImplementedError):
            # stdin may not be available in some contexts
            return
        
        while self._running:
            try:
                line = await reader.readline()
                if not line:
                    # EOF
                    break
                
                line_str = line.decode().strip()
                if not line_str:
                    continue
                
                try:
                    data = json.loads(line_str)
                    from ..schema import UICommand
                    command = UICommand.from_dict(data)
                    await self._command_queue.put(command)
                except json.JSONDecodeError:
                    # Invalid JSON, skip
                    continue
                except Exception:
                    # Other parsing errors, skip
                    continue
                    
            except asyncio.CancelledError:
                break
            except Exception:
                # Don't crash on read errors
                continue
    
    async def emit_batch(self, events: list[UIEvent]) -> None:
        """Write multiple events efficiently.
        
        For Tauri, we still write line by line but minimize flush calls.
        
        Args:
            events: List of UIEvents to emit
        """
        lines = [event.to_json() for event in events]
        output = "\n".join(lines) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
