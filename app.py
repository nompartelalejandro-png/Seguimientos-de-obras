### `/app/backend/.env`

```env

MONGO_URL="mongodb://localhost:27017"

DB_NAME="test_database"

CORS_ORIGINS="*"

EMERGENT_LLM_KEY="sk-emergent-402634d84Ca5e73646"

APP_NAME="albaranes_app"

```



### `/app/backend/server.py`

```python

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Header, Query, Cookie

from fastapi.responses import StreamingResponse

from dotenv import load_dotenv

from starlette.middleware.cors import CORSMiddleware

from motor.motor_asyncio import AsyncIOMotorClient

import os

import io

import uuid

import logging

import requests

from pathlib import Path

from pydantic import BaseModel, Field

from typing import List, Optional

from datetime import datetime, timezone, timedelta



ROOT_DIR = Path(__file__).parent

load_dotenv(ROOT_DIR / '.env')



mongo_url = os.environ['MONGO_URL']

client = AsyncIOMotorClient(mongo_url)

db = client[os.environ['DB_NAME']]



STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")

APP_NAME = os.environ.get("APP_NAME", "albaranes_app")

storage_key: Optional[str] = None



EMERGENT_AUTH_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"



app = FastAPI()

api_router = APIRouter(prefix="/api")



logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')





# --------------------- Storage helpers ---------------------

def init_storage():

    global storage_key

    if storage_key:

        return storage_key

    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)

    resp.raise_for_status()

    storage_key = resp.json()["storage_key"]

    return storage_key





def put_object(path: str, data: bytes, content_type: str) -> dict:

    key = init_storage()

    resp = requests.put(

        f"{STORAGE_URL}/objects/{path}",

        headers={"X-Storage-Key": key, "Content-Type": content_type},

        data=data, timeout=120,

    )

    resp.raise_for_status()

    return resp.json()





def get_object(path: str):

    key = init_storage()

    resp = requests.get(

        f"{STORAGE_URL}/objects/{path}",

        headers={"X-Storage-Key": key}, timeout=60,

    )

    resp.raise_for_status()

    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")





# --------------------- Models ---------------------

class User(BaseModel):

    user_id: str

    email: str

    name: str

    picture: Optional[str] = None

    created_at: str





class Worker(BaseModel):

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    name: str

    role: Optional[str] = None

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())





class WorkerCreate(BaseModel):

    name: str

    role: Optional[str] = None





class BudgetItem(BaseModel):

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    code: Optional[str] = None

    name: str

    budget_amount: float = 0.0

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())





class BudgetItemCreate(BaseModel):

    code: Optional[str] = None

    name: str

    budget_amount: float = 0.0





class AlbaranPhoto(BaseModel):

    id: str

    storage_path: str

    original_filename: str

    content_type: str

    size: int





class Albaran(BaseModel):

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    numero: str

    fecha: str

    worker_id: str

    worker_name: str

    budget_item_id: str

    budget_item_name: str

    gastos: float

    comentarios: Optional[str] = ""

    photos: List[AlbaranPhoto] = []

    owner_user_id: str

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())





class AlbaranCreate(BaseModel):

    numero: str

    fecha: str

    worker_id: str

    budget_item_id: str

    gastos: float

    comentarios: Optional[str] = ""





class AlbaranUpdate(BaseModel):

    numero: Optional[str] = None

    fecha: Optional[str] = None

    worker_id: Optional[str] = None

    budget_item_id: Optional[str] = None

    gastos: Optional[float] = None

    comentarios: Optional[str] = None





# --------------------- Auth helpers ---------------------

async def get_current_user(request: Request) -> dict:

    token = request.cookies.get("session_token")

    if not token:

        auth = request.headers.get("Authorization")

        if auth and auth.lower().startswith("bearer "):

            token = auth.split(" ", 1)[1]

    if not token:

        raise HTTPException(status_code=401, detail="Not authenticated")



    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})

    if not session:

        raise HTTPException(status_code=401, detail="Invalid session")



    expires_at = session.get("expires_at")

    if isinstance(expires_at, str):

        expires_at = datetime.fromisoformat(expires_at)

    if expires_at.tzinfo is None:

        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):

        raise HTTPException(status_code=401, detail="Session expired")



    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})

    if not user:

        raise HTTPException(status_code=401, detail="User not found")

    return user





# --------------------- Auth routes ---------------------

@api_router.post("/auth/session")

async def auth_session(request: Request, response: Response):

    body = await request.json()

    session_id = body.get("session_id")

    if not session_id:

        raise HTTPException(status_code=400, detail="session_id required")



    r = requests.get(EMERGENT_AUTH_SESSION_URL, headers={"X-Session-ID": session_id}, timeout=30)

    if r.status_code != 200:

        raise HTTPException(status_code=401, detail="Invalid session_id")

    data = r.json()



    email = data["email"]

    existing = await db.users.find_one({"email": email}, {"_id": 0})

    if existing:

        user_id = existing["user_id"]

        await db.users.update_one(

            {"user_id": user_id},

            {"$set": {"name": data.get("name", existing.get("name")),

                       "picture": data.get("picture", existing.get("picture"))}},

        )

    else:

        user_id = f"user_{uuid.uuid4().hex[:12]}"

        await db.users.insert_one({

            "user_id": user_id,

            "email": email,

            "name": data.get("name", ""),

            "picture": data.get("picture", ""),

            "created_at": datetime.now(timezone.utc).isoformat(),

        })



    session_token = data["session_token"]

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await db.user_sessions.insert_one({

        "user_id": user_id,

        "session_token": session_token,

        "expires_at": expires_at.isoformat(),

        "created_at": datetime.now(timezone.utc).isoformat(),

    })



    response.set_cookie(

        key="session_token",

        value=session_token,

        max_age=7 * 24 * 60 * 60,

        httponly=True,

        secure=True,

        samesite="none",

        path="/",

    )



    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})

    return {"user": user, "session_token": session_token}





@api_router.get("/auth/me")

async def auth_me(request: Request):

    user = await get_current_user(request)

    return user





@api_router.post("/auth/logout")

async def auth_logout(request: Request, response: Response):

    token = request.cookies.get("session_token") or ""

    if token:

        await db.user_sessions.delete_one({"session_token": token})

    response.delete_cookie("session_token", path="/")

    return {"ok": True}





# --------------------- Workers ---------------------

@api_router.get("/workers", response_model=List[Worker])

async def list_workers(request: Request):

    await get_current_user(request)

    items = await db.workers.find({}, {"_id": 0}).sort("name", 1).to_list(1000)

    return items





@api_router.post("/workers", response_model=Worker)

async def create_worker(payload: WorkerCreate, request: Request):

    await get_current_user(request)

    worker = Worker(**payload.model_dump())

    await db.workers.insert_one(worker.model_dump())

    return worker





@api_router.put("/workers/{worker_id}", response_model=Worker)

async def update_worker(worker_id: str, payload: WorkerCreate, request: Request):

    await get_current_user(request)

    res = await db.workers.update_one({"id": worker_id}, {"$set": payload.model_dump()})

    if res.matched_count == 0:

        raise HTTPException(status_code=404, detail="Worker not found")

    doc = await db.workers.find_one({"id": worker_id}, {"_id": 0})

    return doc





@api_router.delete("/workers/{worker_id}")

async def delete_worker(worker_id: str, request: Request):

    await get_current_user(request)

    await db.workers.delete_one({"id": worker_id})

    return {"ok": True}





# --------------------- Budget items ---------------------

@api_router.get("/budget-items", response_model=List[BudgetItem])

async def list_budget_items(request: Request):

    await get_current_user(request)

    items = await db.budget_items.find({}, {"_id": 0}).sort("name", 1).to_list(1000)

    return items





@api_router.post("/budget-items", response_model=BudgetItem)

async def create_budget_item(payload: BudgetItemCreate, request: Request):

    await get_current_user(request)

    item = BudgetItem(**payload.model_dump())

    await db.budget_items.insert_one(item.model_dump())

    return item





@api_router.put("/budget-items/{item_id}", response_model=BudgetItem)

async def update_budget_item(item_id: str, payload: BudgetItemCreate, request: Request):

    await get_current_user(request)

    res = await db.budget_items.update_one({"id": item_id}, {"$set": payload.model_dump()})

    if res.matched_count == 0:

        raise HTTPException(status_code=404, detail="Budget item not found")

    doc = await db.budget_items.find_one({"id": item_id}, {"_id": 0})

    return doc





@api_router.delete("/budget-items/{item_id}")

async def delete_budget_item(item_id: str, request: Request):

    await get_current_user(request)

    await db.budget_items.delete_one({"id": item_id})

    return {"ok": True}





# --------------------- Albaranes ---------------------

async def _enrich_names(payload: dict) -> dict:

    worker = await db.workers.find_one({"id": payload["worker_id"]}, {"_id": 0})

    item = await db.budget_items.find_one({"id": payload["budget_item_id"]}, {"_id": 0})

    if not worker:

        raise HTTPException(status_code=400, detail="Trabajador no encontrado")

    if not item:

        raise HTTPException(status_code=400, detail="Partida no encontrada")

    payload["worker_name"] = worker["name"]

    payload["budget_item_name"] = item["name"]

    return payload





@api_router.get("/albaranes", response_model=List[Albaran])

async def list_albaranes(

    request: Request,

    worker_id: Optional[str] = None,

    budget_item_id: Optional[str] = None,

    date_from: Optional[str] = None,

    date_to: Optional[str] = None,

    q: Optional[str] = None,

):

    await get_current_user(request)

    query: dict = {}

    if worker_id: query["worker_id"] = worker_id

    if budget_item_id: query["budget_item_id"] = budget_item_id

    if date_from or date_to:

        query["fecha"] = {}

        if date_from: query["fecha"]["$gte"] = date_from

        if date_to:   query["fecha"]["$lte"] = date_to

    if q:

        query["$or"] = [

            {"numero": {"$regex": q, "$options": "i"}},

            {"comentarios": {"$regex": q, "$options": "i"}},

        ]

    items = await db.albaranes.find(query, {"_id": 0}).sort("fecha", -1).to_list(2000)

    return items





@api_router.get("/albaranes/{albaran_id}", response_model=Albaran)

async def get_albaran(albaran_id: str, request: Request):

    await get_current_user(request)

    doc = await db.albaranes.find_one({"id": albaran_id}, {"_id": 0})

    if not doc:

        raise HTTPException(status_code=404, detail="Albaran not found")

    return doc





@api_router.post("/albaranes", response_model=Albaran)

async def create_albaran(payload: AlbaranCreate, request: Request):

    user = await get_current_user(request)

    data = payload.model_dump()

    data = await _enrich_names(data)

    albaran = Albaran(**data, owner_user_id=user["user_id"], photos=[])

    await db.albaranes.insert_one(albaran.model_dump())

    return albaran





@api_router.put("/albaranes/{albaran_id}", response_model=Albaran)

async def update_albaran(albaran_id: str, payload: AlbaranUpdate, request: Request):

    await get_current_user(request)

    existing = await db.albaranes.find_one({"id": albaran_id}, {"_id": 0})

    if not existing:

        raise HTTPException(status_code=404, detail="Albaran not found")

    update = {k: v for k, v in payload.model_dump().items() if v is not None}

    if "worker_id" in update or "budget_item_id" in update:

        merged = {**existing, **update}

        merged = await _enrich_names(merged)

        update["worker_name"] = merged["worker_name"]

        update["budget_item_name"] = merged["budget_item_name"]

    await db.albaranes.update_one({"id": albaran_id}, {"$set": update})

    doc = await db.albaranes.find_one({"id": albaran_id}, {"_id": 0})

    return doc





@api_router.delete("/albaranes/{albaran_id}")

async def delete_albaran(albaran_id: str, request: Request):

    await get_current_user(request)

    await db.albaranes.delete_one({"id": albaran_id})

    return {"ok": True}





# --------------------- Photo upload ---------------------

@api_router.post("/albaranes/{albaran_id}/photos")

async def upload_albaran_photo(albaran_id: str, request: Request, file: UploadFile = File(...)):

    user = await get_current_user(request)

    existing = await db.albaranes.find_one({"id": albaran_id}, {"_id": 0})

    if not existing:

        raise HTTPException(status_code=404, detail="Albaran not found")



    ext = (file.filename.split(".")[-1] if "." in (file.filename or "") else "bin").lower()

    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):

        raise HTTPException(status_code=400, detail="Tipo de imagen no soportado")



    photo_id = str(uuid.uuid4())

    path = f"{APP_NAME}/albaranes/{user['user_id']}/{albaran_id}/{photo_id}.{ext}"

    data = await file.read()

    result = put_object(path, data, file.content_type or f"image/{ext}")



    photo = {

        "id": photo_id,

        "storage_path": result["path"],

        "original_filename": file.filename or f"photo.{ext}",

        "content_type": file.content_type or f"image/{ext}",

        "size": int(result.get("size", len(data))),

    }

    await db.albaranes.update_one({"id": albaran_id}, {"$push": {"photos": photo}})

    return photo





@api_router.delete("/albaranes/{albaran_id}/photos/{photo_id}")

async def delete_albaran_photo(albaran_id: str, photo_id: str, request: Request):

    await get_current_user(request)

    await db.albaranes.update_one(

        {"id": albaran_id},

        {"$pull": {"photos": {"id": photo_id}}},

    )

    return {"ok": True}





@api_router.get("/files/{path:path}")

async def download_file(path: str, request: Request, auth: Optional[str] = Query(None)):

    token = request.cookies.get("session_token")

    if not token:

        a = request.headers.get("Authorization")

        if a and a.lower().startswith("bearer "):

            token = a.split(" ", 1)[1]

    if not token and auth:

        token = auth

    if not token:

        raise HTTPException(status_code=401, detail="Not authenticated")

    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})

    if not session:

        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session.get("expires_at")

    if isinstance(expires_at, str):

        expires_at = datetime.fromisoformat(expires_at)

    if expires_at.tzinfo is None:

        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):

        raise HTTPException(status_code=401, detail="Session expired")

    data, content_type = get_object(path)

    return Response(content=data, media_type=content_type)





# --------------------- Dashboard ---------------------

@api_router.get("/dashboard/summary")

async def dashboard_summary(request: Request):

    await get_current_user(request)

    pipeline = [

        {"$group": {

            "_id": "$budget_item_id",

            "budget_item_name": {"$first": "$budget_item_name"},

            "total": {"$sum": "$gastos"},

            "count": {"$sum": 1},

        }},

        {"$sort": {"total": -1}},

    ]

    by_partida = []

    async for d in db.albaranes.aggregate(pipeline):

        by_partida.append({

            "budget_item_id": d["_id"],

            "budget_item_name": d.get("budget_item_name", ""),

            "total": float(d["total"] or 0),

            "count": d["count"],

        })



    total_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$gastos"}, "count": {"$sum": 1}}}]

    total_doc = None

    async for d in db.albaranes.aggregate(total_pipeline):

        total_doc = d

    total = float(total_doc["total"]) if total_doc else 0.0

    count = int(total_doc["count"]) if total_doc else 0



    workers_count = await db.workers.count_documents({})

    items_count = await db.budget_items.count_documents({})



    return {

        "total_gastos": total,

        "total_albaranes": count,

        "workers_count": workers_count,

        "budget_items_count": items_count,

        "by_partida": by_partida,

    }





# --------------------- Export ---------------------

@api_router.get("/albaranes/export/excel")

async def export_excel(request: Request):

    await get_current_user(request)

    items = await db.albaranes.find({}, {"_id": 0}).sort("fecha", -1).to_list(5000)



    from openpyxl import Workbook

    wb = Workbook()

    ws = wb.active

    ws.title = "Albaranes"

    headers = ["Numero", "Fecha", "Trabajador", "Partida", "Gastos", "Comentarios", "Fotos"]

    ws.append(headers)

    for it in items:

        ws.append([

            it.get("numero", ""),

            it.get("fecha", ""),

            it.get("worker_name", ""),

            it.get("budget_item_name", ""),

            float(it.get("gastos", 0) or 0),

            it.get("comentarios", "") or "",

            len(it.get("photos", []) or []),

        ])



    buf = io.BytesIO()

    wb.save(buf)

    buf.seek(0)

    return StreamingResponse(

        buf,

        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        headers={"Content-Disposition": "attachment; filename=albaranes.xlsx"},

    )





@api_router.get("/albaranes/export/pdf")

async def export_pdf(request: Request):

    await get_current_user(request)

    items = await db.albaranes.find({}, {"_id": 0}).sort("fecha", -1).to_list(5000)



    from reportlab.lib.pagesizes import A4, landscape

    from reportlab.lib import colors

    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    from reportlab.lib.styles import getSampleStyleSheet



    buf = io.BytesIO()

    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Albaranes")

    styles = getSampleStyleSheet()

    elements = [Paragraph("<b>Listado de Albaranes</b>", styles["Title"]), Spacer(1, 12)]



    data = [["Numero", "Fecha", "Trabajador", "Partida", "Gastos", "Comentarios"]]

    total = 0.0

    for it in items:

        gastos = float(it.get("gastos", 0) or 0)

        total += gastos

        data.append([

            it.get("numero", ""),

            it.get("fecha", ""),

            it.get("worker_name", ""),

            it.get("budget_item_name", ""),

            f"{gastos:.2f} EUR",

            (it.get("comentarios", "") or "")[:60],

        ])

    data.append(["", "", "", "TOTAL", f"{total:.2f} EUR", ""])



    table = Table(data, repeatRows=1, colWidths=[70, 70, 110, 130, 70, 250])

    table.setStyle(TableStyle([

        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0047AB")),

        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),

        ("FONTSIZE", (0, 0), (-1, -1), 9),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F3F4F6")),

        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),

    ]))

    elements.append(table)

    doc.build(elements)

    buf.seek(0)

    return StreamingResponse(

        buf,

        media_type="application/pdf",

        headers={"Content-Disposition": "attachment; filename=albaranes.pdf"},

    )





@api_router.get("/")

async def root():

    return {"message": "Albaranes API"}





app.include_router(api_router)



app.add_middleware(

    CORSMiddleware,

    allow_credentials=True,

    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),

    allow_methods=["*"],

    allow_headers=["*"],

    expose_headers=["*"],

)





@app.on_event("startup")

async def startup_event():

    try:

        init_storage()

        logger.info("Storage initialized")

    except Exception as e:

        logger.error(f"Storage init failed: {e}")





@app.on_event("shutdown")

async def shutdown_db_client():

    client.close()

```



