from abc import ABC, abstractmethod
from logic import Allegiance, BoardState, Move
from typing import Literal, TypedDict


# Represents a client's view of the server. The client can send messages to the server and is
# completely agnostic about how the server is implemented.
class ServerInterface(ABC):
    @abstractmethod
    async def send(self, message: ClientMessage) -> None:
        pass


class ClientInterface(ABC):
    @abstractmethod
    async def send(self, message: ServerMessage) -> None:
        pass


type ServerMessage = InitMessage | OpponentMove


class InitMessage(TypedDict):
    kind: Literal["init"]
    state: BoardState
    player_allegiance: Allegiance
    opponent_name: str


class OpponentMove(TypedDict):
    kind: Literal["opponent_move"]
    move: Move


type ClientMessage = MoveMessage


class MoveMessage(TypedDict):
    kind: Literal["move"]
    move: Move
