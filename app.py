import random
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, send, close_room
from models import db, Player, Game, GameSession
from collections import deque
from typing import List, Tuple, Optional, Dict

# ----------------------------
# Flask + DB + SocketIO Setup
# ----------------------------
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///game.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")  # allow CORS for testing

with app.app_context():
    db.create_all()

# ----------------------------
# Random username generator
# ----------------------------
ADJECTIVES = ["Fast", "Red", "Clever", "Sneaky", "Brave", "Quick", "Fuzzy"]
NOUNS = ["Tiger", "Robot", "Wizard", "Ninja", "Eagle", "Panther", "Fox"]

def generate_unique_username():
    while True:
        adj = random.choice(ADJECTIVES)
        noun = random.choice(NOUNS)
        number = random.randint(0, 9999)
        username = f"{adj}{noun}{number:04d}"

        # Ensure uniqueness in DB
        existing = Player.query.filter_by(username=username).first()
        if not existing:
            return username

# Directions (dx, dy) and name
DIRECTIONS = {
    "Down": (0, 1),
    "Up": (0, -1),
    "Left": (-1, 0),
    "Right": (1, 0),
}

def is_blocked_by_wall(grid: List[List[int]], x: int, y: int, dx: int, dy: int) -> bool:
    """
    Return True if movement from (x,y) to (x+dx, y+dy) is blocked by a wall (either current cell or target cell).
    grid[y][x] uses bitmask: 1=N, 2=E, 4=S, 8=W
    """
    rows = len(grid)
    cols = len(grid[0])
    nx, ny = x + dx, y + dy
    # out of bounds treated as blocked
    if not (0 <= nx < cols and 0 <= ny < rows):
        return True

    # moving Up (dy == -1): blocked if current has North or target has South
    if dx == 0 and dy == -1:
        return (grid[y][x] & 1) != 0 or (grid[ny][nx] & 4) != 0
    # moving Down (dy == 1): blocked if current has South or target has North
    if dx == 0 and dy == 1:
        return (grid[y][x] & 4) != 0 or (grid[ny][nx] & 1) != 0
    # moving Right (dx == 1): blocked if current has East or target has West
    if dx == 1 and dy == 0:
        return (grid[y][x] & 2) != 0 or (grid[ny][nx] & 8) != 0
    # moving Left (dx == -1): blocked if current has West or target has East
    if dx == -1 and dy == 0:
        return (grid[y][x] & 8) != 0 or (grid[ny][nx] & 2) != 0

    return True  # fallback: block

def slide_until_block(grid: List[List[int]], start: Tuple[int,int],
                     dx: int, dy: int, occupied: set) -> Tuple[int,int]:
    """
    Slide from start (x,y) along (dx,dy) until the next cell would be blocked by wall or occupied.
    Return final (x,y).
    """
    x, y = start
    rows = len(grid)
    cols = len(grid[0])

    while True:
        nx, ny = x + dx, y + dy
        # stop if out of bounds or wall between current and next
        if not (0 <= nx < cols and 0 <= ny < rows):
            break
        if is_blocked_by_wall(grid, x, y, dx, dy):
            break
        # stop if occupied (there is a robot at next cell)
        if (nx, ny) in occupied:
            break
        # otherwise move to nx,ny and continue
        x, y = nx, ny

    return (x, y)

def encode_positions(positions: List[Tuple[int,int]]) -> Tuple[Tuple[int,int], ...]:
    """Canonical encoding for visited set"""
    return tuple(positions)

def solve_board(board: Dict, rows = 10, cols = 10) -> Optional[List[Dict]]:
    """
    BFS solver.
    board: dict with keys: 'rows','cols','grid' (2D int list), 'robots' (list of [y,x]),
           'target' (y,x)
    Returns list of moves: [{ 'robot': i, 'dir': 'Right', 'to': [y,x] }, ...] or None.
    """
    grid = board["grid"]
    robots = [tuple(r) for r in board["robots"]]  # list of (y, x)
    target = tuple(board["target"])               # (y,x)
    num_robots = len(robots)

    # BFS queue: each node = (positions_list, moves_list)
    start_positions = robots
    start_key = encode_positions(start_positions)

    q = deque()
    q.append((start_positions, []))
    visited = {start_key}

    while q:
        positions, moves = q.popleft()

        # check if any robot at target
        if any(pos == target for pos in positions):
            # return moves as sequence of dicts
            return moves

        # for each robot, try sliding in each direction
        for ridx in range(num_robots):
            for dname, (dx, dy) in DIRECTIONS.items():
                occupied = set(positions)  # set of occupied cells
                start = positions[ridx]
                new_pos = slide_until_block(grid, start, dx, dy, occupied)

                # if no movement, skip
                if new_pos == start:
                    continue

                # build new positions list
                new_positions = list(positions)
                new_positions[ridx] = new_pos
                key = encode_positions(new_positions)
                if key in visited:
                    continue
                visited.add(key)

                # append move record
                move_record = {
                    "robot": ridx,
                    "dir": dname,
                    "to": [new_pos[0], new_pos[1]]
                }
                q.append((new_positions, moves + [move_record]))

    # no solution
    return None


