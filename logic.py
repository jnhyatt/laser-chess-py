import json
from dataclasses import dataclass
from pygame.math import Vector2
from typing import Literal, Optional, TypeGuard


type PieceKind = OneSided | TwoSided | King | Wall

type Allegiance = Literal["red", "blue"]


def opponent(allegiance: Allegiance) -> Allegiance:
    return "red" if allegiance == "blue" else "blue"


@dataclass
class OneSided:
    kind: Literal["one-sided"]
    dir: OneSidedDir

    def __init__(self, dir: OneSidedDir) -> None:
        self.kind = "one-sided"
        self.dir = dir

    def reflect(self, direction: LaserDir) -> LaserDir | Optional[PieceKind]:
        match (self.dir, direction):
            case ("ne", "w") | ("nw", "e"):
                return "n"
            case ("ne", "s") | ("se", "n"):
                return "e"
            case ("se", "w") | ("sw", "e"):
                return "s"
            case ("sw", "n") | ("nw", "s"):
                return "w"
            case _:
                return None


@dataclass
class TwoSided:
    kind: Literal["two-sided"]
    dir: TwoSidedDir

    def __init__(self, dir: TwoSidedDir) -> None:
        self.kind = "two-sided"
        self.dir = dir

    def reflect(self, direction: LaserDir) -> LaserDir | Optional[PieceKind]:
        match direction:
            case "n":
                return "w" if self.dir == "ne" else "e"
            case "e":
                return "s" if self.dir == "ne" else "n"
            case "s":
                return "e" if self.dir == "ne" else "w"
            case "w":
                return "n" if self.dir == "ne" else "s"


@dataclass
class King:
    kind: Literal["king"]

    def __init__(self) -> None:
        self.kind = "king"

    def reflect(self, direction: LaserDir) -> LaserDir | Optional[PieceKind]:
        return None


class Wall:
    kind: Literal["wall"]
    stacked: bool

    def __init__(self, stacked: bool = True) -> None:
        self.kind = "wall"
        self.stacked = stacked

    def reflect(self, direction: LaserDir) -> LaserDir | Optional[PieceKind]:
        return Wall(stacked=False) if self.stacked else None


@dataclass
class Piece[T: PieceKind]:
    position: Vector2
    allegiance: Allegiance
    kind: T


x = Piece(Vector2(0, 0), "red", Wall())


type BoardState = list[Piece[PieceKind]]

type MoveKind = MoveDir | RotateDir

type MoveDir = Literal["n", "ne", "e", "se", "s", "sw", "w", "nw"]
type RotateDir = Literal["cw", "ccw"]


@dataclass
class Move:
    piece: Vector2
    kind: MoveKind


@dataclass
class LaserHit:
    index: int
    replacement: Optional[PieceKind]


type LaserDir = Literal["n", "e", "s", "w"]
type OneSidedDir = Literal["ne", "se", "sw", "nw"]
type TwoSidedDir = Literal["ne", "se"]


@dataclass
class LaserResult:
    path: list[Vector2]
    hit: Optional[LaserHit]


@dataclass
class Laser:
    position: Vector2
    direction: LaserDir

    @staticmethod
    def start(player: Allegiance) -> Laser:
        match player:
            case "red":
                return Laser(Vector2(0, -1), "s")
            case "blue":
                return Laser(Vector2(9, 8), "n")

    def bounce(self, state: BoardState) -> LaserResult:
        path: list[Vector2] = [Vector2(self.position)]

        def trace() -> Optional[LaserHit]:
            hit_index = self.cast(state)
            # cast mutates self.position to the hit piece's position (or off-board)
            path.append(Vector2(self.position))
            if hit_index is None:
                return None
            match state[hit_index].kind.reflect(self.direction):
                case "n" | "e" | "s" | "w" as new_dir:
                    self.direction = new_dir
                    return trace()
                case new_piece:
                    return LaserHit(hit_index, new_piece)

        hit = trace()
        return LaserResult(path, hit)

    # Raycast a laser in a straight line until it hits a wall (return None) or a piece (return
    # its index).
    def cast(self, state: BoardState) -> Optional[int]:
        next_seg = self.advance()
        if next_seg is None:
            return None
        hit_index = next(
            (i for i, piece in enumerate(state) if piece.position == next_seg.position),
            None,
        )
        if hit_index is not None:
            return hit_index
        return next_seg.cast(state)

    # Advance the laser one cell in its current direction. Returns the new laser state, or None if
    # it goes off the board.
    def advance(self) -> Optional[Laser]:
        match self.direction:
            case "n":
                self.position += Vector2(0, -1)
            case "e":
                self.position += Vector2(1, 0)
            case "s":
                self.position += Vector2(0, 1)
            case "w":
                self.position += Vector2(-1, 0)
        return (
            self if (0 <= self.position.x < 10 and 0 <= self.position.y < 8) else None
        )


