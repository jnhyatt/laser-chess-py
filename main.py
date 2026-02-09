import asyncio
import itertools
import pygame
from pygame.math import Vector2
import sys
from typing import Tuple, TypedDict

from client import LocalClient
from draw import Laser, MoveIndicatorDrawable, PieceDrawable
from logic import Allegiance, BoardState, Move, MoveKind, opponent, update_state, winner
from protocol import ClientInterface, ServerInterface
from server import LocalServer


def tmp_board_state() -> BoardState:
    return [
        {"kind": "king", "position": Vector2(5, 0), "allegiance": "red"},
        {
            "kind": "wall",
            "position": Vector2(6, 0),
            "allegiance": "red",
            "stacked": True,
        },
        {
            "kind": "wall",
            "position": Vector2(4, 0),
            "allegiance": "red",
            "stacked": True,
        },
        {
            "kind": "two-sided",
            "position": Vector2(7, 0),
            "allegiance": "red",
            "dir": "se",
        },
        {"kind": "king", "position": Vector2(4, 7), "allegiance": "blue"},
        {
            "kind": "wall",
            "position": Vector2(3, 7),
            "allegiance": "blue",
            "stacked": True,
        },
        {
            "kind": "wall",
            "position": Vector2(5, 7),
            "allegiance": "blue",
            "stacked": True,
        },
        {
            "kind": "two-sided",
            "position": Vector2(2, 7),
            "allegiance": "blue",
            "dir": "se",
        },
        {
            "kind": "one-sided",
            "position": Vector2(9, 5),
            "allegiance": "red",
            "dir": "sw",
        },
        {
            "kind": "one-sided",
            "position": Vector2(4, 5),
            "allegiance": "blue",
            "dir": "se",
        },
        {
            "kind": "one-sided",
            "position": Vector2(4, 6),
            "allegiance": "red",
            "dir": "ne",
        },
        {
            "kind": "one-sided",
            "position": Vector2(6, 6),
            "allegiance": "blue",
            "dir": "nw",
        },
        {
            "kind": "one-sided",
            "position": Vector2(6, 2),
            "allegiance": "red",
            "dir": "sw",
        },
        {
            "kind": "one-sided",
            "position": Vector2(5, 2),
            "allegiance": "blue",
            "dir": "ne",
        },
    ]


async def main() -> None:
    pygame.init()
    surface = pygame.display.set_mode((1280, 720))

    progress = [0.0]
    asyncio.create_task(advance_laser(progress))

    while True:
        for event in pygame.event.get():
            if event.type == pygame.constants.QUIT:
                pygame.quit()
                sys.exit()

        surface.fill((28, 72, 28))
        for y in range(0, 8):
            for x in range(0, 10):
                color = (180, 180, 128) if (x + y) % 2 == 0 else (24, 24, 24)
                pygame.draw.rect(surface, color, (x * 90 + 190, y * 90, 90, 90))

        laser = Laser(
            [
                Vector2(9, 8),
                Vector2(9, 5),
                Vector2(4, 5),
                Vector2(4, 6),
                Vector2(6, 6),
                Vector2(6, 2),
                Vector2(5, 2),
                Vector2(5, 0),
            ],
            progress[0],
        )
        pieces = [PieceDrawable(x) for x in tmp_board_state()]
        move_options: list[MoveKind] = [
            "e",
            "ne",
            "n",
            "nw",
            "w",
            "sw",
            "se",
            "cw",
            "ccw",
        ]
        move_indicators = [
            MoveIndicatorDrawable(
                pieces[9].piece,
                dir,
            )
            for dir in move_options
        ]
        laser.draw(surface)
        for piece in pieces:
            piece.draw(surface)
        for indicator in move_indicators:
            indicator.draw(surface)

        pygame.display.flip()
        await asyncio.sleep(1 / 60)  # yield to event loop


async def advance_laser(progress: list[float]) -> None:
    progress[0] = 0
    while True:
        await animate_laser(progress)
        progress[0] = 0


async def animate_laser(progress: list[float]) -> None:
    last_time = pygame.time.get_ticks()
    while progress[0] < 1:
        now = pygame.time.get_ticks()
        delta = now - last_time
        last_time = now
        progress[0] += delta / 1000
        await asyncio.sleep(1 / 60)
    await asyncio.sleep(1)


# Orchestrator stuff


def start_local_game() -> None:
    red = LocalClient()
    blue = LocalClient()
    server = LocalServer(tmp_board_state())
    server_task = server.start(red, blue)
    red_client_task = red.start(server)
    blue_client_task = blue.start(server)
    asyncio.gather(server_task, red_client_task, blue_client_task)


if __name__ == "__main__":
    asyncio.run(main())