---



## 📁 FRONTEND



### `/app/frontend/.env`

```env

REACT_APP_BACKEND_URL=https://expense-logger-166.preview.emergentagent.com

WDS_SOCKET_PORT=443

ENABLE_HEALTH_CHECK=false

```



### `/app/frontend/src/index.css`

```css

@tailwind base;

@tailwind components;

@tailwind utilities;



@import url('https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');



body {

    margin: 0;

    font-family: 'IBM Plex Sans', system-ui, -apple-system, sans-serif;

    -webkit-font-smoothing: antialiased;

    -moz-osx-font-smoothing: grayscale;

    background: #FFFFFF;

    color: #111827;

}



h1, h2, h3, h4, h5, h6 {

    font-family: 'Work Sans', system-ui, sans-serif;

    letter-spacing: -0.01em;

}



.font-display { font-family: 'Work Sans', sans-serif; }

.font-mono { font-family: 'IBM Plex Mono', monospace; }



@layer base {

    :root {

        --background: 0 0% 100%;

        --foreground: 220 30% 10%;

        --card: 0 0% 100%;

        --card-foreground: 220 30% 10%;

        --popover: 0 0% 100%;

        --popover-foreground: 220 30% 10%;

        --primary: 214 100% 34%;

        --primary-foreground: 0 0% 100%;

        --secondary: 220 14% 96%;

        --secondary-foreground: 220 30% 10%;

        --muted: 220 14% 96%;

        --muted-foreground: 220 9% 46%;

        --accent: 22 100% 50%;

        --accent-foreground: 0 0% 100%;

        --destructive: 0 72% 51%;

        --destructive-foreground: 0 0% 100%;

        --border: 220 13% 91%;

        --input: 220 13% 91%;

        --ring: 214 100% 34%;

        --chart-1: 214 100% 34%;

        --chart-2: 22 100% 50%;

        --chart-3: 173 58% 39%;

        --chart-4: 43 74% 50%;

        --chart-5: 280 60% 55%;

        --radius: 0.5rem;

    }

}



@layer base {

    * { @apply border-border; }

    body { @apply bg-background text-foreground; }

}



.bg-grid-soft {

    background-image:

        linear-gradient(to right, rgba(17, 24, 39, 0.04) 1px, transparent 1px),

        linear-gradient(to bottom, rgba(17, 24, 39, 0.04) 1px, transparent 1px);

    background-size: 32px 32px;

}



.surface { background: #F9FAFB; }



@keyframes fadeUp {

    from { opacity: 0; transform: translateY(8px); }

    to   { opacity: 1; transform: translateY(0); }

}

.fade-up { animation: fadeUp 0.35s ease-out both; }



.photo-thumb {

    width: 100%;

    aspect-ratio: 1 / 1;

    object-fit: cover;

    border-radius: 0.5rem;

    border: 1px solid hsl(var(--border));

}

```



