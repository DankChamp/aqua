import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.routes import chat, documents, notes, flashcards, quizzes, profile, webroutes, facts, search as search_routes, study, teach as teach_routes, activity as activity_routes, ncert as ncert_routes
from api.routes import settings as settings_routes
from config import get_settings

logger = logging.getLogger("aqua.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.deps import get_router, get_db
    get_router()
    get_db()
    yield


s = get_settings()
app = FastAPI(title=s.app_name, debug=s.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(notes.router)
app.include_router(flashcards.router)
app.include_router(quizzes.router)
app.include_router(profile.router)
app.include_router(webroutes.router)
app.include_router(facts.router)
app.include_router(search_routes.router)
app.include_router(settings_routes.router)
app.include_router(study.router)
app.include_router(teach_routes.router)
app.include_router(activity_routes.router)
app.include_router(ncert_routes.router)

WEB_DIR = Path(__file__).resolve().parent / "web"
if WEB_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")


@app.get("/")
def root():
    s = get_settings()
    return {"status": "Aqua is running", "app": s.app_name}


@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "auth_required": bool(s.web_password)}


class LoginRequest(BaseModel):
    password: str


@app.post("/api/auth")
def login(payload: LoginRequest):
    s = get_settings()
    if s.web_password and payload.password == s.web_password:
        return {"ok": True}
    raise HTTPException(401, "Wrong password")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    s = get_settings()
    if not s.web_password:
        return await call_next(request)
    if request.url.path in ("/", "/health", "/api/auth") or request.url.path.startswith("/ui/") or request.url.path.startswith("/api/facts"):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {s.web_password}":
        return await call_next(request)
    if request.cookies.get("aqua_token") == s.web_password:
        return await call_next(request)
    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
