from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from bitcask import DB


@asynccontextmanager
async def lifespan(app: FastAPI):
    with DB(os.environ.get("PYCASK_DATA_FILE", "database.data")) as db:
        app.state.db = db
        yield


app = FastAPI(
    title="PyCask REST API",
    description="A Bitcask-based Key-Value database engine written in Python.",
    version="2.0.0",
    lifespan=lifespan,
)


def get_db(request: Request) -> DB:
    return request.app.state.db


# İstemciden gelecek JSON formatı: {"value": "herhangi_bir_deger"}
class KeyValuePayload(BaseModel):
    value: str


@app.get("/")
def health_check(db: DB = Depends(get_db)):
    with db.write_lock:
        return {"status": "online", "engine": "PyCask", "indexed_keys_count": len(db.index)}


# YAZMA / GÜNCELLEME UÇ NOKTASI
@app.put("/keys/{key}", status_code=status.HTTP_200_OK)
def set_key(key: str, payload: KeyValuePayload, db: DB = Depends(get_db)):
    db.put(key, payload.value)
    return {"message": "Key saved successfully", "key": key}


# OKUMA UÇ NOKTASI
@app.get("/keys/{key}")
def get_key(key: str, db: DB = Depends(get_db)):
    val = db.get(key)
    if val is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": val}


# SİLME UÇ NOKTASI
@app.delete("/keys/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(key: str, db: DB = Depends(get_db)):
    success = db.delete(key)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# COMPACTION UÇ NOKTASI
@app.post("/compact", status_code=status.HTTP_200_OK)
def compact_db(db: DB = Depends(get_db)):
    db.compact()
    return {"message": "Compaction completed successfully"}
