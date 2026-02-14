from abc import ABC, abstractmethod
from dataclasses import dataclass
import itertools
import math
from logic import (
    Allegiance,
    King,
    MoveDir,
    MoveKind,
    OneSided,
    Piece,
    PieceKind,
    RotateDir,
    TwoSided,
    Wall,
)
import pygame
from pygame.math import Vector2


type RenderState = list[Drawable]


class Drawable(ABC):
    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        pass


@dataclass
class LaserDrawable(Drawable):
    path: list[Vector2]
    progress: float

    def draw(self, surface: pygame.Surface) -> None:
        # Laser is a list of points. The total length is the sum of the distances between each pair of
        # points. We want to put together a list of segments mapped to the accumulated distance to the
        # end of that segment.
        pairs = list(itertools.pairwise(self.path))
        total_dist = sum(a.distance_to(b) for a, b in pairs) * self.progress
        distances = itertools.accumulate(
            (pair[0].distance_to(pair[1]) for pair in pairs)
        )
        for (start, end), dist in zip(itertools.pairwise(self.path), distances):
            seg_len = start.distance_to(end)
            # If the laser hasn't reached the start of this segment, skip it.
            if dist - seg_len >= total_dist:
                continue
            # If the laser hasn't reached the end of this segment, shorten it to the correct distance.
            if dist > total_dist:
                end = start + (end - start) * (
                    (total_dist - (dist - seg_len)) / seg_len
                )
            # Transform from cell space to world space and draw the line segment.
            pygame.draw.line(
                surface,
                (255, 63, 63),
                (start.x * 90 + 235, start.y * 90 + 45),
                (end.x * 90 + 235, end.y * 90 + 45),
                5,
            )


# TODO `Piece` is too inflexible for the renderer -- it can't represent pieces in the middle of
# animating through a movement or rotation. Make a mirrored hierarchy of drawable pieces that can
# represent these intermediate states.
@dataclass
class PieceDrawable(Drawable):
    piece: PieceKind
    position: Vector2
    rotation: float
    allegiance: str

    def draw(self, surface: pygame.Surface) -> None:
        match self.piece.kind:
            case "one-sided":
                draw_one_sided(
                    surface, self.piece, self.position, self.rotation, self.allegiance
                )
            case "two-sided":
                draw_two_sided(
                    surface, self.piece, self.position, self.rotation, self.allegiance
                )
            case "king":
                draw_king(surface, self.piece, self.position, self.allegiance)
            case "wall":
                draw_wall(surface, self.piece, self.position, self.allegiance)


@dataclass
class MoveIndicatorDrawable(Drawable):
    piece: Piece
    move: MoveKind

    def draw(self, surface: pygame.Surface) -> None:
        color = (255, 255, 0)
        offset = self.piece.position * 90 + Vector2(235, 45)
        match self.move:
            case "cw" | "ccw":
                points = [x + offset for x in turn_arrow(self.move)]
                pygame.draw.polygon(surface, color, points)
            case "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw":
                points = [
                    rotated(x, move_dir_rotation(self.move)) + offset
                    for x in move_arrow()
                ]
                pygame.draw.polygon(surface, color, points)


def draw_one_sided(
    surface: pygame.Surface,
    piece: OneSided,
    position: Vector2,
    rotation: float,
    allegiance: str,
) -> None:
    color = (200, 0, 0) if allegiance == "red" else (0, 0, 200)
    points = [Vector2(-35, -35), Vector2(-35, 35), Vector2(35, 35), Vector2(35, -35)]
    match piece.dir:
        case "ne":
            indices = [0, 1, 2]
        case "se":
            indices = [0, 1, 3]
        case "sw":
            indices = [0, 2, 3]
        case "nw":
            indices = [1, 2, 3]
    pygame.draw.polygon(
        surface,
        color,
        [position + rotated(points[i], rotation) for i in indices],
    )


