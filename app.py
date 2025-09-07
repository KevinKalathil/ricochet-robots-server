import random
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, send
from models import db, Player, Game, GameSession

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
        socketio.emit("game_start", {
            "game_id": game.id,
            "players": [p.player.username for p in game.players], 
            "board": generate_board()
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

# ----------------------------
# Run server
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)
