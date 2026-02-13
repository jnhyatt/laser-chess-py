from abc import ABC, abstractmethod
from dataclasses import dataclass
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


@dataclass
class InitMessage:
    state: BoardState
    player_allegiance: Allegiance
    opponent_name: str


@dataclass
class OpponentMove:
    move: Move


type ClientMessage = MoveMessage


@dataclass
class MoveMessage:
    move: Move
