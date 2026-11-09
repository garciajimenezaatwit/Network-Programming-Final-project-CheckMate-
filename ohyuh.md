# CheckMate (Python port)

Chess for two players over a network, or against a random-move CPU.
Original authors: Alby Garcia-Jimenez,Nicholas Tran, Khush Patel.

## Run

    pip install -r requirements.txt     # Pillow, for the piece images (optional)
    python main.py

Needs Python 3.8+ with Tkinter (bundled with Python on Windows/macOS;
on Debian/Ubuntu: `sudo apt install python3-tk`).

Without Pillow the pieces are drawn as Unicode chess symbols.
To play online, one player picks **Host Game** (port 1234) and the other
enters the host's IP and picks **Join Friend**.

## Tests

    python -m unittest -v        # engine rules + network round trip, no display needed

## Where the Java classes went

| Java                                                                  | Python        |
|-----------------------------------------------------------------------|---------------|
| Square, Piece, Pawn, Rook, Knight, Bishop, Queen, King, ChessBoard, Move, GameStateManager | `engine.py` |
| ChessBot                                                              | `bot.py`      |
| NetworkManager                                                        | `network.py`  |
| ConnectionUI, GUI                                                     | `ui.py`       |
| CheckMate (main)                                                      | `main.py`     |

## Differences from the Java version

* **Network protocol:** moves are sent as one line of JSON instead of Java object serialization.
  (This means the Python version can't talk to the Java one.)
* **Castling** now works. The Java `canCastle` threw "no valid rook" whenever both rooks were
  still on the board, so castling was effectively impossible. It now picks the rook on the
  side the king moves toward, and the rook is looked up locally on the receiving player's board.
* **Promotion** now works. In Java the new piece was placed and then immediately overwritten by
  the old pawn, so pawns never actually changed.
* **Check evasion** no longer deletes a captured piece from the board while testing a move
  (`wouldBeInCheck(King, Move)` used to clear the destination square afterwards).
* After castling the king is marked as having moved, and en passant eligibility is cleared.
* Piece images are found case-insensitively (`WhiteKing.png` vs `whiteKing.png`), so they load on Linux too.
* Tk isn't thread-safe, so network and connect threads hand results to the UI through a queue.

## Known limitations (carried over from the Java version)

* The CPU picks random moves that follow piece movement rules but ignore check.
* Castling doesn't verify the king isn't castling out of or through check.
* No stalemate, draw, or resignation handling; the board is never flipped for Black.
