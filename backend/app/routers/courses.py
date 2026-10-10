from fastapi import APIRouter, HTTPException
from typing import List
from app.models.schema import CourseCreate, CourseResponse
from app.db.storage import storage

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("", response_model=CourseResponse)
def create_course(req: CourseCreate):
    res = storage.create_course(title=req.title, description=req.description or "")
    return CourseResponse(**res)

@router.get("", response_model=List[CourseResponse])
def list_courses():
    courses = storage.list_courses()
    return [CourseResponse(**c) for c in courses]

@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: str):
    c = storage.get_course(course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    return CourseResponse(**c)
