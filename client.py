from abc import ABC, abstractmethod
import asyncio
from typing import Literal, Optional, TypedDict
from pygame import Rect, Vector2
from draw import RenderState
from logic import BoardState, MoveKind
from protocol import (
    ClientInterface,
    InitMessage,
    ServerInterface,
    ServerMessage,
)

type InputEvent = Drag | DragDrop | Click


class DragStart(TypedDict):
    kind: Literal["drag_start"]
    pos: Vector2


class Drag(TypedDict):
    kind: Literal["drag"]
    delta: Vector2


class DragDrop(TypedDict):
    kind: Literal["drag_drop"]


class Click(TypedDict):
    kind: Literal["click"]
    pos: Vector2


type Interaction = Dragging | Selected


class Dragging(TypedDict):
    kind: Literal["dragging"]
    piece_index: int


class Selected(TypedDict):
    kind: Literal["selected"]
    piece_index: int


type Clickable = Piece | MoveIndicator


class Piece(TypedDict):
    kind: Literal["piece"]
    hitbox: Rect
    draggable: Literal[True]
    index: int


class MoveIndicator(TypedDict):
    kind: Literal["move_indicator"]
    hitbox: Rect
    draggable: Literal[False]
    move: MoveKind


class TurnPhase(ABC):
    @abstractmethod
    async def next_phase(
        self, client: LocalClient, server: ServerInterface
    ) -> Optional[TurnPhase]:
        pass


class MyTurn(TurnPhase):
    board_state: BoardState
    active_interaction: Optional[Interaction]
    selectables: list[Clickable]

    async def next_phase(
        self, client: LocalClient, _server: ServerInterface
    ) -> Optional[TurnPhase]:
        # Flush input events so we don't eat stale events
        while not client.input_events.empty():
            client.input_events.get_nowait()
        # We're waiting for:
        # - A drag start -> set active interaction to dragging, listen for drag/drag drop events
        # - A click -> set active interaction to selected, spawn move options, listen for click events
        return Animating()


class Animating(TurnPhase):
    async def next_phase(
        self, _client: LocalClient, _server: ServerInterface
    ) -> Optional[TurnPhase]:
        # Push client states until animation is complete.
        return WaitOpponent()


class WaitOpponent(TurnPhase):
    async def next_phase(
        self, _client: LocalClient, _server: ServerInterface
    ) -> Optional[TurnPhase]:
        # Wait for opponent move messages, push client states as needed.
        return MyTurn()


class LocalClient(ClientInterface):
    messages: asyncio.Queue[ServerMessage]
    render_state: asyncio.Queue[RenderState]
    input_events: asyncio.Queue[InputEvent]

    def __init__(self) -> None:
        self.messages = asyncio.Queue()
        self.render_state = asyncio.Queue()
        self.input_events = asyncio.Queue()

    async def start(self, server: ServerInterface) -> None:
        init_message = await self.get_init_message()
        phase: Optional[TurnPhase] = (
            MyTurn() if init_message["player_allegiance"] == "red" else WaitOpponent()
        )
        while phase is not None:
            phase = await phase.next_phase(self, server)

    async def get_init_message(self) -> InitMessage:
        while True:
            message = await self.messages.get()
            if message["kind"] == "init":
                return message
            else:
                print(f"Waiting for init message, got {message}")

    # Here we handle messages from the server. For remote clients, this would be where we send
    # messages over the network.
    async def send(self, message: ServerMessage) -> None:
        self.messages.put_nowait(message)
