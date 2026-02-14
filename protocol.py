from abc import ABC, abstractmethod
from logic import Allegiance, BoardState, Move


# Represents a client's view of the server. The client can send messages to the server and is
# completely agnostic about how the server is implemented.
class ServerInterface(ABC):
    @abstractmethod
    async def send_move(self, move: Move) -> None:
        pass

    @abstractmethod
    async def get_state(self) -> BoardState:
        pass


class ClientInterface(ABC):
    @abstractmethod
    async def send_init(
        self, player_allegiance: Allegiance, opponent_name: str
    ) -> None:
        pass

    @abstractmethod
    async def send_opponent_move(self, move: Move) -> None:
        pass
