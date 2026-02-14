from abc import ABC, abstractmethod
import asyncio
import copy
from dataclasses import dataclass
import itertools
from typing import Literal, Optional
from pygame import Rect, Vector2
import pygame
from draw import (
    Drawable,
    GameOverDrawable,
    LaserDrawable,
    MoveIndicatorDrawable,
    PieceDrawable,
    RenderState,
    TurnIndicatorDrawable,
)
from logic import (
    Allegiance,
    BoardState,
    Move,
    MoveKind,
    Piece,
    PieceKind,
    add_dir,
    fire_laser,
    move_options,
    opponent,
    update_state,
    winner,
)
from picking import Picker
from protocol import ClientInterface, ServerInterface


@dataclass
class InitInfo:
    player_allegiance: Allegiance
    opponent_name: str


type SoundEffect = Literal["laser_fire", "mirror_hit"]


class LocalClient(ClientInterface):
    init_info: asyncio.Queue[InitInfo] = asyncio.Queue()
    opponent_moves: asyncio.Queue[Move] = asyncio.Queue()

    async def send_init(
        self, player_allegiance: Allegiance, opponent_name: str
    ) -> None:
        self.init_info.put_nowait(InitInfo(player_allegiance, opponent_name))

    async def send_opponent_move(self, move: Move) -> None:
        self.opponent_moves.put_nowait(move)


@dataclass
class Selected:
    index: int


class TurnPhase(ABC):
    @abstractmethod
    async def next_phase(
        self, presenter: GamePresenter, server: ServerInterface
    ) -> Optional[TurnPhase]:
        pass


@dataclass
class MyTurn(TurnPhase):
    board_state: BoardState
    allegiance: Allegiance

    async def next_phase(
        self, presenter: GamePresenter, server: ServerInterface
    ) -> Optional[TurnPhase]:
        selected: Optional[Selected] = None
        await presenter.render_state.put(
            generate_render_state(self.board_state, None, self.allegiance)
        )
        while True:
            click = await presenter.picker.next_click()
            if selected is not None:
                piece = self.board_state[selected.index]
                options = move_options(piece, self.board_state)
                clicked_move = next(
                    (
                        m
                        for m in options
                        if move_hitbox(piece.position, m).collidepoint(click)
                    ),
                    None,
                )
                if clicked_move is not None:
                    # Snapshot state before sending -- server mutates the shared objects
                    anim_state = copy.deepcopy(self.board_state)
                    update_state(
                        anim_state, Move(piece.position, clicked_move), self.allegiance
                    )
                    await server.send_move(Move(piece.position, clicked_move))
                    return Animating(anim_state, self.allegiance)
                hit_index = _hit_test_own_piece(
                    click, self.board_state, self.allegiance
                )
                if hit_index is not None:
                    selected = Selected(hit_index)
                    await presenter.render_state.put(
                        generate_render_state(
                            self.board_state, selected.index, self.allegiance
                        )
                    )
                    # await _push_selected_state(presenter, self.board_state, hit_index)
                continue

            hit_index = _hit_test_own_piece(click, self.board_state, self.allegiance)
            if hit_index is not None:
                selected = Selected(hit_index)
                await presenter.render_state.put(
                    generate_render_state(self.board_state, hit_index, self.allegiance)
                )
                # await _push_selected_state(presenter, self.board_state, hit_index)


@dataclass
class Animating(TurnPhase):
    board_state: BoardState
    allegiance: Allegiance  # The player who just moved

    async def next_phase(
        self, presenter: GamePresenter, server: ServerInterface
    ) -> Optional[TurnPhase]:
        # Compute laser path from the post-move board state (before server removes the hit piece)
        laser_result = fire_laser(self.allegiance, self.board_state)
        # Build the intermediate render state: the moved board (pre-removal)
        base_drawables: list[Drawable] = [drawable_for(p) for p in self.board_state]

        # Calculate total path length in pixels for speed-based animation
        pairs = list(itertools.pairwise(laser_result.path))
        total_dist_cells = sum(a.distance_to(b) for a, b in pairs) if pairs else 0
        total_dist_px = total_dist_cells * 90  # cells to pixels
        duration = total_dist_px / 720  # 720 pixels/sec

        # Compute progress values at each interior path point (mirror bounces).
        # Path points: [origin, bounce1, bounce2, ..., terminal]
        # Interior points at indices 1..len-2 are mirror hits.
        bounce_progresses: list[float] = []
        if total_dist_cells > 0 and len(laser_result.path) > 2:
            cumulative = 0.0
            for a, b in pairs[:-1]:  # exclude last segment (ends at terminal)
                cumulative += a.distance_to(b)
                bounce_progresses.append(cumulative / total_dist_cells)

        # Fire laser sound at animation start
        presenter.sound_effects.put_nowait("laser_fire")

        # Animate laser progress from 0 to 1
        laser_drawable = LaserDrawable(laser_result.path, 0.0)
        next_bounce = 0  # index into bounce_progresses
        last_time = pygame.time.get_ticks()
        while laser_drawable.progress < 1.0:
            now = pygame.time.get_ticks()
            delta = (now - last_time) / 1000.0
            last_time = now
            if duration > 0:
                laser_drawable.progress = min(
                    laser_drawable.progress + delta / duration, 1.0
                )
            else:
                laser_drawable.progress = 1.0

            # Check if we crossed any bounce thresholds
            while (
                next_bounce < len(bounce_progresses)
                and laser_drawable.progress >= bounce_progresses[next_bounce]
            ):
                presenter.sound_effects.put_nowait("mirror_hit")
                next_bounce += 1

            await presenter.render_state.put(
                generate_render_state(self.board_state, None, self.allegiance)
                + [laser_drawable]
            )
            await asyncio.sleep(1 / 60)

        await asyncio.sleep(1.0)

        # Fetch authoritative post-laser state from server
        new_state = await server.get_state()
        game_winner = winner(new_state)
        if game_winner is not None:
            final: list[Drawable] = [drawable_for(p) for p in new_state]
            final.append(GameOverDrawable(game_winner))
            await presenter.render_state.put(final)
            return None
        next_player = opponent(self.allegiance)
        return presenter.next_turn_phase(new_state, next_player)


