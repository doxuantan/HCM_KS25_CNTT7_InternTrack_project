from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import router as api_router
from app.db.database import Base, engine, get_db
from sqlalchemy import text
from sqlalchemy.orm import Session
import app.models


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router)

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Server đang hoạt động bình thường"
    }


@app.get("/test-connection")
def test_connection(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"message":"kết nối thành công database"}
    except Exception as e:
        return {"message":f"Kết nối thất bại Lỗi {e}"}
