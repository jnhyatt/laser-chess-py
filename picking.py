import asyncio
from typing import AsyncGenerator, Literal, NoReturn, TypedDict
from pygame import Vector2
import pygame


class Picker:
    _down: asyncio.Queue[Vector2] = asyncio.Queue()
    _move: asyncio.Queue[Vector2] = asyncio.Queue()
    _up: asyncio.Queue[Vector2] = asyncio.Queue()

    async def next_click(self) -> Vector2:
        async def next_cancel(down_at: Vector2) -> CancelClick:
            while True:
                if (await self._move.get() - down_at).length() > 5:
                    return {"type": "cancel"}

        async def next_up() -> FinishClick:
            return {"type": "up", "pos": await self._up.get()}

        while True:
            while not self._down.empty():
                self._down.get_nowait()

            down_at = await self._down.get()

            while not self._move.empty():
                self._move.get_nowait()
            cancel_task: asyncio.Task[PendingClickEvent] = asyncio.create_task(
                next_cancel(down_at)
            )

            while not self._up.empty():
                self._up.get_nowait()
            up_task: asyncio.Task[PendingClickEvent] = asyncio.create_task(next_up())

            done, pending = await asyncio.wait(
                [cancel_task, up_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            result = done.pop().result()
            if result["type"] == "up":
                return result["pos"]

    def on_event(self, event: pygame.event.Event) -> None:
        match event.type:
            case pygame.constants.MOUSEBUTTONDOWN if event.button == 1:
                self._down.put_nowait(Vector2(event.pos))
            case pygame.constants.MOUSEMOTION:
                self._move.put_nowait(Vector2(event.pos))
            case pygame.constants.MOUSEBUTTONUP if event.button == 1:
                self._up.put_nowait(Vector2(event.pos))


class FinishClick(TypedDict):
    type: Literal["up"]
    pos: Vector2


class CancelClick(TypedDict):
    type: Literal["cancel"]


type PendingClickEvent = FinishClick | CancelClick
