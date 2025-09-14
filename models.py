from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # If a player can be in multiple games, keep this relationship.
    sessions = db.relationship(
        "GameSession",
        back_populates="player",
        cascade="all, delete-orphan"
    )


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default="waiting")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    max_players = db.Column(db.Integer, default=2)

    players = db.relationship(
        "GameSession",
        back_populates="game",
        cascade="all, delete-orphan"   # 🔑 delete sessions when game is deleted
    )


class GameSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_token = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))

    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)

    player = db.relationship("Player", back_populates="sessions")
    game = db.relationship("Game", back_populates="players")
