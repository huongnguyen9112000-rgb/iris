"""Tài khoản người dùng: đăng ký, đăng nhập, phiên làm việc và đồng bộ vườn.
Chỉ dùng thư viện chuẩn (sqlite3, hashlib.scrypt) nên không cần cài thêm gói.

Lưu ý triển khai: SQLite lưu trong một file. Trên Render gói miễn phí, ổ đĩa không được giữ
khi dịch vụ khởi động lại hoặc deploy lại, nên tài khoản sẽ mất. Muốn lưu lâu dài hãy gắn
Render Disk và đặt biến môi trường DB_PATH trỏ vào đó, hoặc chuyển sang cơ sở dữ liệu ngoài."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

SESSION_DAYS = 30
COOKIE = "iris_session"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
MAX_GARDEN_BYTES = 100_000
MAX_PLANTS = 50

_BASE = Path(__file__).parent


def _db_path():
    want = os.environ.get("DB_PATH")
    candidates = [Path(want)] if want else []
    candidates += [_BASE / "data" / "iris.db", Path("/tmp/iris.db")]
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(p) as c:
                c.execute("CREATE TABLE IF NOT EXISTS _probe (x)")
            return p
        except (OSError, sqlite3.Error):
            continue
    raise RuntimeError("Không tạo được cơ sở dữ liệu")


DB = _db_path()


def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init():
    with conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                pw TEXT NOT NULL,
                created REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS garden (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                data TEXT NOT NULL,
                updated REAL NOT NULL
            );
        """)


init()


class AuthError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


# ---------- mật khẩu ----------
def hash_password(password):
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${h.hex()}"


def verify_password(password, stored):
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, bytes.fromhex(h))
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password("dummy-password-for-timing")


def clean_email(email):
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e) or len(e) > 254:
        raise AuthError(422, "Email không hợp lệ.")
    return e


def check_password(pw):
    if not isinstance(pw, str) or len(pw) < 8:
        raise AuthError(422, "Mật khẩu cần ít nhất 8 ký tự.")
    if len(pw) > 128:
        raise AuthError(422, "Mật khẩu tối đa 128 ký tự.")


# ---------- người dùng và phiên ----------
def public_user(row):
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


def register(email, password, name=None):
    email = clean_email(email)
    check_password(password)
    name = (name or "").strip()[:40] or email.split("@")[0][:40]
    try:
        with conn() as c:
            cur = c.execute("INSERT INTO users (email, name, pw, created) VALUES (?,?,?,?)",
                            (email, name, hash_password(password), time.time()))
            uid = cur.lastrowid
            return public_user(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    except sqlite3.IntegrityError:
        raise AuthError(409, "Email này đã được đăng ký. Hãy đăng nhập.")


def login(email, password):
    try:
        email = clean_email(email)
    except AuthError:
        verify_password(password or "", _DUMMY)
        raise AuthError(401, "Email hoặc mật khẩu không đúng.")
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    ok = verify_password(password or "", row["pw"] if row else _DUMMY)
    if not row or not ok:
        raise AuthError(401, "Email hoặc mật khẩu không đúng.")
    return public_user(row)


def _th(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        c.execute("INSERT INTO sessions (token_hash, user_id, expires) VALUES (?,?,?)",
                  (_th(token), user_id, time.time() + SESSION_DAYS * 86400))
    return token


def user_from_token(token):
    if not token or len(token) > 100:
        return None
    with conn() as c:
        row = c.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                           WHERE s.token_hash=? AND s.expires>?""", (_th(token), time.time())).fetchone()
    return public_user(row) if row else None


def end_session(token):
    if token:
        with conn() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (_th(token),))


# ---------- vườn ----------
def _valid_plant(p):
    return (isinstance(p, dict) and isinstance(p.get("id"), str) and 0 < len(p["id"]) <= 40
            and isinstance(p.get("name"), str) and len(p["name"]) <= 60
            and p.get("sp") in ("setosa", "versicolor", "virginica", "unknown")
            and p.get("place") in ("pot", "ground")
            and isinstance(p.get("planted"), str) and re.match(r"^\d{4}-\d{2}-\d{2}$", p["planted"])
            and isinstance(p.get("every"), dict) and isinstance(p.get("last"), dict))


def get_garden(user_id):
    with conn() as c:
        row = c.execute("SELECT data FROM garden WHERE user_id=?", (user_id,)).fetchone()
    try:
        return json.loads(row["data"]) if row else []
    except ValueError:
        return []


def save_garden(user_id, plants):
    if not isinstance(plants, list) or len(plants) > MAX_PLANTS or not all(_valid_plant(p) for p in plants):
        raise AuthError(422, "Dữ liệu vườn không hợp lệ.")
    data = json.dumps(plants, ensure_ascii=False, separators=(",", ":"))
    if len(data.encode()) > MAX_GARDEN_BYTES:
        raise AuthError(413, "Dữ liệu vườn quá lớn.")
    with conn() as c:
        c.execute("""INSERT INTO garden (user_id, data, updated) VALUES (?,?,?)
                     ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated=excluded.updated""",
                  (user_id, data, time.time()))
    return plants
