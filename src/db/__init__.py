"""数据库模块"""
from .database import (
    ensure_db,
    get_db_path,
    save_resume,
    get_resume,
    list_resumes,
    save_jd,
    get_jd,
    list_jds,
    save_score_result,
    get_scores_for_resume,
    get_scores_for_jd,
    get_stats,
)

__all__ = [
    "ensure_db",
    "get_db_path",
    "save_resume",
    "get_resume",
    "list_resumes",
    "save_jd",
    "get_jd",
    "list_jds",
    "save_score_result",
    "get_scores_for_resume",
    "get_scores_for_jd",
    "get_stats",
]
