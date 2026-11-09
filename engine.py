"""CheckMate chess engine: squares, pieces, board, moves and game state.

Python port of the Java classes Square, Piece, Pawn, Rook, Knight, Bishop,
Queen, King, ChessBoard, Move and GameStateManager.

Conventions
-----------
* Rows ("ranks") run 0-7 from the top of the screen; Black starts on rows 0-1
  and White starts on rows 6-7, exactly like the Java version.
* Pieces signal an illegal move by raising ``IllegalMoveError`` (the Java code
  used ``IllegalStateException``).
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

WHITE = "White"
BLACK = "Black"


class IllegalMoveError(Exception):
    """Raised by a piece when a move is not legal."""


# --------------------------------------------------------------------------
# Square
# --------------------------------------------------------------------------
class Square:
    def __init__(self, rank: int, file: int):
        self.rank = rank
        self.file = file
        self.piece: Optional[Piece] = None

    @property
    def is_occupied(self) -> bool:
        return self.piece is not None

    def occupy(self, piece: Optional["Piece"]) -> None:
        self.piece = piece

    def vacate(self) -> None:
        self.piece = None

    def total_distance(self, other: "Square") -> float:
        return math.hypot(self.rank - other.rank, self.file - other.file)

    def rank_distance(self, other: "Square") -> int:
        return abs(self.rank - other.rank)

    def file_distance(self, other: "Square") -> int:
        return abs(self.file - other.file)

    def same_rank(self, other: "Square") -> bool:
        return self.rank == other.rank

    def same_file(self, other: "Square") -> bool:
        return self.file == other.file

    def same_diagonal(self, other: "Square") -> bool:
        return self.rank_distance(other) == self.file_distance(other)

    def equals(self, other: Optional["Square"]) -> bool:
        """Same coordinates?  (Deliberately not __eq__, so squares stay hashable by identity.)"""
        return other is not None and self.rank == other.rank and self.file == other.file

    def __repr__(self) -> str:
        return f"Square({self.rank}, {self.file})"


# --------------------------------------------------------------------------
# Pieces
# --------------------------------------------------------------------------
class Piece(ABC):
    """Abstract base class: the board only ever holds concrete pieces."""

    def __init__(self, color: str, spaces_to_move: float, location: Optional[Square]):
        self.color = color
        self.spaces_to_move = spaces_to_move
        self.location = location

    def _reject_ally_or_same_square(self, destination: Square) -> None:
        if destination.is_occupied and destination.piece.color == self.color:
            raise IllegalMoveError("Target square is occupied by an ally piece!")
        if self.location.equals(destination):
            raise IllegalMoveError("Target square is the same as the current square!")

    @abstractmethod
    def check_legal_move(self, destination: Square) -> bool:
        """Return True if legal, otherwise raise IllegalMoveError."""

    @abstractmethod
    def get_valid_moves(self, board: "ChessBoard", current_square: Square) -> List["Move"]:
        ...

    def __repr__(self) -> str:
        return f"{self.color}{type(self).__name__}"


def _straight_path_clear(loc: Square, dest: Square) -> bool:
    """Squares strictly between loc and dest on a rank/file must be empty (raises if not)."""
    if loc.same_rank(dest):
        step = -1 if loc.file - dest.file > 0 else 1
        for i in range(1, loc.file_distance(dest)):
            if ChessBoard.get_square(loc.rank, loc.file + step * i).is_occupied:
                raise IllegalMoveError("Target square must not be obstructed by other pieces!")
    if loc.same_file(dest):
        step = -1 if loc.rank - dest.rank > 0 else 1
        for i in range(1, loc.rank_distance(dest)):
            if ChessBoard.get_square(loc.rank + step * i, loc.file).is_occupied:
                raise IllegalMoveError("Target square must not be obstructed by other pieces!")
    return True


def _diagonal_path_clear(loc: Square, dest: Square) -> bool:
    """Squares strictly between loc and dest on a diagonal must be empty (returns False if not)."""
    rank_step = 1 if dest.rank > loc.rank else -1
    file_step = 1 if dest.file > loc.file else -1
    r, f = loc.rank + rank_step, loc.file + file_step
    while r != dest.rank and f != dest.file:
        if ChessBoard.get_square(r, f).is_occupied:
            return False
        r += rank_step
        f += file_step
    return True


_ORTHOGONAL = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_DIAGONAL = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _sliding_moves(piece: Piece, current_square: Square, directions) -> List["Move"]:
    """Collect moves for rooks, bishops and queens by sliding along each direction."""
    moves: List[Move] = []
    for dr, df in directions:
        for i in range(1, 8):
            target = ChessBoard.get_square(current_square.rank + dr * i,
                                           current_square.file + df * i)
            if target is None:          # fell off the board
                break
            try:
                if piece.check_legal_move(target):
                    moves.append(Move.from_squares(current_square, target, piece.color))
                if target.is_occupied:  # any piece blocks further sliding
                    break
            except IllegalMoveError:    # ally piece or obstruction
                break
    return moves


class Rook(Piece):
    def __init__(self, color: str, location: Square):
        super().__init__(color, 8, location)
        self.has_moved = False

    def is_path_clear(self, destination: Square) -> bool:
        return _straight_path_clear(self.location, destination)

    def check_legal_move(self, destination: Square) -> bool:
        self._reject_ally_or_same_square(destination)
        if not self.location.same_rank(destination) and not self.location.same_file(destination):
            raise IllegalMoveError("Target square must be on the same rank or file!")
        if self.location.total_distance(destination) > 1:
            self.is_path_clear(destination)
        return True

    def get_valid_moves(self, board, current_square):
        return _sliding_moves(self, current_square, _ORTHOGONAL)


class Bishop(Piece):
    def __init__(self, color: str, location: Square):
        super().__init__(color, 8, location)

    def same_diagonal(self, destination: Square) -> bool:
        return self.location.same_diagonal(destination)

    def is_diagonal_path_clear(self, destination: Square) -> bool:
        return _diagonal_path_clear(self.location, destination)

    def check_legal_move(self, destination: Square) -> bool:
        self._reject_ally_or_same_square(destination)
        if not self.same_diagonal(destination):
            raise IllegalMoveError("Target square must be on the same diagonal!")
        if not self.is_diagonal_path_clear(destination):
            raise IllegalMoveError("Target square cannot be obstructed by other pieces!")
        return True

    def get_valid_moves(self, board, current_square):
        return _sliding_moves(self, current_square, _DIAGONAL)


class Queen(Piece):
    def __init__(self, color: str, location: Square):
        super().__init__(color, 8, location)

    def is_path_clear(self, destination: Square) -> bool:
        return _straight_path_clear(self.location, destination)

    def is_diagonal_path_clear(self, destination: Square) -> bool:
        return _diagonal_path_clear(self.location, destination)

    def check_legal_move(self, destination: Square) -> bool:
        self._reject_ally_or_same_square(destination)
        loc = self.location
        rd, fd = loc.rank_distance(destination), loc.file_distance(destination)
        if (rd == 2 and fd == 1) or (rd == 1 and fd == 2):
            raise IllegalMoveError("Target square cannot be a knight move away!")
        if loc.same_rank(destination) or loc.same_file(destination):
            if loc.total_distance(destination) > 1:
                self.is_path_clear(destination)
        elif loc.same_diagonal(destination):
            if not self.is_diagonal_path_clear(destination):
                raise IllegalMoveError("Target square cannot be diagonally obstructed!")
        else:
            raise IllegalMoveError("Target square must be on a rank, file or diagonal!")
        return True

    def get_valid_moves(self, board, current_square):
        return _sliding_moves(self, current_square, _ORTHOGONAL + _DIAGONAL)


class Knight(Piece):
    _OFFSETS = [(-2, -1), (-2, 1), (2, -1), (2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2)]

    def __init__(self, color: str, location: Square):
        super().__init__(color, math.sqrt(5), location)

    def check_legal_move(self, destination: Square) -> bool:
        self._reject_ally_or_same_square(destination)
        rd = self.location.rank_distance(destination)
        fd = self.location.file_distance(destination)
        if not ((rd == 2 and fd == 1) or (rd == 1 and fd == 2)):
            raise IllegalMoveError("Target square is not an L shape!")
        return True

    def get_valid_moves(self, board, current_square):
        moves = []
        for dr, df in self._OFFSETS:
            target = ChessBoard.get_square(current_square.rank + dr, current_square.file + df)
            if target is None:
                continue
            try:
                if self.check_legal_move(target):
                    moves.append(Move.from_squares(current_square, target, self.color))
            except IllegalMoveError:
                pass
        return moves


class King(Piece):
    _OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def __init__(self, color: str, location: Square):
        super().__init__(color, 1, location)
        self.has_moved = False
        self.castling_with: List[Optional[Piece]] = [None, None]

    def can_castle(self, destination: Square) -> bool:
        if not self.location.same_rank(destination):
            raise IllegalMoveError("The king can only castle along its own rank!")
        # +1: the king is moving left (towards file 0); -1: towards file 7.
        direction = 1 if self.location.file - destination.file > 0 else -1
        rook: Optional[Rook] = None
        for p in ChessBoard.get_pieces(self.color):
            if not isinstance(p, Rook) or p.location.rank != self.location.rank:
                continue
            delta = self.location.file - p.location.file
            if (delta > 0 and direction == 1) or (delta < 0 and direction == -1):
                rook = p
        if rook is None:
            raise IllegalMoveError("No valid rook exists!")
        if rook.has_moved:
            raise IllegalMoveError("Cannot castle: that rook has already moved!")
        if self.has_moved:
            raise IllegalMoveError("Cannot castle: the king has already moved!")
        if not rook.is_path_clear(self.location):
            raise IllegalMoveError("You cannot castle through your own pieces!")
        self.castling_with = [self, rook]
        return True

    def check_legal_move(self, destination: Square) -> bool:
        self._reject_ally_or_same_square(destination)
        # Castling is checked first: a two-square horizontal step.
        if self.location.file_distance(destination) == 2:
            if self.can_castle(destination):
                GameStateManager.let_me_castle(self.castling_with[0], self.castling_with[1])
                return True
        if (self.location.file_distance(destination) > self.spaces_to_move
                or self.location.rank_distance(destination) > self.spaces_to_move):
            raise IllegalMoveError("Target square is outside of the piece's movement range!")
        return True

    def get_valid_moves(self, board, current_square):
        moves = []
        for dr, df in self._OFFSETS:
            target = ChessBoard.get_square(current_square.rank + dr, current_square.file + df)
            if target is None:
                continue
            try:
                if self.check_legal_move(target):
                    moves.append(Move.from_squares(current_square, target, self.color))
            except IllegalMoveError:
                pass
        return moves


class Pawn(Piece):
    def __init__(self, color: str, location: Square):
        super().__init__(color, 2, location)
        self.has_moved = False
        # Black moves down the board (+1), White moves up (-1).
        self.direction = 1 if color.lower() == "black" else -1

    def check_legal_move(self, destination: Square) -> bool:
        self._reject_ally_or_same_square(destination)

        file_dist = destination.file - self.location.file
        rank_dist = destination.rank - self.location.rank

        # En passant: diagonal step onto an empty square.
        if abs(file_dist) == 1 and rank_dist == self.direction and not destination.is_occupied:
            if self.check_en_passant(destination):
                GameStateManager.let_me_passant()
                return True

        if file_dist == 0:                                  # straight ahead
            if rank_dist == 2 * self.direction:
                if self.has_moved:
                    raise IllegalMoveError("Pawn can only move 2 squares on its first move!")
                middle = ChessBoard.get_square(self.location.rank + self.direction, self.location.file)
                if middle.is_occupied:
                    raise IllegalMoveError("Pawn cannot jump over pieces!")
                if destination.is_occupied:
                    raise IllegalMoveError("Destination is blocked!")
                return True
            if rank_dist == self.direction:
                if destination.is_occupied:
                    raise IllegalMoveError("Pawn is blocked by another piece!")
                return True
            raise IllegalMoveError("Illegal forward movement distance!")

        if abs(file_dist) == 1 and rank_dist == self.direction:   # diagonal capture
            if destination.is_occupied:
                return True                                 # ally case was rejected above
            raise IllegalMoveError("Pawn cannot move diagonally unless capturing!")

        raise IllegalMoveError("Illegal move pattern for Pawn!")

    def check_en_passant(self, destination: Square) -> bool:
        # The victim sits on the attacker's rank and the destination's file.
        victim = ChessBoard.get_square(self.location.rank, destination.file)
        if victim is not None and isinstance(victim.piece, Pawn):
            return GameStateManager.there_is_passant and victim.equals(GameStateManager.where_passant)
        return False

    def promote(self, piece_type: int) -> Piece:
        """Retire this pawn and return its replacement (1=Queen, 2=Rook, 3=Bishop, 4=Knight)."""
        cls = {1: Queen, 2: Rook, 3: Bishop, 4: Knight}.get(piece_type, Queen)
        new_piece = cls(self.color, self.location)
        self.location = None
        return new_piece

    def get_valid_moves(self, board, current_square):
        moves = []
        offsets = [(self.direction, 0), (self.direction * 2, 0),
                   (self.direction, -1), (self.direction, 1)]
        for dr, df in offsets:
            target = ChessBoard.get_square(current_square.rank + dr, current_square.file + df)
            if target is None:
                continue
            try:
                if self.check_legal_move(target):
                    moves.append(Move.from_squares(current_square, target, self.color))
            except IllegalMoveError:
                continue
        return moves


# --------------------------------------------------------------------------
# Board
# --------------------------------------------------------------------------
class ChessBoard:
    """The 8x8 board.  There is only ever one, so state and helpers live on the class."""

    _board: List[List[Square]] = []

    def __init__(self):
        ChessBoard._board = [[Square(r, c) for c in range(8)] for r in range(8)]
        self._init_pieces()

    def _init_pieces(self) -> None:
        b = ChessBoard._board
        for i in range(8):
            b[6][i].occupy(Pawn(WHITE, b[6][i]))
            b[1][i].occupy(Pawn(BLACK, b[1][i]))
        self._setup_back_row(0, BLACK)
        self._setup_back_row(7, WHITE)

    def _setup_back_row(self, row: int, color: str) -> None:
        b = ChessBoard._board
        order = [Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]
        for col, cls in enumerate(order):
            b[row][col].occupy(cls(color, b[row][col]))

    @staticmethod
    def get_square(row: int, col: int) -> Optional[Square]:
        """The square at (row, col), or None if it is off the board."""
        if 0 <= row < 8 and 0 <= col < 8:
            return ChessBoard._board[row][col]
        return None

    @staticmethod
    def get_board() -> List[List[Square]]:
        return ChessBoard._board

    @staticmethod
    def square_exists(target: Square, rank_dis: int, file_dis: int) -> bool:
        return 0 <= target.rank + rank_dis < 8 and 0 <= target.file + file_dis < 8

    @staticmethod
    def get_pieces(color: str) -> List[Piece]:
        return [sq.piece for row in ChessBoard._board for sq in row
                if sq.piece is not None and sq.piece.color.lower() == color.lower()]

    @staticmethod
    def get_white_pieces() -> List[Piece]:
        return ChessBoard.get_pieces(WHITE)

    @staticmethod
    def get_black_pieces() -> List[Piece]:
        return ChessBoard.get_pieces(BLACK)

    @staticmethod
    def get_num_pieces() -> List[int]:
        """[white_count, black_count]"""
        return [len(ChessBoard.get_white_pieces()), len(ChessBoard.get_black_pieces())]


# --------------------------------------------------------------------------
# Move
# --------------------------------------------------------------------------
@dataclass
class Move:
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    player_color: str
    # Special-move flags (sent over the network so both sides stay in sync)
    is_en_passant: bool = False
    is_castle: bool = False
    promotion_type: int = 0      # 0: none, 1: Queen, 2: Rook, 3: Bishop, 4: Knight
    # Local only (not sent): the rook taking part in a castle
    castle_rook: Optional[Rook] = field(default=None, repr=False, compare=False)

    @classmethod
    def from_squares(cls, location: Square, destination: Square, player_color: str) -> "Move":
        return cls(location.rank, location.file, destination.rank, destination.file, player_color)

    # --- network (de)serialisation -----------------------------------------
    def to_dict(self) -> dict:
        return {
            "start_row": self.start_row, "start_col": self.start_col,
            "end_row": self.end_row, "end_col": self.end_col,
            "player_color": self.player_color,
            "is_en_passant": self.is_en_passant, "is_castle": self.is_castle,
            "promotion_type": self.promotion_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Move":
        return cls(int(d["start_row"]), int(d["start_col"]), int(d["end_row"]), int(d["end_col"]),
                   str(d["player_color"]), bool(d.get("is_en_passant", False)),
                   bool(d.get("is_castle", False)), int(d.get("promotion_type", 0)))

    # --- validation ---------------------------------------------------------
    def check_valid_move(self) -> bool:
        real_start = ChessBoard.get_square(self.start_row, self.start_col)
        real_end = ChessBoard.get_square(self.end_row, self.end_col)

        if real_start is None or real_end is None or not real_start.is_occupied:
            return False

        p = real_start.piece
        if p.color.strip().lower() != self.player_color.strip().lower():
            print("DEBUG: Wrong color turn")
            return False

        # Reset global flags before running the piece's own logic
        GameStateManager.wants_to_passant = False
        GameStateManager.wants_to_castle = False

        try:
            valid = p.check_legal_move(real_end)

            if valid and GameStateManager.wants_to_passant:
                self.is_en_passant = True
            if valid and GameStateManager.wants_to_castle:
                self.castle_rook = GameStateManager.castle_with[1]
                self.is_castle = True

            # King safety
            if isinstance(p, King):
                if GameStateManager.would_be_in_check_at(p, real_end):
                    raise IllegalMoveError("Move would put the king in check!")
            else:
                for piece in ChessBoard.get_pieces(self.player_color.strip()):
                    if isinstance(piece, King) and GameStateManager.is_in_check(piece):
                        # King is in check: this move has to resolve it
                        if not GameStateManager.would_be_in_check_after(piece, self):
                            return valid
                        raise IllegalMoveError("King is in check!")
            return valid

        except IllegalMoveError as ex:
            print("DEBUG:", ex)
            return False

    # --- execution ----------------------------------------------------------
    def execute_move(self) -> None:
        real_start = ChessBoard.get_square(self.start_row, self.start_col)
        real_end = ChessBoard.get_square(self.end_row, self.end_col)
        if real_start is None or real_end is None or not real_start.is_occupied:
            return
        p = real_start.piece

        # 1. En passant capture
        if self.is_en_passant:
            direction = 1 if p.color.lower() == "black" else -1
            victim_square = ChessBoard.get_square(self.end_row - direction, self.end_col)
            if victim_square is not None:
                victim_square.vacate()
                print("DEBUG: En Passant Deletion Successful")
            GameStateManager.wants_to_passant = False
            GameStateManager.there_is_passant = False

        # 2. Castling
        if self.is_castle:
            rook = self.castle_rook
            if rook is None:
                # Move arrived over the network: find our own copy of the rook.
                rook_file = 7 if self.end_col == 6 else 0
                candidate = ChessBoard.get_square(self.start_row, rook_file).piece
                rook = candidate if isinstance(candidate, Rook) else None

            p.location.vacate()
            real_end.occupy(p)
            p.location = real_end
            if isinstance(p, King):
                p.has_moved = True

            if rook is not None:
                rook_end_file = 5 if self.end_col == 6 else 3
                rook_end = ChessBoard.get_square(self.start_row, rook_end_file)
                rook.location.vacate()
                rook_end.occupy(rook)
                rook.location = rook_end
                rook.has_moved = True
            GameStateManager.wants_to_castle = False
            GameStateManager.there_is_passant = False

        # 3. Standard move and promotion
        else:
            if isinstance(p, Pawn):
                if abs(self.start_row - self.end_row) == 2:
                    GameStateManager.set_passant_eligible(real_end)
                else:
                    GameStateManager.there_is_passant = False
                p.has_moved = True
                if self.end_row in (0, 7) and self.promotion_type > 0:
                    p = p.promote(self.promotion_type)
            else:
                GameStateManager.there_is_passant = False

            if isinstance(p, (King, Rook)):
                p.has_moved = True

            real_end.vacate()           # captured piece (if any) leaves the board
            real_start.vacate()
            real_end.occupy(p)
            p.location = real_end

        # 4. Did that checkmate the opponent?
        enemy_color = BLACK if p.color.lower() == "white" else WHITE
        for piece in ChessBoard.get_pieces(enemy_color):
            if isinstance(piece, King):
                if GameStateManager.is_checkmate(piece):
                    GameStateManager.handle_checkmate(p.color)
                break


# --------------------------------------------------------------------------
# Game state
# --------------------------------------------------------------------------
class GameStateManager:
    """Global game state: en passant, castling flags, check/checkmate detection."""

    where_passant: Optional[Square] = None
    there_is_passant = False
    wants_to_passant = False
    wants_to_castle = False
    castle_with: List[Optional[Piece]] = [None, None]
    active_gui = None            # set by the UI; needs a checkmate_popup(winner_color) method

    # --- en passant / castling bookkeeping ---------------------------------
    @staticmethod
    def set_passant_eligible(square: Square) -> None:
        GameStateManager.where_passant = square
        GameStateManager.there_is_passant = True

    @staticmethod
    def let_me_passant() -> None:
        GameStateManager.wants_to_passant = True

    @staticmethod
    def let_me_castle(king: King, rook: Rook) -> None:
        GameStateManager.castle_with = [king, rook]
        GameStateManager.wants_to_castle = True

    # --- check detection ----------------------------------------------------
    @staticmethod
    def _enemies_of(king: King) -> List[Piece]:
        return ChessBoard.get_pieces(BLACK if king.color.lower() == "white" else WHITE)

    @staticmethod
    def is_in_check(king: King) -> bool:
        target = king.location
        for p in GameStateManager._enemies_of(king):
            try:
                if p.check_legal_move(target):
                    return True
            except IllegalMoveError:
                pass
        return False

    @staticmethod
    def would_be_in_check_at(king: King, destination: Square) -> bool:
        """Would the king be attacked if it stepped onto `destination`?"""
        victim = destination.piece
        original = king.location
        original.vacate()                    # mock the move
        destination.occupy(king)
        result = False
        for p in GameStateManager._enemies_of(king):
            if p is victim:                  # captured pieces can't give check
                continue
            try:
                if p.check_legal_move(destination):
                    result = True
                    break
            except IllegalMoveError:
                pass
        destination.occupy(victim)           # restore the board
        original.occupy(king)
        return result

    @staticmethod
    def would_be_in_check_after(king: King, move: Move) -> bool:
        """Would the king be attacked after `move` is played?"""
        start = ChessBoard.get_square(move.start_row, move.start_col)
        end = ChessBoard.get_square(move.end_row, move.end_col)
        moving, captured = start.piece, end.piece
        end.occupy(moving)                   # mock the move
        start.vacate()
        result = False
        for p in GameStateManager._enemies_of(king):
            try:
                if p.check_legal_move(king.location):
                    result = True
            except IllegalMoveError:
                pass
        start.occupy(moving)                 # restore the board (including any captured piece)
        end.occupy(captured)
        return result

    @staticmethod
    def get_attackers(king: King) -> List[Piece]:
        attackers = []
        for p in GameStateManager._enemies_of(king):
            try:
                if p.check_legal_move(king.location):
                    attackers.append(p)
            except IllegalMoveError:
                pass
        return attackers

    # --- checkmate ----------------------------------------------------------
    @staticmethod
    def is_checkmate(king: King) -> bool:
        # Checkmate = in check AND the king can't escape AND the lone attacker
        # can't be captured AND it can't be blocked.
        if not GameStateManager.is_in_check(king):
            return False
        attackers = GameStateManager.get_attackers(king)
        allies = ChessBoard.get_pieces(king.color)

        # ESCAPE: can the king move?
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == 0 and df == 0:
                    continue
                dest = ChessBoard.get_square(king.location.rank + dr, king.location.file + df)
                if dest is not None:
                    if Move.from_squares(king.location, dest, king.color).check_valid_move():
                        return False

        if len(attackers) > 1:               # double check: only a king move can help
            return True

        # CAPTURE: can we take the lone attacker?
        lone = attackers[0]
        for p in allies:
            if Move.from_squares(p.location, lone.location, p.color).check_valid_move():
                return False

        # BLOCK: can we step in front of the lone sliding attacker?
        if isinstance(lone, (Rook, Bishop, Queen)):
            kl, al = king.location, lone.location
            for row in range(8):
                for col in range(8):
                    pot = ChessBoard.get_square(row, col)
                    if pot is None or pot.is_occupied:
                        continue
                    on_path = False
                    try:
                        if (isinstance(lone, (Rook, Queen))
                                and ((kl.same_rank(pot) and al.same_rank(pot))
                                     or (kl.same_file(pot) and al.same_file(pot)))):
                            if lone.is_path_clear(kl):
                                if kl.total_distance(al) > kl.total_distance(pot):
                                    on_path = True
                        elif (isinstance(lone, (Bishop, Queen))
                              and kl.same_diagonal(pot) and al.same_diagonal(pot)):
                            if lone.is_diagonal_path_clear(kl):
                                if kl.total_distance(al) > kl.total_distance(pot):
                                    on_path = True
                    except Exception:
                        pass
                    if on_path:
                        for p in allies:
                            if isinstance(p, King):
                                continue
                            if Move.from_squares(p.location, pot, p.color).check_valid_move():
                                return False
        return True

    @staticmethod
    def handle_checkmate(winner_color: str) -> None:
        if GameStateManager.active_gui is not None:
            GameStateManager.active_gui.checkmate_popup(winner_color)
