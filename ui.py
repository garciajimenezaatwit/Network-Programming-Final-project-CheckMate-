"""Tkinter user interface (port of ConnectionUI.java and GUI.java)."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from bot import ChessBot
from engine import ChessBoard, GameStateManager, Move, Pawn
from network import NetworkManager

try:                                   # Pillow gives smooth image scaling
    from PIL import Image, ImageTk
    _RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS
except ImportError:                    # fall back to text glyphs
    Image = ImageTk = None

PORT = 1234
SQUARE_SIZE = 75
IMAGE_SIZE = 65
IMAGE_DIR = Path(__file__).resolve().parent / "images"
LIGHT_SQUARE, DARK_SQUARE = "white", "#404040"

_GLYPHS = {
    ("white", "King"): "\u2654", ("white", "Queen"): "\u2655", ("white", "Rook"): "\u2656",
    ("white", "Bishop"): "\u2657", ("white", "Knight"): "\u2658", ("white", "Pawn"): "\u2659",
    ("black", "King"): "\u265a", ("black", "Queen"): "\u265b", ("black", "Rook"): "\u265c",
    ("black", "Bishop"): "\u265d", ("black", "Knight"): "\u265e", ("black", "Pawn"): "\u265f",
}


# --------------------------------------------------------------------------
# Connection screen
# --------------------------------------------------------------------------
class ConnectionUI:
    def __init__(self, root: tk.Tk, nm: NetworkManager):
        self.root = root
        self.nm = nm
        self._events: "queue.Queue[tuple]" = queue.Queue()

        root.title("CheckMate Online")
        root.geometry("350x250")
        self.frame = tk.Frame(root)
        self.frame.pack(expand=True, fill="both", padx=20, pady=10)

        tk.Label(self.frame, text="Enter Host IP (Join only):").pack(pady=(5, 0))
        self.ip_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(self.frame, textvariable=self.ip_var, justify="center").pack(fill="x", pady=4)
        tk.Button(self.frame, text=f"Host Game (Port {PORT})", command=self._host).pack(fill="x", pady=2)
        tk.Button(self.frame, text="Join Friend", command=self._join).pack(fill="x", pady=2)
        tk.Button(self.frame, text="Play vs CPU (Offline)", bg="#dcdcdc",
                  command=lambda: self._start_game(True, True)).pack(fill="x", pady=2)
        self.status = tk.Label(self.frame, text="", fg="gray30")
        self.status.pack(pady=4)

        root.protocol("WM_DELETE_WINDOW", root.destroy)
        self._poll()

    # Network calls block, so they run on a worker thread and report back through a queue
    # (Tk widgets must only be touched from the main thread).
    def _host(self) -> None:
        self.status.config(text=f"Waiting for opponent on port {PORT}...")

        def work():
            try:
                self.nm.start_as_host(PORT)
                self._events.put(("start", True, False))
            except Exception as exc:
                print(exc)
                self._events.put(("error", f"Port {PORT} is busy."))
        threading.Thread(target=work, daemon=True).start()

    def _join(self) -> None:
        ip = self.ip_var.get().strip()
        self.status.config(text=f"Connecting to {ip}...")

        def work():
            try:
                self.nm.start_as_guest(ip, PORT)
                self._events.put(("start", False, False))
            except Exception as exc:
                print(exc)
                self._events.put(("error", "Could not connect."))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:
        if not self.frame.winfo_exists():
            return
        try:
            while True:
                event = self._events.get_nowait()
                if event[0] == "start":
                    self._start_game(event[1], event[2])
                    return
                self.status.config(text="")
                messagebox.showinfo("CheckMate", event[1], parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _start_game(self, is_white: bool, is_bot: bool) -> None:
        self.frame.destroy()
        board = ChessBoard()
        GameStateManager.active_gui = GUI(self.root, board, self.nm, is_white, is_bot)


# --------------------------------------------------------------------------
# Game window
# --------------------------------------------------------------------------
class GUI:
    def __init__(self, root: tk.Tk, board: ChessBoard, nm: NetworkManager,
                 is_white: bool, is_bot: bool):
        self.root = root
        self.board = board
        self.nm = nm
        self.is_bot = is_bot
        self.my_turn = is_white
        self.color = "White" if is_white else "Black"
        self.selected = None                 # (row, col) of the selected piece
        self._closed = False
        self._incoming: "queue.Queue" = queue.Queue()
        self.images = {}

        self._preload_images()

        root.title(f"CheckMate - {self.color}")
        size = SQUARE_SIZE * 8
        root.geometry(f"{size}x{size}")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=size, height=size, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)
        self._draw()

        if not is_bot and nm is not None:
            self._start_listening()
            self._poll_incoming()

    # --- images -------------------------------------------------------------
    def _preload_images(self) -> None:
        # File names are matched case-insensitively ("WhiteKing.png" vs "whiteKing.png"),
        # since the Java original relied on a case-insensitive file system.
        files = {p.name.lower(): p for p in IMAGE_DIR.glob("*.png")} if IMAGE_DIR.is_dir() else {}
        if Image is None:
            print("Pillow is not installed; using text glyphs for the pieces.")
            return
        for color in ("black", "white"):
            for piece in ("Pawn", "Rook", "Knight", "Bishop", "Queen", "King"):
                name = f"{color}{piece}.png"
                path = files.get(name.lower())
                try:
                    img = Image.open(path).convert("RGBA").resize((IMAGE_SIZE, IMAGE_SIZE), _RESAMPLE)
                    self.images[name] = ImageTk.PhotoImage(img)
                except Exception:
                    print("Could not load image:", name)

    # --- drawing ------------------------------------------------------------
    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        for r in range(8):
            for f in range(8):
                x0, y0 = f * SQUARE_SIZE, r * SQUARE_SIZE
                c.create_rectangle(x0, y0, x0 + SQUARE_SIZE, y0 + SQUARE_SIZE,
                                   fill=LIGHT_SQUARE if (r + f) % 2 == 0 else DARK_SQUARE,
                                   outline="black")
                piece = ChessBoard.get_square(r, f).piece
                if piece is None:
                    continue
                cx, cy = x0 + SQUARE_SIZE // 2, y0 + SQUARE_SIZE // 2
                name = type(piece).__name__
                img = self.images.get(f"{piece.color.lower()}{name}.png")
                if img is not None:
                    c.create_image(cx, cy, image=img)
                else:
                    c.create_text(cx, cy, text=_GLYPHS[(piece.color.lower(), name)], font=("Arial", 40),
                                  fill="#1e88e5" if piece.color.lower() == "white" else "#c62828")
        if self.selected is not None:
            r, f = self.selected
            c.create_rectangle(f * SQUARE_SIZE + 2, r * SQUARE_SIZE + 2,
                               (f + 1) * SQUARE_SIZE - 2, (r + 1) * SQUARE_SIZE - 2,
                               outline="red", width=3)

    # --- input --------------------------------------------------------------
    def _on_click(self, event) -> None:
        r, f = event.y // SQUARE_SIZE, event.x // SQUARE_SIZE
        if not self.my_turn or not (0 <= r < 8 and 0 <= f < 8):
            return

        if self.selected is None:
            square = ChessBoard.get_square(r, f)
            # Only select one of your own pieces
            if square.is_occupied and square.piece.color.lower() == self.color.lower():
                self.selected = (r, f)
        else:
            start_sq = ChessBoard.get_square(*self.selected)
            move = Move.from_squares(start_sq, ChessBoard.get_square(r, f), self.color)
            self.selected = None

            if move.check_valid_move():
                if isinstance(start_sq.piece, Pawn) and r in (0, 7):
                    move.promotion_type = self._prompt_promotion()

                self.my_turn = False
                if not self.is_bot and self.nm is not None:
                    self.nm.send_move(move)

                self._apply_move_locally(move)

                if self.is_bot and not self._closed:
                    self.root.after(700, self._trigger_bot_move)
        if not self._closed:
            self._draw()

    def _prompt_promotion(self) -> int:
        """Modal dialog; returns 1=Queen, 2=Rook, 3=Bishop, 4=Knight (Queen if closed)."""
        choice = tk.IntVar(value=1)
        dialog = tk.Toplevel(self.root)
        dialog.title("Promotion")
        dialog.transient(self.root)
        tk.Label(dialog, text="Promote Pawn to:").pack(padx=20, pady=10)
        row = tk.Frame(dialog)
        row.pack(padx=20, pady=(0, 15))
        for value, label in enumerate(("Queen", "Rook", "Bishop", "Knight"), start=1):
            tk.Button(row, text=label, width=8,
                      command=lambda v=value: (choice.set(v), dialog.destroy())).pack(side="left", padx=3)
        dialog.grab_set()
        self.root.wait_window(dialog)
        return choice.get()

    # --- applying moves -----------------------------------------------------
    def _apply_move_locally(self, move: Move) -> None:
        move.execute_move()          # may end the game via checkmate_popup()
        if not self._closed:
            self._draw()

    def _trigger_bot_move(self) -> None:
        if self._closed:
            return
        bot_color = "Black" if self.color.lower() == "white" else "White"
        move = ChessBot().generate_random_move(self.board, bot_color)
        if move is not None:
            start = ChessBoard.get_square(move.start_row, move.start_col)
            if isinstance(start.piece, Pawn) and move.end_row in (0, 7):
                move.promotion_type = 1            # the bot always promotes to a Queen
            self._apply_move_locally(move)
        self.my_turn = True

    # --- network ------------------------------------------------------------
    def _start_listening(self) -> None:
        def listen():
            try:
                while True:
                    self._incoming.put(self.nm.receive_move())
            except Exception:
                print("Network connection closed.")
        threading.Thread(target=listen, daemon=True).start()

    def _poll_incoming(self) -> None:
        if self._closed:
            return
        try:
            while True:
                self._apply_move_locally(self._incoming.get_nowait())
                self.my_turn = True
        except queue.Empty:
            pass
        if not self._closed:
            self.root.after(50, self._poll_incoming)

    # --- game over ----------------------------------------------------------
    def checkmate_popup(self, winner_color: str) -> None:
        messagebox.showinfo("Checkmate", f"GAME OVER! {winner_color} Won!", parent=self.root)
        self._closed = True
        self.root.destroy()