### `/app/frontend/src/App.css`

```css

.App { min-height: 100vh; }

```



### `/app/frontend/src/App.js`

```jsx

import React from "react";

import "@/App.css";

import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";

import { AuthProvider, useAuth } from "@/context/AuthContext";

import { Toaster } from "@/components/ui/sonner";

import Login from "@/pages/Login";

import AuthCallback from "@/pages/AuthCallback";

import Dashboard from "@/pages/Dashboard";

import Albaranes from "@/pages/Albaranes";

import AlbaranForm from "@/pages/AlbaranForm";

import Workers from "@/pages/Workers";

import Partidas from "@/pages/Partidas";

import ProtectedRoute from "@/components/ProtectedRoute";



function RootRedirect() {

  const { user, loading } = useAuth();

  if (loading) {

    return (

      <div className="min-h-screen flex items-center justify-center">

        <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />

      </div>

    );

  }

  if (user) return <Navigate to="/dashboard" replace />;

  return <Login />;

}



function AppRouter() {

  const location = useLocation();

  if (location.hash?.includes("session_id=")) {

    return <AuthCallback />;

  }

  return (

    <Routes>

      <Route path="/" element={<RootRedirect />} />

      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />

      <Route path="/albaranes" element={<ProtectedRoute><Albaranes /></ProtectedRoute>} />

      <Route path="/albaranes/nuevo" element={<ProtectedRoute><AlbaranForm /></ProtectedRoute>} />

      <Route path="/albaranes/:id" element={<ProtectedRoute><AlbaranForm /></ProtectedRoute>} />

      <Route path="/trabajadores" element={<ProtectedRoute><Workers /></ProtectedRoute>} />

      <Route path="/partidas" element={<ProtectedRoute><Partidas /></ProtectedRoute>} />

      <Route path="*" element={<Navigate to="/" replace />} />

    </Routes>

  );

}



export default function App() {

  return (

    <div className="App">

      <BrowserRouter>

        <AuthProvider>

          <AppRouter />

          <Toaster richColors position="top-right" />

        </AuthProvider>

      </BrowserRouter>

    </div>

  );

}

```



