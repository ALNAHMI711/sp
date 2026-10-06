"""Local admin authentication store for the control plane."""
from __future__ import annotations
import os, sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
import jwt
from pwdlib import PasswordHash

DB=os.getenv("CONTROL_QUEUE_DB",".data/control-queue.sqlite3")
JWT_SECRET=os.getenv("CONTROL_JWT_SECRET","")
password_hash=PasswordHash.recommended()

def _db():
    db=sqlite3.connect(DB,timeout=10); db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS admin_users(username TEXT PRIMARY KEY,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'SUPER_ADMIN',disabled INTEGER NOT NULL DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,action TEXT NOT NULL,target TEXT,detail TEXT,created_at TEXT NOT NULL)")
    return db

def bootstrap_admin():
    u,p=os.getenv("CONTROL_ADMIN_USERNAME"),os.getenv("CONTROL_ADMIN_PASSWORD")
    if not u or not p:return
    with _db() as db:
        if db.execute("SELECT 1 FROM admin_users WHERE username=?",(u,)).fetchone() is None:
            db.execute("INSERT INTO admin_users VALUES(?,?,?,0)",(u,password_hash.hash(p),"SUPER_ADMIN"))

ROLE_SCOPES={"SUPER_ADMIN":{"jobs:read","jobs:write","jobs:cancel","kill:write","audit:read"},"ADMIN":{"jobs:read","jobs:write","jobs:cancel","audit:read"},"OPERATOR":{"jobs:read","jobs:write","jobs:cancel"},"VIEWER":{"jobs:read"},"AUTOMATION_AGENT":{"jobs:read","jobs:write"}}


def login(username,password):
    if not JWT_SECRET: raise RuntimeError("CONTROL_JWT_SECRET is not configured")
    bootstrap_admin()
    with _db() as db:user=db.execute("SELECT * FROM admin_users WHERE username=?",(username,)).fetchone()
    if not user or user["disabled"] or not password_hash.verify(password,user["password_hash"]):
        raise HTTPException(status_code=401,detail="invalid credentials")
    exp=datetime.now(timezone.utc)+timedelta(minutes=30)
    role=user["role"]
    return jwt.encode({"sub":username,"role":role,"scopes":sorted(ROLE_SCOPES.get(role,set())),"exp":exp},JWT_SECRET,algorithm="HS256")

def require_scope(user:dict, scope:str):
    if scope not in set(user.get("scopes", [])):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return user


def current_user(request:Request):
    if not JWT_SECRET: raise HTTPException(status_code=503,detail="authentication is not configured")
    value=request.headers.get("authorization","")
    if not value.startswith("Bearer "): raise HTTPException(status_code=401,detail="authentication required")
    try:return jwt.decode(value[7:],JWT_SECRET,algorithms=["HS256"])
    except jwt.PyJWTError as exc:raise HTTPException(status_code=401,detail="invalid or expired token") from exc

def audit(username,action,target="",detail=""):
    with _db() as db:db.execute("INSERT INTO audit_events(username,action,target,detail,created_at) VALUES(?,?,?,?,?)",(username,action,target,detail[:2000],datetime.now(timezone.utc).isoformat()))