def is_king_piece(piece: Piece[PieceKind]) -> TypeGuard[Piece[King]]:
    return piece.kind.kind == "king"


# Returns the allegiance of the winner, or None if there is no winner yet. This doubles as the "game
# over" check.
def winner(state: BoardState) -> Optional[Allegiance]:
    kings: list[Piece[King]] = [piece for piece in state if is_king_piece(piece)]
    if len(kings) < 2:
        return kings[0].allegiance
    return None


# Validate and apply a move to a board state. Returns the new board state if the move is valid, or
# None if the move is invalid.
def update_state(
    state: BoardState, move: Move, player: Allegiance
) -> Optional[BoardState]:
    piece = next((piece for piece in state if piece.position == move.piece), None)
    if piece is None:
        return None  # No piece at the specified position
    if piece.allegiance != player:
        return None  # Can't move other player's pieces
    match move.kind:
        case "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw":
            target = add_dir(piece.position, move.kind)
            if not (0 <= target.x < 10 and 0 <= target.y < 8):
                return None  # Target position is out of bounds
            if any(piece.position == target for piece in state):
                return None  # Target position is occupied
            piece.position = target
        case "cw" | "ccw":
            match piece.kind.kind:
                case "one-sided":
                    rotate_one_sided(piece.kind, move.kind)
                case "two-sided":
                    rotate_two_sided(piece.kind)
                case "king" | "wall":
                    return None  # Can't rotate kings or walls
    return state


def add_dir(position: Vector2, dir: MoveDir) -> Vector2:
    match dir:
        case "n":
            return position + Vector2(0, -1)
        case "ne":
            return position + Vector2(1, -1)
        case "e":
            return position + Vector2(1, 0)
        case "se":
            return position + Vector2(1, 1)
        case "s":
            return position + Vector2(0, 1)
        case "sw":
            return position + Vector2(-1, 1)
        case "w":
            return position + Vector2(-1, 0)
        case "nw":
            return position + Vector2(-1, -1)


def fire_laser(player: Allegiance, state: BoardState) -> LaserResult:
    return Laser.start(player).bounce(state)


def move_options(piece: Piece[PieceKind], state: BoardState) -> set[MoveKind]:
    options: set[MoveKind] = set()
    # Rotation options for pieces that can rotate
    match piece.kind.kind:
        case "one-sided" | "two-sided":
            options.add("cw")
            options.add("ccw")
    # Directional movement: check all 8 adjacent cells
    all_dirs: list[MoveDir] = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]
    for dir in all_dirs:
        target = add_dir(piece.position, dir)
        if not (0 <= target.x < 10 and 0 <= target.y < 8):
            continue
        if any(p.position == target for p in state):
            continue
        options.add(dir)
    return options


def rotate_one_sided(piece: OneSided, dir: RotateDir) -> None:
    match piece.dir:
        case "ne":
            piece.dir = "se" if dir == "cw" else "nw"
        case "se":
            piece.dir = "sw" if dir == "cw" else "ne"
        case "sw":
            piece.dir = "nw" if dir == "cw" else "se"
        case "nw":
            piece.dir = "ne" if dir == "cw" else "sw"


def rotate_two_sided(piece: TwoSided) -> None:
    piece.dir = "se" if piece.dir == "ne" else "ne"


def load_board_state(path: str) -> BoardState:
    with open(path) as f:
        data = json.load(f)
    pieces: BoardState = []
    for p in data["pieces"]:
        kind: PieceKind
        match p["kind"]:
            case "one-sided":
                kind = OneSided(p["dir"])
            case "two-sided":
                kind = TwoSided(p["dir"])
            case "king":
                kind = King()
            case "wall":
                kind = Wall(p.get("stacked", True))
            case other:
                raise ValueError(f"Unknown piece kind: {other}")
        pieces.append(Piece(Vector2(p["x"], p["y"]), p["allegiance"], kind))
    return pieces
