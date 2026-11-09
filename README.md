CheckMate (Python Port)
Group: 7
Team members: Alby Garcia-Jimenez, Nicholas Tran, and Khush Patel

Project
Build CheckMate, a two-player network chess game written in Python that supports online multiplayer or playing against a random-move CPU. The application provides full move validation, a graphical interface, network serialization, and automated tests.

Module structure
Original Module	Python File
Square, Piece, Pawn, Rook, Knight, Bishop, Queen, King, ChessBoard, Move, GameStateManager	engine.py
ChessBot	bot.py
NetworkManager	network.py
ConnectionUI, GUI	ui.py
CheckMate (main)	main.py

Implementation details
Key technical implementation details and features include:

* Network protocol: Moves are sent as single-line JSON strings over TCP sockets.
* Castling mechanics: Properly identifies target rooks on the designated side and resolves them locally.
* Pawn promotion: Replaces promoted pawns cleanly upon reaching the back rank.
* Check evasion validation: Safely tests potential moves for check without mutating or destroying board state.
* State tracking: Marks pieces as moved after castling and resets en passant eligibility after every turn.
* Asset loading: File paths for piece graphics are handled case-insensitively for Linux compatibility.
* Thread safety: Network operations run asynchronously and pass UI updates safely using thread queues.

Known limitations
Planned features and current constraints include:

* CPU opponent selects random legal moves and does not evaluate check.
* Castling logic does not check if the king is passing through or moving out of check.
* Win/loss condition handling does not yet include stalemate, draws, resignation, or board flipping for Black.

Run
Requires Python 3.8+ with Tkinter (bundled on Windows/macOS; on Debian/Ubuntu: `sudo apt install python3-tk`). Install optional image dependencies and run:

pip install -r requirements.txt     # Pillow, for piece images (optional)
python main.py

Without Pillow, pieces render using Unicode chess symbols. To play online, one player selects **Host Game** (port 1234) and the second player enters the host's IP address to **Join Friend**.

Tests
Run the automated test suite for engine rules and network round trips (no GUI required):

python -m unittest -v

This is a learning project and is not intended for production use.
