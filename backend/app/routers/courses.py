from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.models.schema import CourseCreate, CourseResponse
from app.db.storage import storage
from app.core.auth import get_optional_user, get_current_user

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("", response_model=CourseResponse)
def create_course(
    req: CourseCreate,
    current_user: dict = Depends(get_current_user)
):
    res = storage.create_course(
        title=req.title,
        description=req.description or "",
        owner_id=current_user["id"],
        visibility="private",
        is_demo=0
    )
    return CourseResponse(**res)

@router.get("", response_model=List[CourseResponse])
def list_courses(optional_user: Optional[dict] = Depends(get_optional_user)):
    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False
    courses = storage.list_courses(user_id=user_id, is_admin=is_admin)
    return [CourseResponse(**c) for c in courses]

@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: str, optional_user: Optional[dict] = Depends(get_optional_user)):
    c = storage.get_course(course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")

    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False
    if not storage.is_course_accessible(course_id, user_id=user_id, is_admin=is_admin):
        # Prevent IDOR: do not reveal existence of private courses to unauthorized users
        raise HTTPException(status_code=404, detail="Course not found")

    return CourseResponse(**c)

@router.get("/{course_id}/topics", response_model=List[str])
def get_course_topics(course_id: str, optional_user: Optional[dict] = Depends(get_optional_user)):
    c = storage.get_course(course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")

    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False
    if not storage.is_course_accessible(course_id, user_id=user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    return storage.get_all_topics(course_id)

@router.delete("/{course_id}")
def delete_course(
    course_id: str,
    current_user: dict = Depends(get_current_user)
):
    course = storage.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    is_admin = current_user.get("role") == "admin"
    if course.get("is_demo") or course.get("visibility") == "shared_demo":
        if not is_admin:
            raise HTTPException(status_code=403, detail="Shared demo courses are read-only and cannot be deleted")

    if not is_admin and course.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Course not found")

    storage.delete_course(course_id)
    return {"deleted": True, "course_id": course_id}
