"""
database.py — SQLite 對局紀錄
紀錄每局開始/結束時間、勝者、雙方分數、難度
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "splendor.db")


def init_db():
    """初始化資料庫，建立對局記錄表"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id     TEXT UNIQUE NOT NULL,
            mode        TEXT NOT NULL,
            difficulty  TEXT,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            winner_id   INTEGER,
            score_p0    INTEGER,
            score_p1    INTEGER,
            turns       INTEGER
        )
    """)
    con.commit()
    con.close()


def record_game_start(game_id: str, mode: str, difficulty: str):
    """記錄對局開始"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO games (game_id, mode, difficulty, started_at)
        VALUES (?, ?, ?, ?)
    """, (game_id, mode, difficulty, datetime.utcnow().isoformat()))
    con.commit()
    con.close()


def record_game_end(game_id: str, winner_id: int,
                    score_p0: int, score_p1: int, turns: int):
    """記錄對局結束"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        UPDATE games
        SET ended_at=?, winner_id=?, score_p0=?, score_p1=?, turns=?
        WHERE game_id=?
    """, (datetime.utcnow().isoformat(), winner_id, score_p0, score_p1, turns, game_id))
    con.commit()
    con.close()


def get_history(limit: int = 20) -> list[dict]:
    """取得最近 limit 筆對局紀錄"""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT * FROM games
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    con.close()
    return rows
