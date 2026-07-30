from fastapi import APIRouter

from core.study.ncert import CURRICULUM

router = APIRouter(prefix="/ncert", tags=["ncert"])


@router.get("/classes")
def ncert_classes():
    return sorted(CURRICULUM.keys())


@router.get("/subjects")
def ncert_subjects(class_std: str):
    data = CURRICULUM.get(class_std)
    if not data:
        return []
    return sorted(data.keys())


@router.get("/chapters")
def ncert_chapters(class_std: str, subject: str):
    from core.study.ncert import get_chapters
    chs = get_chapters(class_std, subject)
    if not chs:
        return []
    return chs
