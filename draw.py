from abc import ABC, abstractmethod
from dataclasses import dataclass
import itertools
import math
from logic import King, MoveDir, MoveKind, OneSided, Piece, RotateDir, TwoSided, Wall
import pygame
from pygame.math import Vector2


type RenderState = list[Drawable]


class Drawable(ABC):
    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        pass


@dataclass
class Laser(Drawable):
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
    piece: Piece

    def draw(self, surface: pygame.Surface) -> None:
        match self.piece["kind"]:
            case "one-sided":
                draw_one_sided(surface, self.piece)
            case "two-sided":
                draw_two_sided(surface, self.piece)
            case "king":
                draw_king(surface, self.piece)
            case "wall":
                draw_wall(surface, self.piece)


@dataclass
class MoveIndicatorDrawable(Drawable):
    piece: Piece
    move: MoveKind

    def draw(self, surface: pygame.Surface) -> None:
        color = (255, 255, 0)
        offset = self.piece["position"] * 90 + Vector2(235, 45)
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


def draw_one_sided(surface: pygame.Surface, piece: OneSided) -> None:
    x, y = piece["position"]
    color = (200, 0, 0) if piece["allegiance"] == "red" else (0, 0, 200)
    points = [(10, 10), (10, 80), (80, 80), (80, 10)]
    match piece["dir"]:
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
        [(x * 90 + 190 + points[i][0], y * 90 + points[i][1]) for i in indices],
    )


def draw_two_sided(surface: pygame.Surface, piece: TwoSided) -> None:
    x, y = piece["position"]
    color = (200, 0, 0) if piece["allegiance"] == "red" else (0, 0, 200)
    match piece["dir"]:
        case "ne":
            points = [(10, 10), (20, 10), (80, 70), (80, 80), (70, 80), (10, 20)]
        case "se":
            points = [(10, 80), (20, 80), (80, 20), (80, 10), (70, 10), (10, 70)]
    pygame.draw.polygon(
        surface,
        color,
        [(x * 90 + 190 + points[i][0], y * 90 + points[i][1]) for i in range(6)],
    )


def draw_king(surface: pygame.Surface, piece: King) -> None:
    x, y = piece["position"]
    color = (200, 0, 0) if piece["allegiance"] == "red" else (0, 0, 200)
    pygame.draw.circle(surface, color, (x * 90 + 235, y * 90 + 45), 30)


def draw_wall(surface: pygame.Surface, piece: Wall) -> None:
    x, y = piece["position"]
    color = (200, 0, 0) if piece["allegiance"] == "red" else (0, 0, 200)
    pygame.draw.rect(surface, color, (x * 90 + 205, y * 90 + 15, 60, 60))
    if piece["stacked"]:
        pygame.draw.rect(surface, (200, 200, 0), (x * 90 + 215, y * 90 + 25, 40, 40))


def move_arrow() -> list[Vector2]:
    return [Vector2(80, 0), Vector2(50, -15), Vector2(50, 15)]


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