### `/app/frontend/src/lib/api.js`

```jsx

import axios from "axios";



const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const API = `${BACKEND_URL}/api`;



const api = axios.create({

  baseURL: API,

  withCredentials: true,

});



export default api;

```



### `/app/frontend/src/context/AuthContext.jsx`

```jsx

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

import api from "@/lib/api";



const AuthContext = createContext(null);



export function AuthProvider({ children }) {

  const [user, setUser] = useState(null);

  const [loading, setLoading] = useState(true);



  const checkAuth = useCallback(async () => {

    try {

      const res = await api.get("/auth/me");

      setUser(res.data);

    } catch {

      setUser(null);

    } finally {

      setLoading(false);

    }

  }, []);



  useEffect(() => {

    if (window.location.hash?.includes("session_id=")) {

      setLoading(false);

      return;

    }

    checkAuth();

  }, [checkAuth]);



  const logout = async () => {

    try { await api.post("/auth/logout"); } catch (e) { /* ignore */ }

    setUser(null);

    window.location.href = "/";

  };



  return (

    <AuthContext.Provider value={{ user, setUser, loading, checkAuth, logout }}>

      {children}

    </AuthContext.Provider>

  );

}



export const useAuth = () => useContext(AuthContext);

```



### `/app/frontend/src/components/ProtectedRoute.jsx`

