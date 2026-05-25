"""
数据库模块 - SQLite 持久化
存储简历、JD、评分结果
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
from contextlib import contextmanager

from ..parsers import ResumeData, JDData
from ..scoring import ScoreResult


DB_PATH = Path(__file__).parent.parent.parent / "data" / "resume_screener.db"


def get_db_path() -> Path:
    """获取数据库路径"""
    return DB_PATH


def ensure_db():
    """确保数据库和表存在"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # 简历表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                raw_text TEXT,
                name TEXT,
                email TEXT,
                phone TEXT,
                education TEXT,
                years_experience INTEGER,
                skills TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # JD 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_descriptions (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                requirements TEXT,
                preferred_skills TEXT,
                experience_years INTEGER,
                experience_range TEXT,
                education_level TEXT,
                salary_range TEXT,
                raw_text TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 评分结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS score_results (
                id TEXT PRIMARY KEY,
                resume_id TEXT NOT NULL,
                jd_id TEXT NOT NULL,
                overall_score REAL NOT NULL,
                skill_match_score REAL NOT NULL,
                experience_score REAL NOT NULL,
                education_score REAL NOT NULL,
                semantic_score REAL NOT NULL,
                reasons TEXT,
                top_matches TEXT,
                gaps TEXT,
                weights_used TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (resume_id) REFERENCES resumes(id),
                FOREIGN KEY (jd_id) REFERENCES job_descriptions(id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumes_email ON resumes(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_resume ON score_results(resume_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_jd ON score_results(jd_id)")

        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ============ 简历操作 ============
def save_resume(resume: ResumeData) -> str:
    """
    保存简历到数据库

    Args:
        resume: ResumeData 对象

    Returns:
        resume_id
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO resumes
            (id, filename, raw_text, name, email, phone, education,
             years_experience, skills, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            resume.get("id") or str(uuid.uuid4()),
            resume["filename"],
            resume["raw_text"],
            resume.get("name"),
            resume.get("email"),
            resume.get("phone"),
            resume.get("education"),
            resume.get("years_experience"),
            json.dumps(resume.get("skills", []), ensure_ascii=False),
            json.dumps(resume.get("raw_json", {}), ensure_ascii=False),
            resume.get("created_at") or datetime.now().isoformat(),
        ))
        conn.commit()
        return resume.get("id") or cursor.lastrowid


def get_resume(resume_id: str) -> Optional[ResumeData]:
    """根据 ID 获取简历"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_resume(row)
        return None


def list_resumes(limit: int = 50, offset: int = 0) -> list[ResumeData]:
    """列出所有简历"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM resumes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [_row_to_resume(row) for row in cursor.fetchall()]


def _row_to_resume(row: sqlite3.Row) -> ResumeData:
    """将数据库行转换为 ResumeData"""
    return ResumeData(
        id=row["id"],
        filename=row["filename"],
        raw_text=row["raw_text"] or "",
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        education=row["education"],
        years_experience=row["years_experience"],
        skills=json.loads(row["skills"]) if row["skills"] else [],
        raw_json=json.loads(row["raw_json"]) if row["raw_json"] else {},
        created_at=row["created_at"],
    )


# ============ JD 操作 ============
def save_jd(jd: JDData) -> str:
    """
    保存 JD 到数据库

    Args:
        jd: JDData 对象

    Returns:
        jd_id
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO job_descriptions
            (id, title, company, requirements, preferred_skills,
             experience_years, experience_range, education_level,
             salary_range, raw_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            jd.get("id") or str(uuid.uuid4()),
            jd.get("title"),
            jd.get("company"),
            json.dumps(jd.get("requirements", []), ensure_ascii=False),
            json.dumps(jd.get("preferred_skills", []), ensure_ascii=False),
            jd.get("experience_years"),
            json.dumps(jd.get("experience_range")) if jd.get("experience_range") else None,
            jd.get("education_level"),
            json.dumps(jd.get("salary_range")) if jd.get("salary_range") else None,
            jd.get("raw_text"),
            jd.get("created_at") or datetime.now().isoformat(),
        ))
        conn.commit()
        return jd.get("id") or cursor.lastrowid


def get_jd(jd_id: str) -> Optional[JDData]:
    """根据 ID 获取 JD"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_descriptions WHERE id = ?", (jd_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_jd(row)
        return None


def list_jds(limit: int = 50, offset: int = 0) -> list[JDData]:
    """列出所有 JD"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM job_descriptions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [_row_to_jd(row) for row in cursor.fetchall()]


def _row_to_jd(row: sqlite3.Row) -> JDData:
    """将数据库行转换为 JDData"""
    return JDData(
        id=row["id"],
        title=row["title"],
        company=row["company"],
        requirements=json.loads(row["requirements"]) if row["requirements"] else [],
        preferred_skills=json.loads(row["preferred_skills"]) if row["preferred_skills"] else [],
        experience_years=row["experience_years"],
        experience_range=json.loads(row["experience_range"]) if row["experience_range"] else None,
        education_level=row["education_level"],
        salary_range=json.loads(row["salary_range"]) if row["salary_range"] else None,
        raw_text=row["raw_text"] or "",
        created_at=row["created_at"],
    )


# ============ 评分结果操作 ============
def save_score_result(result: ScoreResult) -> str:
    """
    保存评分结果

    Args:
        result: ScoreResult 对象

    Returns:
        score_id
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO score_results
            (id, resume_id, jd_id, overall_score, skill_match_score,
             experience_score, education_score, semantic_score,
             reasons, top_matches, gaps, weights_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.get("id") or str(uuid.uuid4()),
            result["resume_id"],
            result["jd_id"],
            result["overall_score"],
            result["skill_match_score"],
            result["experience_score"],
            result["education_score"],
            result["semantic_score"],
            json.dumps(result.get("reasons", []), ensure_ascii=False),
            json.dumps(result.get("top_matches", []), ensure_ascii=False),
            json.dumps(result.get("gaps", []), ensure_ascii=False),
            json.dumps(result.get("weights_used", {}), ensure_ascii=False),
            result.get("created_at") or datetime.now().isoformat(),
        ))
        conn.commit()
        return result.get("id") or cursor.lastrowid


def get_scores_for_resume(resume_id: str) -> list[ScoreResult]:
    """获取某简历的所有评分结果"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM score_results WHERE resume_id = ? ORDER BY overall_score DESC",
            (resume_id,)
        )
        return [_row_to_score(row) for row in cursor.fetchall()]


def get_scores_for_jd(jd_id: str) -> list[ScoreResult]:
    """获取某 JD 的所有评分结果"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM score_results WHERE jd_id = ? ORDER BY overall_score DESC",
            (jd_id,)
        )
        return [_row_to_score(row) for row in cursor.fetchall()]


def _row_to_score(row: sqlite3.Row) -> ScoreResult:
    """将数据库行转换为 ScoreResult"""
    return ScoreResult(
        id=row["id"],
        resume_id=row["resume_id"],
        jd_id=row["jd_id"],
        overall_score=row["overall_score"],
        skill_match_score=row["skill_match_score"],
        experience_score=row["experience_score"],
        education_score=row["education_score"],
        semantic_score=row["semantic_score"],
        reasons=json.loads(row["reasons"]) if row["reasons"] else [],
        top_matches=json.loads(row["top_matches"]) if row["top_matches"] else [],
        gaps=json.loads(row["gaps"]) if row["gaps"] else [],
        weights_used=json.loads(row["weights_used"]) if row["weights_used"] else {},
        created_at=row["created_at"],
    )


# ============ 统计 ============
def get_stats() -> dict:
    """获取统计信息"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM resumes")
        resume_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM job_descriptions")
        jd_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM score_results")
        score_count = cursor.fetchone()["count"]

        cursor.execute("SELECT AVG(overall_score) as avg FROM score_results")
        avg_score = cursor.fetchone()["avg"] or 0

        return {
            "resume_count": resume_count,
            "jd_count": jd_count,
            "score_count": score_count,
            "avg_score": round(avg_score, 1),
        }


# ============ 测试 ============
if __name__ == "__main__":
    import json

    # 初始化数据库
    ensure_db()
    print("✅ 数据库初始化完成")

    # 测试保存简历
    demo_resume = ResumeData(
        id="test-001",
        filename="张三.pdf",
        raw_text="这是简历内容",
        name="张三",
        email="zhangsan@example.com",
        phone="13812345678",
        education="硕士",
        years_experience=5,
        skills=["Python", "Django", "PostgreSQL"],
        raw_json={},
        created_at=datetime.now().isoformat(),
    )
    save_resume(demo_resume)
    print(f"✅ 简历已保存: {demo_resume['id']}")

    # 测试保存 JD
    demo_jd = JDData(
        id="test-jd-001",
        title="Python工程师",
        company="字节",
        requirements=["5年经验", "Python"],
        preferred_skills=["Django"],
        experience_years=5,
        education_level="本科",
        raw_text="",
        created_at=datetime.now().isoformat(),
    )
    save_jd(demo_jd)
    print(f"✅ JD 已保存: {demo_jd['id']}")

    # 测试保存评分结果
    demo_score = ScoreResult(
        id="score-001",
        resume_id=demo_resume["id"],
        jd_id=demo_jd["id"],
        overall_score=85.5,
        skill_match_score=90.0,
        experience_score=80.0,
        education_score=85.0,
        semantic_score=82.0,
        reasons=["技能匹配", "经验符合"],
        top_matches=["Python", "Django"],
        gaps=["AWS"],
        weights_used={"skill_match": 0.4, "experience": 0.3},
        created_at=datetime.now().isoformat(),
    )
    save_score_result(demo_score)
    print(f"✅ 评分结果已保存: {demo_score['id']}")

    # 测试统计
    stats = get_stats()
    print(f"\n📊 统计: {json.dumps(stats, ensure_ascii=False)}")
