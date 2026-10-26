"""Persistência SQLite; datas UTC e histórico removido em cascata com o dispositivo."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from monitor import validate_target

DEVICE_TYPES = ("roteador", "servidor", "computador", "impressora", "outro")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@contextmanager
def connect(path):
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL UNIQUE,
                device_type TEXT NOT NULL CHECK(device_type IN
                    ('roteador','servidor','computador','impressora','outro')),
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY,
                device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                status TEXT NOT NULL CHECK(status IN ('online','offline','timeout','error')),
                latency_ms REAL CHECK(latency_ms IS NULL OR latency_ms >= 0),
                latency_is_upper_bound INTEGER NOT NULL DEFAULT 0
                    CHECK(latency_is_upper_bound IN (0,1)),
                error TEXT,
                checked_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS checks_device_date
                ON checks(device_id, checked_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS checks_date ON checks(checked_at DESC);
        """)


def validate_device(name, address, device_type, description=""):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or any(ord(c) < 32 for c in name):
        raise ValueError("Nome deve conter entre 1 e 100 caracteres, sem caracteres de controle.")
    if device_type not in DEVICE_TYPES:
        raise ValueError("Tipo de dispositivo inválido.")
    if not isinstance(description, str) or len(description) > 1000:
        raise ValueError("Descrição deve conter até 1000 caracteres.")
    return name.strip(), validate_target(address).lower().rstrip("."), device_type, description.strip()


def get_device(path, device_id):
    with connect(path) as db:
        return db.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()


def list_devices(path):
    with connect(path) as db:
        return db.execute("SELECT * FROM devices ORDER BY name COLLATE NOCASE, id").fetchall()


def save_device(path, name, address, device_type, description="", device_id=None):
    values = validate_device(name, address, device_type, description)
    with connect(path) as db:
        if device_id is not None and not db.execute("SELECT id FROM devices WHERE id = ?", (device_id,)).fetchone():
            raise ValueError("Dispositivo não encontrado.")
        try:
            if device_id is None:
                return db.execute("INSERT INTO devices(name,address,device_type,description,created_at) VALUES (?,?,?,?,?)", (*values, utc_now())).lastrowid
            db.execute("UPDATE devices SET name=?,address=?,device_type=?,description=? WHERE id=?", (*values, device_id))
            return device_id
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                raise ValueError("Já existe um dispositivo com esse endereço.") from exc
            raise


def delete_device(path, device_id):
    with connect(path) as db:
        if db.execute("DELETE FROM devices WHERE id=?", (device_id,)).rowcount != 1:
            raise ValueError("Dispositivo não encontrado.")


def record_check(path, device_id, result):
    with connect(path) as db:
        return db.execute("""INSERT INTO checks
            (device_id,status,latency_ms,latency_is_upper_bound,error,checked_at)
            VALUES (?,?,?,?,?,?)""", (device_id, result["status"], result["latency_ms"],
            result["latency_is_upper_bound"], result["error"], utc_now())).lastrowid


def get_history(path, device_id, limit=100):
    with connect(path) as db:
        return db.execute("SELECT * FROM checks WHERE device_id=? ORDER BY checked_at DESC, id DESC LIMIT ?",
                          (device_id, limit)).fetchall()
