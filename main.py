import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Database & Environment Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Database Models
class DBStudent(Base):
    __tablename__ = "students"
    matric_no = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    biometric_mode = Column(String, nullable=False)
    biometric_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    logs = relationship("DBAttendanceLog", back_populates="student")

class DBAttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    matric_no = Column(String, ForeignKey("students.matric_no"), nullable=False)
    course = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="VERIFIED PRESENT")
    student = relationship("DBStudent", back_populates="logs")

Base.metadata.create_all(bind=engine)

# Pydantic Schemas
class StudentRegisterRequest(BaseModel):
    matric_no: str
    full_name: str
    biometric_mode: str
    biometric_key: Optional[str] = None

class AttendanceSignRequest(BaseModel):
    matric_no: str
    course: str

# FastAPI Setup
app = FastAPI(title="Biometric Attendance API")

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

@app.get("/")
def read_root():
    return {"status": "online", "system": "Biometric Attendance API"}

@app.post("/students/register", status_code=201)
def register_student(payload: StudentRegisterRequest, db: Session = Depends(get_db)):
    matric_clean = payload.matric_no.strip().upper()
    existing = db.query(DBStudent).filter(DBStudent.matric_no == matric_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student with this Matric Number is already registered.")
    
    student = DBStudent(
        matric_no=matric_clean,
        full_name=payload.full_name.strip(),
        biometric_mode=payload.biometric_mode,
        biometric_key=payload.biometric_key
    )
    db.add(student)
    db.commit()
    return {"message": "Student registered successfully", "matric": matric_clean}

@app.post("/attendance/sign")
def sign_attendance(payload: AttendanceSignRequest, db: Session = Depends(get_db)):
    matric_clean = payload.matric_no.strip().upper()
    student = db.query(DBStudent).filter(DBStudent.matric_no == matric_clean).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found. Register first.")

    log = DBAttendanceLog(
        matric_no=matric_clean,
        course=payload.course.strip(),
        status="VERIFIED PRESENT"
    )
    db.add(log)
    db.commit()
    return {"message": "Attendance recorded", "student": student.full_name, "matric": matric_clean}

@app.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(DBAttendanceLog).order_by(DBAttendanceLog.timestamp.desc()).all()
    return [{
        "id": l.id,
        "matric": l.matric_no,
        "course": l.course,
        "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "status": l.status
    } for l in logs]
