from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "projects.db")))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_NAME = "udh_session"
SESSION_MAX_AGE = 60 * 60 * 12

app = FastAPI(title="مركز التطوير الموحد", version="1.0.0")
serializer = URLSafeTimedSerializer(SECRET_KEY or secrets.token_urlsafe(48), salt="udh-session")
STATIC_DIR = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
STAGES = {"idea", "planning", "building", "testing", "preview", "deployed", "paused"}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                host = request.headers.get("host", "")
                expected_scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
                if parsed.netloc != host or parsed.scheme not in {"http", "https"} or parsed.scheme != expected_scheme:
                    return Response("Origin not allowed", status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        return response

app.add_middleware(SecurityHeadersMiddleware)

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          repo_url TEXT NOT NULL DEFAULT '',
          stack TEXT NOT NULL DEFAULT '',
          stage TEXT NOT NULL DEFAULT 'idea',
          ci_status TEXT NOT NULL DEFAULT 'unknown',
          deploy_status TEXT NOT NULL DEFAULT 'not_deployed',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          action TEXT NOT NULL,
          project_id INTEGER,
          details TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at);
        CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_events(created_at);
        """)

@app.on_event("startup")
def startup() -> None:
    init_db()

def is_configured() -> bool:
    return bool(ADMIN_USERNAME and ADMIN_PASSWORD and len(SECRET_KEY) >= 32
                and not ADMIN_PASSWORD.startswith("CHANGE_ME")
                and not SECRET_KEY.startswith("CHANGE_ME"))

def current_user(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        raise HTTPException(status_code=401, detail="انتهت الجلسة، سجّل الدخول مجددًا")
    if data.get("username") != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="جلسة غير صالحة")
    return ADMIN_USERNAME

class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    repo_url: str = Field(default="", max_length=500)
    stack: str = Field(default="", max_length=200)
    stage: str = Field(default="idea")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("اسم المشروع يجب أن يحتوي على حرفين على الأقل")
        return value

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value: str) -> str:
        if value not in STAGES:
            raise ValueError("مرحلة المشروع غير معروفة")
        return value

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("رابط المستودع يجب أن يكون رابط HTTPS صالحًا")
        return value

class StageIn(BaseModel):
    stage: str

def require_token(env_name: str, label: str) -> str:
    token = os.getenv(env_name, "").strip()
    if not token:
        raise HTTPException(status_code=503, detail=f"لم يتم ضبط رمز {label} على الخادم")
    return token

async def provider_get(url: str, token: str, params: dict | None = None) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            response = await client.get(url, params=params, headers={
                "Authorization": f"Bearer {token}", "Accept": "application/json",
                "User-Agent": "Unified-Development-Hub/1.0"
            })
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="انتهت مهلة الاتصال بمزود الخدمة")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="تعذر الاتصال بمزود الخدمة")
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="رمز الوصول غير صالح أو صلاحياته غير كافية")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"أعاد مزود الخدمة الحالة {response.status_code}")
    return response

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/health")
def health() -> dict:
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "ok", "configured": is_configured()}
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

@app.get("/api/session")
def session_status(request: Request) -> dict:
    try:
        user = current_user(request)
        return {"authenticated": True, "username": user, "configured": is_configured()}
    except HTTPException:
        return {"authenticated": False, "configured": is_configured()}

@app.post("/api/login")
def login(response: Response, username: str = Form(...), password: str = Form(...)) -> dict:
    if not is_configured():
        raise HTTPException(status_code=503, detail="اضبط ADMIN_PASSWORD و SECRET_KEY قبل تسجيل الدخول")
    if not secrets.compare_digest(username, ADMIN_USERNAME) or not secrets.compare_digest(password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
    token = serializer.dumps({"username": ADMIN_USERNAME, "issued_at": utcnow()})
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE,
                        samesite="lax", max_age=SESSION_MAX_AGE, path="/")
    return {"ok": True}

@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return {"ok": True}

@app.get("/api/projects")
def list_projects(_: str = Depends(current_user)) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]

@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectIn, _: str = Depends(current_user)) -> dict:
    stage = payload.stage if payload.stage in STAGES else "idea"
    now = utcnow()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name, description, repo_url, stack, stage, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
            (payload.name.strip(), payload.description.strip(), payload.repo_url.strip(), payload.stack.strip(), stage, now, now))
        project_id = cur.lastrowid
        conn.execute("INSERT INTO audit_events(action, project_id, details, created_at) VALUES(?,?,?,?)",
                     ("project_created", project_id, payload.name.strip(), now))
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)

@app.patch("/api/projects/{project_id}/stage")
def update_stage(project_id: int, payload: StageIn, _: str = Depends(current_user)) -> dict:
    if payload.stage not in STAGES:
        raise HTTPException(status_code=422, detail="مرحلة غير معروفة")
    now = utcnow()
    with db() as conn:
        cur = conn.execute("UPDATE projects SET stage=?, updated_at=? WHERE id=?",
                           (payload.stage, now, project_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="المشروع غير موجود")
        conn.execute("INSERT INTO audit_events(action, project_id, details, created_at) VALUES(?,?,?,?)",
                     ("stage_updated", project_id, payload.stage, now))
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)

@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, _: str = Depends(current_user)) -> Response:
    now = utcnow()
    with db() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="المشروع غير موجود")
        conn.execute("INSERT INTO audit_events(action, project_id, details, created_at) VALUES(?,?,?,?)",
                     ("project_deleted", None, str(project_id), now))
    return Response(status_code=204)

@app.get("/api/audit")
def audit_events(_: str = Depends(current_user)) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 200").fetchall()
    return [dict(row) for row in rows]

@app.get("/api/integrations")
async def integrations(_: str = Depends(current_user)) -> dict:
    results = []
    providers = [
        ("GitHub", os.getenv("GITHUB_READ_TOKEN", ""), "https://api.github.com/user"),
        ("Vercel", os.getenv("VERCEL_READ_TOKEN", ""), "https://api.vercel.com/v2/user"),
    ]
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as client:
        for name, token, endpoint in providers:
            if not token:
                results.append({"provider": name, "configured": False, "connected": False, "status": "missing_token"})
                continue
            try:
                response = await client.get(endpoint, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
                if response.status_code == 200:
                    results.append({"provider": name, "configured": True, "connected": True, "status": "connected"})
                elif response.status_code in {401, 403}:
                    results.append({"provider": name, "configured": True, "connected": False, "status": "invalid_or_insufficient_token"})
                else:
                    results.append({"provider": name, "configured": True, "connected": False, "status": f"provider_http_{response.status_code}"})
            except httpx.TimeoutException:
                results.append({"provider": name, "configured": True, "connected": False, "status": "timeout"})
            except httpx.HTTPError:
                results.append({"provider": name, "configured": True, "connected": False, "status": "connection_error"})
    return {"integrations": results, "mode": "read_only"}

@app.get("/api/github/repos")
async def github_repositories(_: str = Depends(current_user)) -> dict:
    token = require_token("GITHUB_READ_TOKEN", "GitHub")
    response = await provider_get("https://api.github.com/user/repos", token,
                                  {"sort": "updated", "per_page": "25", "affiliation": "owner,collaborator,organization_member"})
    try:
        payload = response.json()
        items = [{"name": x.get("name"), "full_name": x.get("full_name"),
                  "html_url": x.get("html_url"), "private": x.get("private"),
                  "default_branch": x.get("default_branch"), "updated_at": x.get("updated_at")}
                 for x in payload if isinstance(x, dict)]
    except (ValueError, TypeError):
        raise HTTPException(status_code=502, detail="استجابة GitHub غير مفهومة")
    return {"repositories": items, "read_only": True}

@app.get("/api/vercel/projects")
async def vercel_projects(_: str = Depends(current_user)) -> dict:
    token = require_token("VERCEL_READ_TOKEN", "Vercel")
    response = await provider_get("https://api.vercel.com/v9/projects", token, {"limit": "25"})
    try:
        payload = response.json()
        items = [{"id": x.get("id"), "name": x.get("name"), "framework": x.get("framework"),
                  "updatedAt": x.get("updatedAt"), "link": f"https://vercel.com/{x.get('name')}"}
                 for x in payload.get("projects", []) if isinstance(x, dict)]
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=502, detail="استجابة Vercel غير مفهومة")
    return {"projects": items, "read_only": True}