def generate_board(rows=10, cols=10, num_robots=3, wall_prob=0.1):
    grid = [[0 for _ in range(cols)] for _ in range(rows)]

    # Add random walls + borders
    for y in range(rows):
        for x in range(cols):
            cell = 0
            # North wall
            if y == 0 or random.random() < wall_prob:
                cell |= 1
            # East wall
            if x == cols - 1:
                cell |= 2
            # South wall
            if y == rows - 1:
                cell |= 4
            # West wall
            if x == 0 or random.random() < wall_prob:
                cell |= 8
            grid[y][x] = cell

    # Place robots randomly
    robots = []
    for _ in range(num_robots):
        while True:
            rx, ry = random.randrange(cols), random.randrange(rows)
            if (rx, ry) not in robots:  # don't stack robots
                robots.append((rx, ry))
                break

    # Place target at least distance 3 from any robot
    while True:
        tx, ty = random.randrange(cols), random.randrange(rows)
        if all(abs(tx - rx) + abs(ty - ry) >= 3 for (rx, ry) in robots):
            target = (tx, ty)
            break

    return {
        "rows": rows,
        "cols": cols,
        "grid": grid,       # 2D wall bitmask array
        "robots": robots,   # list of robot coords
        "target": target,   # (x,y) target position
    }    

# ----------------------------
# Socket: join game
# ----------------------------
@socketio.on("join_game")
def handle_join_game(data):
    """
    Client emits: { "username": "Kevin" } (optional)
    """
    print("handling join_game with data:", data)
    username = data.get("username")
    if not username:
        username = generate_unique_username()

    # 1️⃣ Create/find player
    player = Player.query.filter_by(username=username).first()
    if not player:
        player = Player(username=username)
        db.session.add(player)
        db.session.commit()

    # 2️⃣ Find waiting game
    waiting_games = Game.query.filter_by(status="waiting").all()
    game = next((g for g in waiting_games if len(g.players) < g.max_players), None)
    if not game:
        game = Game(status="waiting")
        db.session.add(game)
        db.session.commit()

    # 3️⃣ Create session if not exists
    session = GameSession.query.filter_by(player_id=player.id, game_id=game.id).first()
    if not session:
        session = GameSession(player_id=player.id, game_id=game.id)
        db.session.add(session)
        db.session.commit()

    # 4️⃣ Join the socket room
    room = f"game_{game.id}"
    join_room(room)
    # send({"message": f"{username} joined the game!"}, to=room)
    emit("server_msg", {"message": f"{username} joined the game!"}, room=room)

    # 5️⃣ Count sockets in the room
    participants = socketio.server.manager.get_participants("/", room)
    count = len(list(participants))

    # 6️⃣ Emit waiting or start
    if count >= game.max_players and game.status != "active":
        print("Starting game", game.id, "with players:", [p.player.username for p in game.players])
        game.status = "active"
        db.session.commit()

        # Keep generating until solvable
        while True:
            board = generate_board()
            solution = solve_board(board)
            if solution:  # non-empty solution found
                break
        
        print("Generated board with solution:", solution)
        print("Board:", board)

        socketio.emit("game_start", {
            "game_id": game.id,
            "players": [p.player.username for p in game.players],
            "board": board,
            "solution": solution
        }, room=room)
    else:
        print(f"Waiting for more players in game {game.id}: {count}/{game.max_players}")
        emit("game_waiting", {
            "game_id": game.id,
            "username": username,
            "players_connected": count,
            "players_needed": max(0, game.max_players - count)
        })

# ----------------------------
# Socket: move events
# ----------------------------
@socketio.on("move")
def handle_move(data):
    game_id = data.get("game_id")
    move = data.get("move")
    room = f"game_{game_id}"
    emit("game_update", {"move": move}, room=room)

# ----------------------------
# Socket: connect
# ----------------------------
@socketio.on("connect")
def handle_connect():
    emit("server_msg", {"message": "Welcome!"})

@socketio.on("leave_game")
def handle_leave_game(data):
    game_id = data.get("game_id")
    username = data.get("username")
    room = f"game_{game_id}"
    print(f"{username} leaving game {game_id}, room {room}")
    
    # Announce to everyone still connected
    emit("server_msg", {"message": f"{username} has left the game."}, room=room)

    # End the game completely
    game = db.session.get(Game, game_id)
    if game:
        db.session.delete(game)  # this should cascade delete sessions + players if you configure it
        db.session.commit()

    # Notify clients to clean up
    emit("end_game", {"message": "Game ended due to player leaving."}, room=room)
    close_room(room)




@socketio.on("disconnect")
def handle_disconnect(data):
    print("Client disconnected")
    emit("server_msg", {"message": f"A user has disconnected. {data}"}, broadcast=True)

# ----------------------------
# Run server
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)
