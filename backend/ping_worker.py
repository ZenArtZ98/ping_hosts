from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from ping3 import ping
import asyncio
from db import SessionLocal, HostDB

ping_tasks = {}

async def ping_host_forever(host_id: str):
    while True:
        db: Session = SessionLocal()
        try:
            print(f"[PING] Start pinger for {host_id}")
            host = db.query(HostDB).filter(HostDB.id == host_id).first()
            if not host:
                return
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

            total = 4
            success = len(res_times)
            host.last_ping = sum(res_times)/success if success else None
            host.delivered_pct = round(success / total * 100, 2) if success else 0.0
            host.lost_pct = 100 - host.delivered_pct
            if success:
                host.last_success = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            db.commit()
            print(f"[PING] DB commit for {host.ip}")
        finally:
            db.close()

        await asyncio.sleep(9)

async def start_ping_for_host(host_id: str):
    if host_id not in ping_tasks:
        task = asyncio.create_task(ping_host_forever(host_id))
        ping_tasks[host_id] = task
        print(f"[PING] Task started for host {host_id}")

async def ping_worker():
    print("[WORKER] Launching all tasks...")  # 👈
    db: Session = SessionLocal()
    host_ids = db.scalars(select(HostDB.id)).all()
    db.close()

    async with asyncio.TaskGroup() as tg:
        for host_id in host_ids:
            print(f"[WORKER] Creating task for {host_id}")  # 👈
            ping_tasks[host_id] = tg.create_task(ping_host_forever(host_id))

