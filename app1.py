from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, Player, Game, GameSession
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///game.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

socketio = SocketIO(app)

with app.app_context():
    db.create_all()   # create tables

@app.route("/join", methods=["POST"])
def join_game():
    username = request.args.get("username")  # <- changed here

    # Create or find player
    player = Player.query.filter_by(username=username).first()
    if not player:
        print("Creating new player")
        player = Player(username=username)
        db.session.add(player)
        db.session.commit()

    # Find open game
    games = Game.query.filter_by(status="waiting").all()
    print('waiting games:', games)

    for g in games:
        print('game:', g, 'players:', g.players)

    game = next((g for g in games if len(g.players) < g.max_players), None)

    print('selected game:', game)
    if not game:
        game = Game()
        db.session.add(game)

    # Assign player only if not already assigned
    session = GameSession.query.filter_by(player_id=player.id, game_id=game.id).first()
    if not session:
        # Assign player
        session = GameSession(player_id=player.id, game_id=game.id)
        db.session.add(session)
        db.session.commit()  # Commit so game.players is updated

    if len(game.players) >= game.max_players:
        game.status = "active"

    db.session.commit()

    return jsonify({
        "game_id": game.id,
        "session_token": session.session_token,
        "status": game.status
    })

@socketio.on("connect")
def handle_connect():
    print("Client connected")
    emit("server_msg", {"message": "Welcome!"})

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)   # <-- THIS starts the Flask dev server