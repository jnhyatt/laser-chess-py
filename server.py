import asyncio
from logic import Allegiance, BoardState, Laser, Move, opponent, update_state, winner
from protocol import (
    ClientInterface,
    ClientMessage,
    InitMessage,
    MoveMessage,
    OpponentMove,
    ServerInterface,
)
from typing import Literal, TypedDict


type TryMoveResult = Literal["invalid", "ok"]


class Game:
    state: BoardState
    player_turn: Allegiance

    def __init__(self, state: BoardState) -> None:
        self.state = state
        self.player_turn = "red"

    def try_move(self, move: Move) -> bool:
        new_state = update_state(self.state, move, self.player_turn)
        if new_state is None:
            return False
        self.state = new_state
        winner_allegiance = winner(self.state)
        if winner_allegiance is None:
            self.player_turn = opponent(self.player_turn)
        return True


class LocalServer(ServerInterface):
    # Shared game state.
    game: Game
    client_moves: asyncio.Queue[Move]

    def __init__(self, state: BoardState) -> None:
        self.game = Game(state)
        self.client_moves = asyncio.Queue()

    async def start(self, red: ClientInterface, blue: ClientInterface) -> None:
        clients: Clients = {"red": red, "blue": blue}
        await red.send(
            InitMessage(
                state=self.game.state,
                player_allegiance="red",
                opponent_name="TODO",
            )
        )
        await blue.send(
            InitMessage(
                state=self.game.state,
                player_allegiance="blue",
                opponent_name="TODO",
            )
        )
        while True:
            move = await self.client_moves.get()
            laser = Laser.start(self.game.player_turn)
            await clients[opponent(self.game.player_turn)].send(
                OpponentMove(
                    move=move,
                )
            )
            if winner(self.game.state) is not None:
                break

    # TODO maybe doesn't have to be async
    async def send(self, message: ClientMessage) -> None:
        match message:
            case MoveMessage(move=move):
                if self.game.try_move(move):
                    self.client_moves.put_nowait(move)


class Clients(TypedDict):
    red: ClientInterface
    blue: ClientInterface
