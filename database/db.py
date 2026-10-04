"""aiosqlite asosidagi ma'lumotlar bazasi qatlami.

Har bir bot (Parent va har bir Child) o'zining alohida .db fayliga ega:
    data/main.db      - asosiy bot (+ sub-botlar ro'yxati `bots` jadvalida)
    data/bot_<id>.db  - har bir sub-bot uchun
"""
import re
from typing import Any, Optional

import aiosqlite

TABLES = {"movie": "movies", "series": "series"}
COLS = {
    "movie": {"code", "title", "genre", "year", "lang", "quality", "description",
              "poster", "file_id", "file_type"},
    "series": {"code", "title", "genre", "year", "lang", "quality", "description", "poster"},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP, last_seen TEXT, blocked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS channels(
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, title TEXT, link TEXT,
    kind TEXT NOT NULL, UNIQUE(chat_id, kind));
CREATE TABLE IF NOT EXISTS movies(
    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    title TEXT NOT NULL, genre TEXT, year INTEGER, lang TEXT, quality TEXT, description TEXT,
    poster TEXT, file_id TEXT, file_type TEXT DEFAULT 'video', views INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS series(
    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    title TEXT NOT NULL, genre TEXT, year INTEGER, lang TEXT, quality TEXT, description TEXT,
    poster TEXT, views INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS episodes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    season INTEGER NOT NULL, episode INTEGER NOT NULL,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE, file_id TEXT, file_type TEXT DEFAULT 'video',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(series_id, season, episode));
CREATE TABLE IF NOT EXISTS favorites(
    user_id INTEGER, kind TEXT, item_id INTEGER, PRIMARY KEY(user_id, kind, item_id));
CREATE TABLE IF NOT EXISTS ratings(
    user_id INTEGER, kind TEXT, item_id INTEGER, score INTEGER, PRIMARY KEY(user_id, kind, item_id));
CREATE TABLE IF NOT EXISTS bots(
    id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE, username TEXT, owner_id INTEGER,
    active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


class Database:
    def __init__(self, path):
        self.path = str(path)
        self.conn: Optional[aiosqlite.Connection] = None

    # ------------------------------------------------------------ core
    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        # Unicode (kirill/lotin) uchun registrga bog'liq bo'lmagan qidiruv
        await self.conn.create_function("lower_u", 1, lambda s: s.lower() if isinstance(s, str) else s)
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def fetchall(self, sql: str, params=()) -> list[dict]:
        cur = await self.conn.execute(sql, tuple(params))
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def fetchone(self, sql: str, params=()) -> Optional[dict]:
        rows = await self.fetchall(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql: str, params=()) -> int:
        cur = await self.conn.execute(sql, tuple(params))
        await self.conn.commit()
        last = cur.lastrowid
        await cur.close()
        return last

    async def scalar(self, sql: str, params=()) -> Any:
        row = await self.fetchone(sql, params)
        return list(row.values())[0] if row else None

    # -------------------------------------------------------- settings
    async def get_setting(self, key: str, default: Any = None):
        row = await self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str):
        await self.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))

    # ----------------------------------------------------------- users
    async def upsert_user(self, user_id: int, full_name: str, username: Optional[str]):
        await self.execute(
            "INSERT INTO users(user_id,full_name,username,last_seen) VALUES(?,?,?,CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, "
            "username=excluded.username, last_seen=CURRENT_TIMESTAMP, blocked=0",
            (user_id, full_name, username))

    async def user_ids(self) -> list[int]:
        return [r["user_id"] for r in await self.fetchall("SELECT user_id FROM users WHERE blocked=0")]

    async def mark_blocked(self, user_id: int):
        await self.execute("UPDATE users SET blocked=1 WHERE user_id=?", (user_id,))

    # ---------------------------------------------------------- admins
    async def add_admin(self, user_id: int):
        await self.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (user_id,))

    async def remove_admin(self, user_id: int):
        await self.execute("DELETE FROM admins WHERE user_id=?", (user_id,))

    async def is_admin(self, user_id: int) -> bool:
        return await self.fetchone("SELECT 1 FROM admins WHERE user_id=?", (user_id,)) is not None

    async def list_admins(self) -> list[int]:
        return [r["user_id"] for r in await self.fetchall("SELECT user_id FROM admins")]

    # -------------------------------------------------------- channels
    async def add_channel(self, chat_id: int, title: str, link: str, kind: str):
        await self.execute("INSERT OR REPLACE INTO channels(chat_id,title,link,kind) VALUES(?,?,?,?)",
                           (chat_id, title, link, kind))

    async def list_channels(self, kind: str) -> list[dict]:
        return await self.fetchall("SELECT * FROM channels WHERE kind=? ORDER BY id", (kind,))

    async def delete_channel(self, ch_id: int):
        await self.execute("DELETE FROM channels WHERE id=?", (ch_id,))

    # ----------------------------------------------- movies / series
    async def add_item(self, kind: str, **f) -> int:
        cols = [k for k in f if k in COLS[kind] and f[k] is not None]
        sql = f"INSERT INTO {TABLES[kind]} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        return await self.execute(sql, [f[c] for c in cols])

    async def get_item(self, kind: str, item_id: int) -> Optional[dict]:
        return await self.fetchone(f"SELECT * FROM {TABLES[kind]} WHERE id=?", (item_id,))

    async def update_item(self, kind: str, item_id: int, field: str, value):
        if field not in COLS[kind]:
            raise ValueError("Noto'g'ri maydon")
        await self.execute(f"UPDATE {TABLES[kind]} SET {field}=? WHERE id=?", (value, item_id))

    async def delete_item(self, kind: str, item_id: int):
        if kind == "series":
            await self.execute("DELETE FROM episodes WHERE series_id=?", (item_id,))
        await self.execute("DELETE FROM favorites WHERE kind=? AND item_id=?", (kind, item_id))
        await self.execute("DELETE FROM ratings WHERE kind=? AND item_id=?", (kind, item_id))
        await self.execute(f"DELETE FROM {TABLES[kind]} WHERE id=?", (item_id,))

    async def list_items(self, kind: str, limit: int = 500) -> list[dict]:
        rows = await self.fetchall(
            f"SELECT id,title,year,code,views,created_at FROM {TABLES[kind]} ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["kind"] = kind
        return rows

    async def find_code(self, code: str):
        """Kod bo'yicha kino / serial / qismni topadi -> (kind, row) yoki (None, None)."""
        code = code.strip()
        for kind, table in (("movie", "movies"), ("series", "series"), ("episode", "episodes")):
            row = await self.fetchone(f"SELECT * FROM {table} WHERE code=?", (code,))
            if row:
                return kind, row
        return None, None

    async def code_exists(self, code: str) -> bool:
        return (await self.find_code(code))[1] is not None

    async def next_code(self) -> str:
        rows = await self.fetchall("SELECT code FROM movies UNION ALL SELECT code FROM series "
                                   "UNION ALL SELECT code FROM episodes")
        nums = [int(r["code"]) for r in rows if str(r["code"]).isdigit()]
        return str(max(nums, default=0) + 1)

    async def search(self, mode: str, q: str = "", limit: int = 200) -> list[dict]:
        out = []
        for kind, table in TABLES.items():
            where, params, order = "1=1", [], "created_at DESC, id DESC"
            if mode == "text":
                parts = []
                for w in q.lower().split():
                    parts.append("(lower_u(title) LIKE ? OR lower_u(IFNULL(genre,'')) LIKE ?)")
                    params += [f"%{w}%", f"%{w}%"]
                where = " AND ".join(parts) or "1=0"
            elif mode == "genre":
                where, params = "lower_u(IFNULL(genre,'')) LIKE ?", [f"%{q.lower()}%"]
            elif mode == "year":
                where, params = "year=?", [int(q)]
            elif mode == "top":
                order = "views DESC"
            rows = await self.fetchall(
                f"SELECT id,title,year,code,views,created_at FROM {table} WHERE {where} "
                f"ORDER BY {order} LIMIT ?", params + [limit])
            for r in rows:
                r["kind"] = kind
            out += rows
        out.sort(key=lambda r: r["views"] if mode == "top" else r["created_at"], reverse=True)
        return out[:limit]

    async def genres(self) -> list[str]:
        rows = await self.fetchall("SELECT genre FROM movies WHERE genre IS NOT NULL "
                                   "UNION ALL SELECT genre FROM series WHERE genre IS NOT NULL")
        seen = {}
        for r in rows:
            for g in re.split(r"[,/]", r["genre"]):
                g = g.strip()
                if g:
                    seen.setdefault(g.lower(), g[:1].upper() + g[1:])
        return sorted(seen.values())

    async def years(self) -> list[int]:
        rows = await self.fetchall("SELECT year FROM movies WHERE year IS NOT NULL UNION "
                                   "SELECT year FROM series WHERE year IS NOT NULL ORDER BY year DESC")
        return [r["year"] for r in rows]

    async def add_view(self, kind: str, item_id: int):
        await self.execute(f"UPDATE {TABLES[kind]} SET views=views+1 WHERE id=?", (item_id,))

    # -------------------------------------------------------- episodes
    async def add_episode(self, series_id, season, episode, code, file_id, file_type) -> int:
        return await self.execute(
            "INSERT INTO episodes(series_id,season,episode,code,file_id,file_type) VALUES(?,?,?,?,?,?)",
            (series_id, season, episode, code, file_id, file_type))

    async def get_episode(self, ep_id: int):
        return await self.fetchone("SELECT * FROM episodes WHERE id=?", (ep_id,))

    async def list_episodes(self, series_id: int, season: Optional[int] = None) -> list[dict]:
        if season is None:
            return await self.fetchall("SELECT * FROM episodes WHERE series_id=? ORDER BY season,episode",
                                       (series_id,))
        return await self.fetchall("SELECT * FROM episodes WHERE series_id=? AND season=? ORDER BY episode",
                                   (series_id, season))

    async def season_counts(self, series_id: int) -> list[dict]:
        return await self.fetchall("SELECT season, COUNT(*) AS cnt FROM episodes WHERE series_id=? "
                                   "GROUP BY season ORDER BY season", (series_id,))

    async def episode_exists(self, series_id, season, episode) -> bool:
        return await self.fetchone("SELECT 1 FROM episodes WHERE series_id=? AND season=? AND episode=?",
                                   (series_id, season, episode)) is not None

    async def next_episode_number(self, series_id, season) -> int:
        v = await self.scalar("SELECT MAX(episode) FROM episodes WHERE series_id=? AND season=?",
                              (series_id, season))
        return (v or 0) + 1

    async def adjacent_episode(self, ep: dict):
        return await self.fetchone(
            "SELECT * FROM episodes WHERE series_id=? AND (season>? OR (season=? AND episode>?)) "
            "ORDER BY season,episode LIMIT 1", (ep["series_id"], ep["season"], ep["season"], ep["episode"]))

    async def delete_episode(self, ep_id: int):
        await self.execute("DELETE FROM episodes WHERE id=?", (ep_id,))

    # ------------------------------------------- favorites / ratings
    async def is_fav(self, user_id, kind, item_id) -> bool:
        return await self.fetchone("SELECT 1 FROM favorites WHERE user_id=? AND kind=? AND item_id=?",
                                   (user_id, kind, item_id)) is not None

    async def toggle_fav(self, user_id, kind, item_id) -> bool:
        if await self.is_fav(user_id, kind, item_id):
            await self.execute("DELETE FROM favorites WHERE user_id=? AND kind=? AND item_id=?",
                               (user_id, kind, item_id))
            return False
        await self.execute("INSERT INTO favorites(user_id,kind,item_id) VALUES(?,?,?)", (user_id, kind, item_id))
        return True

    async def list_favs(self, user_id) -> list[dict]:
        out = []
        for kind, table in TABLES.items():
            rows = await self.fetchall(
                f"SELECT t.id,t.title,t.year,t.code,t.views,t.created_at FROM favorites f "
                f"JOIN {table} t ON t.id=f.item_id WHERE f.user_id=? AND f.kind=?", (user_id, kind))
            for r in rows:
                r["kind"] = kind
            out += rows
        return out

    async def set_rating(self, user_id, kind, item_id, score):
        await self.execute("INSERT OR REPLACE INTO ratings(user_id,kind,item_id,score) VALUES(?,?,?,?)",
                           (user_id, kind, item_id, score))

    async def get_rating(self, kind, item_id):
        r = await self.fetchone("SELECT AVG(score) AS a, COUNT(*) AS c FROM ratings WHERE kind=? AND item_id=?",
                                (kind, item_id))
        return (r["a"] or 0.0, r["c"] or 0)

    # ----------------------------------------------------------- stats
    async def stats(self) -> dict:
        return {
            "users": await self.scalar("SELECT COUNT(*) FROM users"),
            "today": await self.scalar("SELECT COUNT(*) FROM users WHERE joined_at >= date('now')"),
            "active": await self.scalar("SELECT COUNT(*) FROM users WHERE last_seen >= date('now')"),
            "blocked": await self.scalar("SELECT COUNT(*) FROM users WHERE blocked=1"),
            "movies": await self.scalar("SELECT COUNT(*) FROM movies"),
            "series": await self.scalar("SELECT COUNT(*) FROM series"),
            "episodes": await self.scalar("SELECT COUNT(*) FROM episodes"),
            "views": (await self.scalar("SELECT SUM(views) FROM movies") or 0)
                     + (await self.scalar("SELECT SUM(views) FROM series") or 0),
            "subs": await self.scalar("SELECT COUNT(*) FROM channels WHERE kind='sub'"),
            "posts": await self.scalar("SELECT COUNT(*) FROM channels WHERE kind='post'"),
        }

    # ------------------------------------------- sub-bot registry
    async def add_bot(self, token, username, owner_id) -> int:
        return await self.execute("INSERT INTO bots(token,username,owner_id) VALUES(?,?,?)",
                                  (token, username, owner_id))

    async def get_bot_by_token(self, token):
        return await self.fetchone("SELECT * FROM bots WHERE token=?", (token,))

    async def get_bot_row(self, row_id):
        return await self.fetchone("SELECT * FROM bots WHERE id=?", (row_id,))

    async def list_bots(self, active_only=False) -> list[dict]:
        sql = "SELECT * FROM bots" + (" WHERE active=1" if active_only else "") + " ORDER BY id"
        return await self.fetchall(sql)

    async def set_bot_active(self, row_id, active: bool):
        await self.execute("UPDATE bots SET active=? WHERE id=?", (1 if active else 0, row_id))

    async def delete_bot(self, row_id):
        await self.execute("DELETE FROM bots WHERE id=?", (row_id,))
