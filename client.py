from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Literal, Optional, TypedDict
from pygame import Rect, Vector2
import pygame
from draw import Drawable, MoveIndicatorDrawable, PieceDrawable, RenderState
from logic import Allegiance, BoardState, Move, MoveDir, MoveKind, Piece, add_dir
from picking import Picker
from protocol import (
    ClientInterface,
    ClientMessage,
    InitMessage,
    MoveMessage,
    OpponentMove,
    ServerInterface,
    ServerMessage,
)

type InputEvent = Click


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


@dataclass
class Selected:
    index: int


class TurnPhase(ABC):
    @abstractmethod
    async def next_phase(
        self, client: LocalClient, server: ServerInterface
    ) -> Optional[TurnPhase]:
        pass


@dataclass
class MyTurn(TurnPhase):
    board_state: BoardState
    allegiance: Allegiance

    async def next_phase(
        self, client: LocalClient, server: ServerInterface
    ) -> Optional[TurnPhase]:
        selected: Optional[Selected] = None
        print("Pushing render state")
        await client.render_state.put(
            [drawable_for(piece) for piece in self.board_state]
        )
        while True:
            click = await client.picker.next_click()
            if selected is not None:
                # Check if we clicked on a move option, and if so, make the move.
                options: set[MoveDir] = {"n", "ne", "e"}
                # TODO also check rotation, probably split the cell into left and right halves
                clicked_move: Optional[MoveDir] = next(
                    (
                        move
                        for move in options
                        if Rect(
                            add_dir(self.board_state[selected.index].position, move)
                            * 90
                            + Vector2(190, 0),
                            (90, 90),
                        ).collidepoint(click)
                    ),
                    None,
                )
                print(f"Clicked move {clicked_move} for piece {selected.index}")
                if clicked_move is not None:
                    await server.send(
                        MoveMessage(
                            Move(
                                self.board_state[selected.index].position, clicked_move
                            )
                        )
                    )
                    await client.render_state.put(
                        [drawable_for(piece) for piece in self.board_state]
                    )
                    break

            # Now check if we clicked on a piece, and if so, select it and show move options.
            hit_index = next(
                (
                    index
                    for index, piece in enumerate(self.board_state)
                    if Rect(
                        piece.position * 90 + Vector2(235, 45) - Vector2(45, 45),
                        (90, 90),
                    ).collidepoint(click)
                ),
                None,
            )
            print(f"Hit index: {hit_index}")
            if (
                hit_index is not None
                and self.allegiance == self.board_state[hit_index].allegiance
            ):
                if hit_index == (selected.index if selected is not None else None):
                    selected = None
                    await client.render_state.put(
                        [drawable_for(piece) for piece in self.board_state]
                    )
                    continue
                selected = Selected(hit_index)
                move_options: set[MoveKind] = {"n", "ne", "e"}
                render_state: list[Drawable] = [
                    drawable_for(piece) for piece in self.board_state
                ]
                render_state.extend(
                    [
                        MoveIndicatorDrawable(self.board_state[hit_index], move)
                        for move in move_options
                    ]
                )
                await client.render_state.put(render_state)
                selected = Selected(hit_index)
        return Animating()


class Animating(TurnPhase):
    async def next_phase(
        self, _client: LocalClient, _server: ServerInterface
    ) -> Optional[TurnPhase]:
        # Push client states until animation is complete.
        return WaitOpponent()


class WaitOpponent(TurnPhase):
    async def next_phase(
        self, client: LocalClient, _server: ServerInterface
    ) -> Optional[TurnPhase]:
        # Wait for opponent move messages, push client states as needed.
        while True:
            server_message = await client.messages.get()
            if isinstance(server_message, OpponentMove):
                print(f"Opponent move: {server_message.move}")
                break
            else:
                print(f"Waiting for opponent move, got {server_message}")
        raise NotImplementedError()


class LocalClient(ClientInterface):
    messages: asyncio.Queue[ServerMessage]
    render_state: asyncio.Queue[RenderState]
    picker: Picker
    # input_events: asyncio.Queue[InputEvent]

    def __init__(self) -> None:
        self.messages = asyncio.Queue()
        self.render_state = asyncio.Queue()
        self.picker = Picker()

    async def start(self, server: ServerInterface) -> None:
        init_message = await self.get_init_message()
        phase: Optional[TurnPhase] = (
            MyTurn(init_message.state, init_message.player_allegiance)
            if init_message.player_allegiance == "red"
            else WaitOpponent()
        )
        while phase is not None:
            phase = await phase.next_phase(self, server)

    async def get_init_message(self) -> InitMessage:
        while True:
            message = await self.messages.get()
            if isinstance(message, InitMessage):
                return message
            else:
                print(f"Waiting for init message, got {message}")

    # Here we handle messages from the server. For remote clients, this would be where we send
    # messages over the network.
    async def send(self, message: ServerMessage) -> None:
        self.messages.put_nowait(message)

    def on_event(self, event: pygame.event.Event) -> None:
        self.picker.on_event(event)


def drawable_for(piece: Piece) -> PieceDrawable:
    return PieceDrawable(
        piece.kind, piece.position * 90 + Vector2(235, 45), 0, piece.allegiance
    )
