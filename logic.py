from pygame.math import Vector2
from typing import Literal, Optional, Tuple, TypedDict


type Piece = OneSided | TwoSided | King | Wall

type Allegiance = Literal["red", "blue"]


def opponent(allegiance: Allegiance) -> Allegiance:
    return "red" if allegiance == "blue" else "blue"


class PieceBase(TypedDict):
    position: Vector2
    allegiance: Allegiance


class OneSided(PieceBase):
    kind: Literal["one-sided"]
    dir: Literal["ne", "se", "sw", "nw"]


class TwoSided(PieceBase):
    kind: Literal["two-sided"]
    dir: Literal["ne", "se"]


class King(PieceBase):
    kind: Literal["king"]


class Wall(PieceBase):
    kind: Literal["wall"]
    stacked: bool


type BoardState = list[Piece]

type MoveKind = MoveDir | RotateDir

type MoveDir = Literal["n", "ne", "e", "se", "s", "sw", "w", "nw"]
type RotateDir = Literal["cw", "ccw"]


class Move(TypedDict):
    piece: Vector2
    kind: MoveKind


# Returns the allegiance of the winner, or None if there is no winner yet. This doubles as the "game
# over" check.
def winner(state: BoardState) -> Optional[Allegiance]:
    kings: list[King] = [piece for piece in state if piece["kind"] == "king"]
    if len(kings) < 2:
        return kings[0]["allegiance"]
    return None


# Validate and apply a move to a board state. Returns the new board state if the move is valid, or
# None if the move is invalid.
def update_state(
    state: BoardState, move: Move, player: Allegiance
) -> Optional[BoardState]:
    piece = next((piece for piece in state if piece["position"] == move["piece"]), None)
    if piece is None:
        return None  # No piece at the specified position
    if piece["allegiance"] != player:
        return None  # Can't move other player's pieces
    match move["kind"]:
        case "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw":
            target = move_target(piece, move["kind"])
            if not (0 <= target.x < 10 and 0 <= target.y < 8):
                return None  # Target position is out of bounds
            if any(piece["position"] == target for piece in state):
                return None  # Target position is occupied
            piece["position"] = target
        case "cw" | "ccw":
            match piece["kind"]:
                case "one-sided":
                    rotate_one_sided(piece, move["kind"])
                case "two-sided":
                    rotate_two_sided(piece)
                case "king" | "wall":
                    return None  # Can't rotate kings or walls
    return state


# Returns the position a piece would move to if it moved in the specified direction. Does no bounds
# checking or collision checking.
def move_target(piece: Piece, dir: MoveDir) -> Vector2:
    match dir:
        case "n":
            return piece["position"] + Vector2(0, -1)
        case "ne":
            return piece["position"] + Vector2(1, -1)
        case "e":
            return piece["position"] + Vector2(1, 0)
        case "se":
            return piece["position"] + Vector2(1, 1)
        case "s":
            return piece["position"] + Vector2(0, 1)
        case "sw":
            return piece["position"] + Vector2(-1, 1)
        case "w":
            return piece["position"] + Vector2(-1, 0)
        case "nw":
            return piece["position"] + Vector2(-1, -1)


def rotate_one_sided(piece: OneSided, dir: RotateDir) -> None:
    match piece["dir"]:
        case "ne":
            piece["dir"] = "se" if dir == "cw" else "nw"
        case "se":
            piece["dir"] = "sw" if dir == "cw" else "ne"
        case "sw":
            piece["dir"] = "nw" if dir == "cw" else "se"
        case "nw":
            piece["dir"] = "ne" if dir == "cw" else "sw"


def rotate_two_sided(piece: TwoSided) -> None:
    piece["dir"] = "se" if piece["dir"] == "ne" else "ne"