def draw_two_sided(
    surface: pygame.Surface,
    piece: TwoSided,
    position: Vector2,
    rotation: float,
    allegiance: str,
) -> None:
    color = (200, 0, 0) if allegiance == "red" else (0, 0, 200)
    match piece.dir:
        case "ne":
            points = [
                Vector2(-35, -35),
                Vector2(-25, -35),
                Vector2(35, 25),
                Vector2(35, 35),
                Vector2(25, 35),
                Vector2(-35, -25),
            ]
        case "se":
            points = [
                Vector2(-35, 35),
                Vector2(-25, 35),
                Vector2(35, -25),
                Vector2(35, -35),
                Vector2(25, -35),
                Vector2(-35, 25),
            ]
    pygame.draw.polygon(
        surface,
        color,
        [position + rotated(points[i], rotation) for i in range(6)],
    )


@dataclass
class GameOverDrawable(Drawable):
    winner: Allegiance

    def draw(self, surface: pygame.Surface) -> None:
        width = surface.get_width()
        height = 80
        banner = pygame.Surface((width, height), pygame.SRCALPHA)
        banner.fill((0, 0, 0, 160))
        y = (surface.get_height() - height) // 2
        surface.blit(banner, (0, y))
        font = pygame.font.Font(None, 48)
        label = f"{self.winner.capitalize()} Wins!"
        text = font.render(label, True, (255, 255, 255))
        text_rect = text.get_rect(center=(width // 2, surface.get_height() // 2))
        surface.blit(text, text_rect)


@dataclass
class TurnIndicatorDrawable(Drawable):
    allegiance: str

    def draw(self, surface: pygame.Surface) -> None:
        color = (255, 0, 0) if self.allegiance == "red" else (0, 0, 255)
        font = pygame.font.Font(None, 36)
        label = f"{self.allegiance.capitalize()} to move"
        text = font.render(label, True, color)
        surface.blit(text, (10, 10))


def draw_king(
    surface: pygame.Surface, piece: King, position: Vector2, allegiance: str
) -> None:
    color = (200, 0, 0) if allegiance == "red" else (0, 0, 200)
    pygame.draw.circle(surface, color, position, 30)


def draw_wall(
    surface: pygame.Surface, piece: Wall, position: Vector2, allegiance: str
) -> None:
    color = (200, 0, 0) if allegiance == "red" else (0, 0, 200)
    pygame.draw.rect(surface, color, (position.x - 30, position.y - 30, 60, 60))
    if piece.stacked:
        pygame.draw.rect(
            surface, (200, 200, 0), (position.x - 15, position.y - 15, 30, 30)
        )


def move_arrow() -> list[Vector2]:
    return [Vector2(100, 0), Vector2(70, -15), Vector2(70, 15)]


def turn_arrow(dir: RotateDir) -> list[Vector2]:
    head = [Vector2(45, 0), Vector2(35, 10), Vector2(25, 0)]
    inside = [
        Vector2(math.cos(x / 60 * math.pi), -math.sin(x / 60 * math.pi)) * 30
        for x in range(0, 21)
    ]
    outside = [
        Vector2(math.cos(x / 60 * math.pi), -math.sin(x / 60 * math.pi)) * 40
        for x in range(20, -1, -1)
    ]
    result = head + inside + outside
    result = [rotated(x, math.pi / 6) for x in result]
    if dir == "ccw":
        result = [Vector2(-p.x, p.y) for p in result]
    return result


def rotated(x: Vector2, angle: float) -> Vector2:
    cos = math.cos(angle)
    sin = math.sin(angle)
    return Vector2(x.x * cos - x.y * sin, x.x * sin + x.y * cos)


def move_dir_rotation(move: MoveDir) -> float:
    match move:
        case "e":
            return 0
        case "se":
            return math.pi / 4
        case "s":
            return math.pi / 2
        case "sw":
            return 3 * math.pi / 4
        case "w":
            return math.pi
        case "nw":
            return -3 * math.pi / 4
        case "n":
            return -math.pi / 2
        case "ne":
            return -math.pi / 4
