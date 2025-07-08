from fastapi import FastAPI, UploadFile, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Float, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, IPvAnyAddress
from typing import List, Optional
from datetime import datetime
import asyncio
import csv
import io
import uuid

from ping3 import ping

DATABASE_URL = "sqlite:///./hosts.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class HostDB(Base):
    __tablename__ = "hosts"
    id = Column(String, primary_key=True, index=True)
    ip = Column(String, unique=True, index=True)
    last_ping = Column(Float, nullable=True)
    delivered_pct = Column(Float, nullable=True)
    lost_pct = Column(Float, nullable=True)
    last_success = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

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
def add_host(host: Host, db: Session = Depends(get_db)):
    if db.query(HostDB).filter(HostDB.ip == str(host.ip)).first():
        raise HTTPException(status_code=400, detail="IP already exists")
    db_host = HostDB(id=host.id, ip=str(host.ip))
    db.add(db_host)
    print("[PING] Cycle complete, committing changes...")
    db.commit()
    db.refresh(db_host)
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
            imported += 1
        except Exception:
            continue
    db.commit()
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

async def ping_worker():
    while True:
        db = SessionLocal()
        try:
            host_ids = [h.id for h in db.query(HostDB.id).all()]
            for host_id in host_ids:
                host = db.query(HostDB).get(host_id)
                if not host:
                    continue

                print(f"[PING] {host.ip}...")
                res_times = []
                for _ in range(4):
                    try:
                        res = ping(str(host.ip), timeout=1)
                        if res is not None:
                            res_times.append(res * 1000)
                    except Exception:
                        pass
                    await asyncio.sleep(0.2)

                latest_host = db.query(HostDB).get(host_id)
                if not latest_host:
                    continue

                total = 4
                success = len(res_times)
                latest_host.last_ping = sum(res_times)/success if success else None
                latest_host.delivered_pct = round(success / total * 100, 2) if success else 0.0
                latest_host.lost_pct = 100 - latest_host.delivered_pct
                if success:
                    latest_host.last_success = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

                print("[PING] Complete, committing changes...")
                db.commit()
        finally:
            db.close()


@app.on_event("startup")
async def start_ping_loop():
    asyncio.create_task(ping_worker())