```jsx

import React from "react";

import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";



export default function ProtectedRoute({ children }) {

  const { user, loading } = useAuth();

  const location = useLocation();



  if (loading) {

    return (

      <div className="min-h-screen flex items-center justify-center">

        <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />

      </div>

    );

  }

  if (!user) return <Navigate to="/" replace state={{ from: location }} />;

  return children;

}

```



### `/app/frontend/src/components/Navbar.jsx`

```jsx

import React from "react";

import { Link, NavLink } from "react-router-dom";

import { LogOut, FileText, LayoutDashboard, Users, FolderKanban, HardHat } from "lucide-react";

import { Button } from "@/components/ui/button";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

import { useAuth } from "@/context/AuthContext";



export default function Navbar() {

  const { user, logout } = useAuth();



  const navLinkClass = ({ isActive }) =>

    `inline-flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors ${

      isActive ? "bg-primary text-primary-foreground" : "text-foreground/80 hover:bg-muted"

    }`;



  return (

    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur">

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">

        <Link to="/dashboard" className="flex items-center gap-2">

          <div className="h-9 w-9 rounded-md bg-primary flex items-center justify-center text-primary-foreground">

            <HardHat className="h-5 w-5" strokeWidth={2.25} />

          </div>

          <div className="leading-tight hidden sm:block">

            <div className="font-display font-bold text-base">Albaranes</div>

            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Gestión de obra</div>

          </div>

        </Link>



        <nav className="flex items-center gap-1 overflow-x-auto">

          <NavLink to="/dashboard" className={navLinkClass}>

            <LayoutDashboard className="h-4 w-4" /> <span className="hidden sm:inline">Resumen</span>

          </NavLink>

          <NavLink to="/albaranes" className={navLinkClass}>

            <FileText className="h-4 w-4" /> <span className="hidden sm:inline">Albaranes</span>

          </NavLink>

          <NavLink to="/trabajadores" className={navLinkClass}>

            <Users className="h-4 w-4" /> <span className="hidden sm:inline">Trabajadores</span>

          </NavLink>

          <NavLink to="/partidas" className={navLinkClass}>

            <FolderKanban className="h-4 w-4" /> <span className="hidden sm:inline">Partidas</span>

          </NavLink>

        </nav>



        <div className="flex items-center gap-3">

          {user && (

            <div className="flex items-center gap-2">

              <Avatar className="h-8 w-8">

                <AvatarImage src={user.picture} alt={user.name} />

                <AvatarFallback>{(user.name || user.email || "U")[0].toUpperCase()}</AvatarFallback>

              </Avatar>

              <span className="hidden md:block text-sm font-medium">{user.name}</span>

            </div>

          )}

          <Button variant="outline" size="sm" onClick={logout}>

            <LogOut className="h-4 w-4 mr-1" /> Salir

          </Button>

        </div>

      </div>

    </header>

  );

}

```



### `/app/frontend/src/components/AppShell.jsx`

```jsx

import React from "react";

import Navbar from "@/components/Navbar";



export default function AppShell({ children }) {

  return (

    <div className="min-h-screen bg-background">

      <Navbar />

      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 md:py-10">

        {children}

      </main>

    </div>

  );

}

```



### `/app/frontend/src/pages/Login.jsx`

```jsx

import React from "react";

import { Button } from "@/components/ui/button";

import { HardHat, ShieldCheck, FileText, Camera } from "lucide-react";



export default function Login() {

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

  const handleGoogleLogin = () => {

    const redirectUrl = window.location.origin + "/dashboard";

    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;

  };



  return (

    <div className="min-h-scr
