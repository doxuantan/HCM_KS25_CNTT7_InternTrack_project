from fastapi import FastAPI,Depends
from app.db.database import Base,engine,get_db
from sqlalchemy import text
from sqlalchemy.orm import Session
import app.models



app = FastAPI()

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Server đang hoạt động bình thường"
    }

@app.get("/test-connection")
def test_connection(db:Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"message":"kết nối thành công database"}
    except Exception as e:
        return {"message":f"Kết nối thất bại Lỗi {e}"}

