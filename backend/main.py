from fastapi import FastAPI, UploadFile, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, IPvAnyAddress
from typing import List, Optional
import asyncio
import csv
import io
import uuid

from db import SessionLocal, HostDB
from ping_worker import start_ping_for_host, ping_worker

class Host(BaseModel):
    id: str
    ip: IPvAnyAddress
    last_ping: Optional[float] = None
    delivered_pct: Optional[float] = None
    lost_pct: Optional[float] = None
    last_success: Optional[str] = None

    class Config:
        from_attributes = True

app = FastAPI(
    title="Ping Hosts API",
    description="API для управления хостами и сбора статистики пинга",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/hosts", response_model=List[Host])
def get_hosts(db: Session = Depends(get_db)):
    return db.query(HostDB).all()

@app.post("/hosts", response_model=Host)
async def add_host(host: Host, db: Session = Depends(get_db)):
    if db.query(HostDB).filter(HostDB.ip == str(host.ip)).first():
        raise HTTPException(status_code=400, detail="IP already exists")
    db_host = HostDB(id=host.id, ip=str(host.ip))
    db.add(db_host)
    db.commit()
    db.refresh(db_host)
    loop = asyncio.get_event_loop()
    loop.create_task(start_ping_for_host(db_host.id))  # запускаем вручную

    return db_host

@app.put("/hosts/{host_id}", response_model=Host)
def edit_host(host_id: str, new_data: Host, db: Session = Depends(get_db)):
    host = db.query(HostDB).filter(HostDB.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    if db.query(HostDB).filter(HostDB.ip == str(new_data.ip), HostDB.id != host_id).first():
        raise HTTPException(status_code=400, detail="IP already exists")
    host.ip = str(new_data.ip)
    db.commit()
    db.refresh(host)
    return host

@app.delete("/hosts/{host_id}")
def delete_host(host_id: str, db: Session = Depends(get_db)):
    host = db.query(HostDB).filter(HostDB.id == host_id).first()
    if host:
        db.delete(host)
        db.commit()
    return {"detail": "Deleted"}

@app.post("/hosts/import")
def import_csv(file: UploadFile, db: Session = Depends(get_db)):
    contents = file.file.read().decode("utf-8")
    reader = csv.reader(io.StringIO(contents))
    imported = 0
    for row in reader:
        try:
            ip = row[0].strip()
            if db.query(HostDB).filter(HostDB.ip == ip).first():
                continue
            db_host = HostDB(id=str(uuid.uuid4()), ip=ip)
            db.add(db_host)
            db.commit()
            start_ping_for_host(db_host.id)
            imported += 1
        except Exception:
            continue
    return {"imported": imported}

@app.get("/stats/export")
def export_csv(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["IP", "Ping", "% Delivered", "% Lost", "Last Success"])
    for h in db.query(HostDB).all():
        writer.writerow([
            h.ip, h.last_ping or "n/a", h.delivered_pct or "n/a",
            h.lost_pct or "n/a", h.last_success or "n/a"
        ])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=stats.csv"
    })

@app.on_event("startup")
async def start_ping_loop():
    asyncio.create_task(ping_worker())
