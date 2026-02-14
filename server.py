import asyncio
from logic import (
    Allegiance,
    BoardState,
    Move,
    fire_laser,
    opponent,
    update_state,
    winner,
)
from protocol import ClientInterface, ServerInterface
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
        # Fire the laser and apply the result
        result = fire_laser(self.player_turn, self.state)
        if result.hit is not None:
            if result.hit.replacement is not None:
                self.state[result.hit.index].kind = result.hit.replacement
            else:
                del self.state[result.hit.index]
        winner_allegiance = winner(self.state)
        if winner_allegiance is None:
            self.player_turn = opponent(self.player_turn)
        return True


class LocalServer(ServerInterface):
    # Shared game state.
    game: Game
    client_moves: asyncio.Queue[Move] = asyncio.Queue()

    def __init__(self, state: BoardState) -> None:
        self.game = Game(state)

    async def start(self, red: ClientInterface, blue: ClientInterface) -> None:
        clients: Clients = {"red": red, "blue": blue}
        await red.send_init(
            player_allegiance="red",
            opponent_name="TODO",
        )
        await blue.send_init(
            player_allegiance="blue",
            opponent_name="TODO",
        )
        while True:
            move = await self.client_moves.get()
            # `move` is from the player who just moved, but `self.game.player_turn` will already
            # have been updated to the next player, so we can just send the latest move to the
            # player whose turn it is now.
            await clients[self.game.player_turn].send_opponent_move(move)
            if winner(self.game.state) is not None:
                break

    async def send_move(self, move: Move) -> None:
        if self.game.try_move(move):
            await self.client_moves.put(move)

    async def get_state(self) -> BoardState:
        return self.game.state


class Clients(TypedDict):
    red: ClientInterface
    blue: ClientInterface
