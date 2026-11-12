from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import router as api_router
from app.core.config import settings
from app.db.database import Base, engine, get_db
from sqlalchemy import text
from sqlalchemy.orm import Session
import app.models


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