@dataclass
class WaitRemoteTurn(TurnPhase):
    board_state: BoardState
    allegiance: Allegiance  # The remote player whose turn it is

    async def next_phase(
        self, presenter: GamePresenter, server: ServerInterface
    ) -> Optional[TurnPhase]:
        # The local player's client receives the opponent's move
        local_allegiance = opponent(self.allegiance)
        move = await presenter.clients[local_allegiance].opponent_moves.get()
        # Apply the move to a local copy for animation (server already mutated the real state)
        anim_state = copy.deepcopy(self.board_state)
        update_state(anim_state, move, self.allegiance)
        return Animating(anim_state, self.allegiance)


class GamePresenter:
    local_players: set[Allegiance]
    clients: dict[Allegiance, LocalClient]
    picker: Picker = Picker()
    render_state: asyncio.Queue[RenderState] = asyncio.Queue()
    sound_effects: asyncio.Queue[SoundEffect] = asyncio.Queue()

    def __init__(
        self,
        local_players: set[Allegiance],
        red: LocalClient,
        blue: LocalClient,
    ) -> None:
        self.local_players = local_players
        self.clients = {"red": red, "blue": blue}

    async def start(self, server: ServerInterface) -> None:
        state = await server.get_state()
        # Drain init messages for metadata
        # TODO Display player names
        # Also TODO Probably shouldn't decide who's red and who's blue before the server has told us
        # which is which -- we should get two clients from the orchestrator and assign them based on
        # the init messages. For now, this works because the orchestrator passes us clients in the
        # same order it gives them to the server, but it's brittle.
        _red_init = await self.clients["red"].init_info.get()
        _blue_init = await self.clients["blue"].init_info.get()

        phase: Optional[TurnPhase] = self.next_turn_phase(state, "red")
        while phase is not None:
            phase = await phase.next_phase(self, server)

    def next_turn_phase(self, state: BoardState, allegiance: Allegiance) -> TurnPhase:
        if allegiance in self.local_players:
            return MyTurn(state, allegiance)
        else:
            return WaitRemoteTurn(state, allegiance)

    def on_event(self, event: pygame.event.Event) -> None:
        self.picker.on_event(event)


def move_hitbox(piece_pos: Vector2, move: MoveKind) -> Rect:
    cell = piece_pos * 90 + Vector2(190, 0)
    match move:
        case "cw":
            return Rect(cell + Vector2(45, 0), (45, 90))
        case "ccw":
            return Rect(cell, (45, 90))
        case dir:
            return Rect(add_dir(piece_pos, dir) * 90 + Vector2(190, 0), (90, 90))


# Check if the click hits a piece, discarding pieces that don't belong to the player. Returns the
# index of the hit piece, or None if no piece was hit.
def _hit_test_own_piece(
    click: Vector2, board_state: BoardState, allegiance: Allegiance
) -> Optional[int]:
    return next(
        (
            index
            for index, piece in enumerate(board_state)
            if piece.allegiance == allegiance
            and Rect(
                piece.position * 90 + Vector2(235, 45) - Vector2(45, 45),
                (90, 90),
            ).collidepoint(click)
        ),
        None,
    )


# Generate the render state for a board state with an optional selected piece. Handles drawing move
# indicators, turn indicator, and game over screen.
def generate_render_state(
    board_state: BoardState, selected_index: Optional[int], player_turn: Allegiance
) -> list[Drawable]:
    pieces: list[Drawable] = [drawable_for(piece) for piece in board_state]
    move_indicators: list[Drawable] = (
        []
        if selected_index is None
        else [
            MoveIndicatorDrawable(board_state[selected_index], move)
            for move in move_options(board_state[selected_index], board_state)
        ]
    )
    _winner = winner(board_state)
    game_over: list[Drawable] = (
        [GameOverDrawable(_winner)] if _winner is not None else []
    )

    return pieces + move_indicators + game_over + [TurnIndicatorDrawable(player_turn)]


def drawable_for(piece: Piece[PieceKind]) -> PieceDrawable:
    return PieceDrawable(
        piece.kind, piece.position * 90 + Vector2(235, 45), 0, piece.allegiance
    )
