import collections
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional
 
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
import engine
import plantcare

BASE = Path(__file__).parent

app = FastAPI(
    title="Iris Classification API",
    description="Nhận diện loài diên vĩ bằng nhiều mô hình học máy",
    version="2.0.0",
)

engine.load()  # nạp mô hình (tự huấn luyện nếu chưa có)


class Measurements(BaseModel):
    sepal_length: float = Field(gt=0, le=20)
    sepal_width: float = Field(gt=0, le=20)
    petal_length: float = Field(gt=0, le=20)
    petal_width: float = Field(gt=0, le=20)

    def values(self):
        return [self.sepal_length, self.sepal_width, self.petal_length, self.petal_width]


class IrisInput(Measurements):
    model: str = engine.DEFAULT_MODEL


class BatchInput(BaseModel):
    rows: List[Measurements] = Field(min_length=1, max_length=2000)
    model: str = engine.DEFAULT_MODEL


def check_model(model_id: str):
    if not engine.has_model(model_id):
        raise HTTPException(status_code=404, detail=f"Không có mô hình '{model_id}'")


@app.get("/", include_in_schema=False)
def home():
    page = BASE / "index.html"
    if page.exists():
        return FileResponse(page)
    return {"message": "Iris SVM API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/info")
def info():
    return engine.info()


@app.get("/api/regions")
def regions(model: str = engine.DEFAULT_MODEL):
    check_model(model)
    return engine.regions(model)


@app.post("/predict")
def predict(data: IrisInput):
    check_model(data.model)
    return engine.predict_one(data.values(), data.model)


@app.post("/predict/batch")
def predict_batch(data: BatchInput):
    check_model(data.model)
    results = engine.predict_rows([r.values() for r in data.rows], data.model)
    return {"model": data.model, "count": len(results), "results": results}


# ---------- Bác sĩ cây cảnh ----------
class DiagnoseInput(BaseModel):
    symptoms: List[str] = Field(min_length=1, max_length=20)


class ChatMsg(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1500)


class ChatInput(BaseModel):
    messages: List[ChatMsg] = Field(min_length=1, max_length=20)
    species: Optional[str] = None
    symptoms: List[str] = Field(default_factory=list, max_length=20)


@app.get("/api/care-kb")
def care_kb():
    return {
        "groups": [{"name": g, "items": [{"id": i, "label": l} for i, l in items]} for g, items in plantcare.SYMPTOM_GROUPS],
        "species": plantcare.SPECIES_CARE,
        "general": plantcare.GENERAL_TIPS,
        "chat_mode": "ai" if os.environ.get("LLM_API_KEY") else "offline",
    }


@app.post("/api/diagnose")
def diagnose(data: DiagnoseInput):
    return {"results": plantcare.diagnose(data.symptoms)}


# Giới hạn lượt chat theo IP để bảo vệ hạn mức miễn phí của nhà cung cấp AI
CHAT_LIMIT, CHAT_WINDOW = 20, 600
_hits = collections.defaultdict(collections.deque)


def client_ip(req: Request):
    fwd = req.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "?")


def call_llm(data: ChatInput):
    key = os.environ.get("LLM_API_KEY")
    if not key:
        return None
    base = os.environ.get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
    msgs = [{"role": "system", "content": plantcare.system_prompt(data.species, data.symptoms)}]
    msgs += [{"role": m.role, "content": m.content} for m in data.messages[-10:]]
    body = json.dumps({"model": model, "messages": msgs, "max_tokens": 500, "temperature": 0.4}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            text = json.load(r)["choices"][0]["message"]["content"]
        return (text or "").strip() or None
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError):
        return None


@app.post("/api/chat")
def chat(data: ChatInput, request: Request):
    ip, now = client_ip(request), time.time()
    q = _hits[ip]
    while q and now - q[0] > CHAT_WINDOW:
        q.popleft()
    if len(q) >= CHAT_LIMIT:
        raise HTTPException(status_code=429, detail="Bạn hỏi hơi nhanh, vui lòng thử lại sau ít phút.")
    q.append(now)
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if not v]:
            del _hits[k]
    last = next((m.content for m in reversed(data.messages) if m.role == "user"), "")
    reply = call_llm(data)
    if reply:
        return {"reply": reply, "mode": "ai"}
    last_bot = next((m.content for m in reversed(data.messages) if m.role == "assistant"), None)
    return {"reply": plantcare.offline_reply(last, data.species, data.symptoms, last_bot), "mode": "offline"}


# Ảnh hoa thật: đặt trong static/photos (xem photos.json)
if (BASE / "static").is_dir():
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


# ---------- Tài khoản ----------
class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    name: Optional[str] = Field(default=None, max_length=40)


class GardenIn(BaseModel):
    plants: List[dict] = Field(max_length=50)


_tries = collections.defaultdict(collections.deque)


def throttle(key, limit, window=600):
    now, q = time.time(), _tries[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Thử quá nhiều lần, vui lòng đợi vài phút rồi thử lại.")
    q.append(now)
    if len(_tries) > 5000:
        for k in [k for k, v in _tries.items() if not v]:
            del _tries[k]


def same_origin(req: Request):
    origin = req.headers.get("origin")
    if origin and urlparse(origin).netloc != req.headers.get("host"):
        raise HTTPException(status_code=403, detail="Yêu cầu không hợp lệ.")


def is_https(req: Request):
    return req.headers.get("x-forwarded-proto", req.url.scheme).split(",")[0].strip() == "https"


def start_session(resp: Response, req: Request, user):
    token = auth.create_session(user["id"])
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=is_https(req), path="/")


def current_user(req: Request):
    return auth.user_from_token(req.cookies.get(auth.COOKIE))


def need_user(req: Request):
    user = current_user(req)
    if not user:
        raise HTTPException(status_code=401, detail="Bạn cần đăng nhập.")
    return user


@app.post("/api/auth/register")
def register(data: Credentials, request: Request, response: Response):
    same_origin(request)
    throttle("reg:" + client_ip(request), 10)
    try:
        user = auth.register(data.email, data.password, data.name)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    start_session(response, request, user)
    return {"user": user}


@app.post("/api/auth/login")
def login(data: Credentials, request: Request, response: Response):
    same_origin(request)
    throttle("login-ip:" + client_ip(request), 30)
    throttle("login-em:" + data.email.strip().lower(), 8)
    try:
        user = auth.login(data.email, data.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    start_session(response, request, user)
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    same_origin(request)
    auth.end_session(request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    return {"user": current_user(request)}


@app.get("/api/garden")
def get_garden(request: Request):
    return {"plants": auth.get_garden(need_user(request)["id"])}


@app.put("/api/garden")
def put_garden(data: GardenIn, request: Request):
    same_origin(request)
    user = need_user(request)
    try:
        return {"plants": auth.save_garden(user["id"], data.plants)}
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
