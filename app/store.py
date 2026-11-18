"""Local SQLite persistence: chat history and pronunciation progress."""
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, session TEXT, role TEXT, content TEXT, lang TEXT, mode TEXT, ts REAL);
CREATE INDEX IF NOT EXISTS ix_msg_session ON messages(session, id);
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY, target TEXT, lang TEXT, overall INTEGER, heard TEXT, tips TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS word_scores(
  attempt_id INTEGER, word TEXT, lang TEXT, score INTEGER);
CREATE INDEX IF NOT EXISTS ix_ws_word ON word_scores(word, lang);
"""


class Store:
    def __init__(self, path=None):
        self.path = str(path or config.DB_PATH)
        if self.path != ":memory:":
            config.DATA.mkdir(parents=True, exist_ok=True)
        self._mem = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = self._mem or sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            if not self._mem:
                conn.close()

    # chat ------------------------------------------------------------------
    def add_message(self, session: str, role: str, content: str, lang: str, mode: str):
        with self._conn() as c:
            c.execute("INSERT INTO messages(session, role, content, lang, mode, ts) VALUES(?,?,?,?,?,?)",
                      (session, role, content, lang, mode, time.time()))

    def history(self, session: str, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT role, content, lang, mode, ts FROM messages WHERE session=? "
                             "ORDER BY id DESC LIMIT ?", (session, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear(self, session: str):
        with self._conn() as c:
            c.execute("DELETE FROM messages WHERE session=?", (session,))

    # practice ----------------------------------------------------------------
    def add_attempt(self, target: str, lang: str, result: dict) -> int:
        with self._conn() as c:
            cur = c.execute("INSERT INTO attempts(target, lang, overall, heard, tips, ts) VALUES(?,?,?,?,?,?)",
                            (target, lang, result["overall"], result["heard"],
                             json.dumps(result.get("tips", [])), time.time()))
            c.executemany("INSERT INTO word_scores VALUES(?,?,?,?)",
                          [(cur.lastrowid, w["word"].lower(), lang, w["score"]) for w in result["words"]])
            return cur.lastrowid

    def progress(self, recent: int = 20) -> dict:
        with self._conn() as c:
            total, avg = c.execute("SELECT COUNT(*), AVG(overall) FROM attempts").fetchone()
            rows = c.execute("SELECT target, lang, overall, ts FROM attempts ORDER BY id DESC LIMIT ?",
                             (recent,)).fetchall()
            weak = c.execute(
                "SELECT word, lang, ROUND(AVG(score)) AS avg, COUNT(*) AS n FROM word_scores "
                "GROUP BY word, lang HAVING AVG(score) < 80 ORDER BY AVG(score) LIMIT 15").fetchall()
        return {"attempts": total, "average": round(avg or 0),
                "recent": [dict(r) for r in reversed(rows)], "weak_words": [dict(r) for r in weak]}
