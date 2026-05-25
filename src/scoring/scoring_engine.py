"""
胜任力评分引擎 - Scoring Engine
基于简历和 JD 计算匹配度评分
评分权重配置来自 spec.yaml
"""

import uuid
from typing import TypedDict, Optional
from datetime import datetime
from dataclasses import dataclass, field

from ..parsers import ResumeData, JDData


# ============ 评分配置 ============
@dataclass
class ScoringWeights:
    """评分权重配置"""
    skill_match: float = 0.40   # 技能匹配
    experience: float = 0.30     # 工作经验
    education: float = 0.15      # 学历
    semantic: float = 0.15       # 语义相似度


# 不同岗位类型的预设权重
PRESET_WEIGHTS = {
    "default": ScoringWeights(),
    "tech_lead": ScoringWeights(
        skill_match=0.50,
        experience=0.30,
        education=0.10,
        semantic=0.10,
    ),
    "fresh": ScoringWeights(
        skill_match=0.30,
        experience=0.20,
        education=0.30,
        semantic=0.20,
    ),
    "research": ScoringWeights(
        skill_match=0.30,
        experience=0.20,
        education=0.35,
        semantic=0.15,
    ),
}


# 学历等级映射（用于比较）
EDUCATION_LEVELS = {
    "博士": 4,
    "硕士": 3,
    "本科": 2,
    "大专": 1,
    None: 0,
}

# 经验年限范围映射（用于比较）
EXPERIENCE_RANGES = {
    "junior": (0, 2),
    "mid": (3, 5),
    "senior": (5, 10),
    "expert": (10, 100),
}


# ============ 评分结果数据结构 ============
class ScoreResult(TypedDict):
    """评分结果数据结构"""
    id: str
    resume_id: str
    jd_id: str
    overall_score: float          # 综合得分 (0-100)
    skill_match_score: float     # 技能匹配得分 (0-100)
    experience_score: float      # 经验匹配得分 (0-100)
    education_score: float       # 学历匹配得分 (0-100)
    semantic_score: float        # 语义匹配得分 (0-100)
    reasons: list[str]           # 评分理由
    top_matches: list[str]       # 匹配的技能
    gaps: list[str]             # 未匹配的要求
    weights_used: dict           # 使用的权重
    created_at: str


@dataclass
class SkillMatchDetail:
    """技能匹配详情"""
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)


# ============ 评分器实现 ============
class ScoringEngine:
    """
    胜任力评分引擎

    支持多种评分模式：
    1. 规则评分（rule-based）：基于关键词匹配
    2. 语义评分（semantic）：基于向量相似度（需要 embedding 模型）
    3. 混合评分：规则 + 语义加权
    """

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        初始化评分引擎

        Args:
            weights: 评分权重，默认使用 default
        """
        self.weights = weights or PRESET_WEIGHTS["default"]

    def set_profile(self, profile: str) -> "ScoringEngine":
        """设置岗位类型预设权重"""
        if profile in PRESET_WEIGHTS:
            self.weights = PRESET_WEIGHTS[profile]
        return self

    def score(
        self,
        resume: ResumeData,
        jd: JDData,
        resume_skills: Optional[list[str]] = None,
        jd_required_skills: Optional[list[str]] = None,
        jd_preferred_skills: Optional[list[str]] = None,
    ) -> ScoreResult:
        """
        计算简历与 JD 的匹配度评分

        Args:
            resume: 简历解析结果
            jd: JD 解析结果
            resume_skills: 简历技能列表（如果与 resume.skills 不同）
            jd_required_skills: JD 必须技能（如果与 jd.requirements 不同）
            jd_preferred_skills: JD 加分技能

        Returns:
            ScoreResult 评分结果
        """
        # 使用传入的参数或默认值
        r_skills = resume_skills or resume.get("skills", [])
        jd_required = jd_required_skills or []
        jd_preferred = jd_preferred_skills or jd.get("preferred_skills", [])

        # 1. 技能匹配评分
        skill_detail = self._score_skills(r_skills, jd_required, jd_preferred)
        skill_score = self._calculate_skill_score(skill_detail, jd_required, jd_preferred)

        # 2. 经验评分
        exp_score, exp_reasons = self._score_experience(
            resume.get("years_experience"),
            jd.get("experience_years"),
            jd.get("experience_range"),
        )

        # 3. 学历评分
        edu_score, edu_reasons = self._score_education(
            resume.get("education"),
            jd.get("education_level"),
        )

        # 4. 语义评分（这里用简化版，实际可用 embedding）
        semantic_score, semantic_reasons = self._score_semantic(r_skills, jd.get("requirements", []))

        # 5. 综合评分
        overall = (
            skill_score * self.weights.skill_match +
            exp_score * self.weights.experience +
            edu_score * self.weights.education +
            semantic_score * self.weights.semantic
        )
        overall = round(overall, 1)

        # 6. 生成理由
        reasons = []
        reasons.extend(skill_detail.reasons)
        reasons.extend(exp_reasons)
        reasons.extend(edu_reasons)
        reasons.extend(semantic_reasons)

        return ScoreResult(
            id=str(uuid.uuid4()),
            resume_id=resume.get("id", ""),
            jd_id=jd.get("id", ""),
            overall_score=overall,
            skill_match_score=round(skill_score, 1),
            experience_score=round(exp_score, 1),
            education_score=round(edu_score, 1),
            semantic_score=round(semantic_score, 1),
            reasons=reasons[:10],  # 最多10条理由
            top_matches=skill_detail.matched,
            gaps=skill_detail.missing,
            weights_used={
                "skill_match": self.weights.skill_match,
                "experience": self.weights.experience,
                "education": self.weights.education,
                "semantic": self.weights.semantic,
            },
            created_at=datetime.now().isoformat(),
        )

    def _score_skills(
        self,
        resume_skills: list[str],
        jd_required: list[str],
        jd_preferred: list[str],
    ) -> SkillMatchDetail:
        """
        评分技能匹配

        策略：
        - 必须技能全部匹配：满分
        - 必须技能部分匹配：按比例扣分
        - 加分技能匹配：额外加分（不计入100%上限）
        """
        detail = SkillMatchDetail()
        reasons = []

        r_skills_lower = [s.lower() for s in resume_skills]

        # 检查必须技能
        for skill in jd_required:
            skill_lower = skill.lower()
            if skill_lower in r_skills_lower:
                detail.matched.append(skill)
            else:
                # 模糊匹配（检查部分重叠）
                found = False
                for r_skill in resume_skills:
                    if skill_lower in r_skill.lower() or r_skill.lower() in skill_lower:
                        detail.partial.append(skill)
                        found = True
                        break
                if not found:
                    detail.missing.append(skill)

        # 检查加分技能
        for skill in jd_preferred:
            skill_lower = skill.lower()
            if skill_lower in r_skills_lower:
                detail.matched.append(f"{skill} (加分)")
            else:
                for r_skill in resume_skills:
                    if skill_lower in r_skill.lower() or r_skill.lower() in skill_lower:
                        detail.partial.append(f"{skill} (部分)")
                        break

        # 生成理由
        if detail.matched:
            reasons.append(f"✅ 技能匹配：{', '.join(detail.matched[:5])}")
        if detail.partial:
            reasons.append(f"⚠️ 部分匹配：{', '.join(detail.partial[:3])}")
        if detail.missing:
            reasons.append(f"❌ 缺失技能：{', '.join(detail.missing[:3])}")

        detail.reasons = reasons
        return detail

    def _calculate_skill_score(
        self,
        detail: SkillMatchDetail,
        jd_required: list[str],
        jd_preferred: list[str],
    ) -> float:
        """
        计算技能匹配得分 (0-100)

        规则：
        - 必须技能每缺失一个扣 15 分
        - 加分技能每个匹配加 5 分（上限 100）
        """
        total_required = len(jd_required) if jd_required else 5  # 默认5个
        matched_count = len(detail.matched) + len(detail.partial) * 0.5

        # 基础分：必须技能匹配率
        if total_required > 0:
            base_score = (matched_count / total_required) * 80  # 最高80分
        else:
            base_score = 100

        # 加分项：加分技能匹配
        preferred_bonus = 0
        preferred_matched = sum(1 for s in detail.matched if "(加分)" in s)
        preferred_partial = sum(1 for s in detail.partial if "(部分)" in s)
        preferred_bonus = (preferred_matched + preferred_partial * 0.3) * 5
        preferred_bonus = min(preferred_bonus, 20)  # 最多加20分

        return min(100, base_score + preferred_bonus)

    def _score_experience(
        self,
        resume_years: Optional[int],
        jd_years: Optional[int],
        jd_range: Optional[tuple[int, int]],
    ) -> tuple[float, list[str]]:
        """
        评分工作经验匹配

        规则：
        - 在 JD 范围内：满分
        - 低于下限：扣分（差距越大扣越多）
        - 高于上限：满分（经验过剩不扣分）
        """
        reasons = []
        score = 100.0

        if resume_years is None and jd_years is None:
            return 80.0, ["ℹ️ 双方均未提供工作年限，按基准分计算"]

        if resume_years is None:
            return 60.0, ["⚠️ 简历未提取到工作年限"]

        if jd_years is None and jd_range is None:
            return 80.0, ["ℹ️ JD 未明确工作年限要求，按基准分计算"]

        # 确定 JD 年限范围
        if jd_range:
            jd_min, jd_max = jd_range
        elif jd_years:
            jd_min = max(0, jd_years - 2)
            jd_max = jd_years + 2
        else:
            jd_min, jd_max = 0, 100

        # 评分
        if jd_min <= resume_years <= jd_max:
            score = 100.0
            reasons.append(f"✅ 工作年限 {resume_years} 年符合 JD 要求 ({jd_min}-{jd_max} 年)")
        elif resume_years < jd_min:
            gap = jd_min - resume_years
            score = max(0, 100 - gap * 15)
            reasons.append(f"⚠️ 工作年限 {resume_years} 年低于 JD 要求（差 {gap} 年）")
        else:
            # 经验过剩不扣分
            score = 100.0
            reasons.append(f"ℹ️ 工作年限 {resume_years} 年超过 JD 上限（{jd_max} 年），经验充足")

        return score, reasons

    def _score_education(
        self,
        resume_education: Optional[str],
        jd_education: Optional[str],
    ) -> tuple[float, list[str]]:
        """
        评分学历匹配

        规则：
        - JD 要求 <= 简历学历：满分
        - JD 要求 > 简历学历：按等级差距扣分
        """
        reasons = []
        score = 100.0

        if resume_education is None:
            if jd_education is None or jd_education == "不限":
                return 80.0, ["ℹ️ 双方均未明确学历要求"]
            return 70.0, ["⚠️ 简历未提取到学历信息"]

        if jd_education is None or jd_education == "不限":
            return 90.0, ["ℹ️ JD 未明确学历要求"]

        r_level = EDUCATION_LEVELS.get(resume_education, 0)
        j_level = EDUCATION_LEVELS.get(jd_education, 0)

        if r_level >= j_level:
            score = 100.0
            reasons.append(f"✅ 学历 {resume_education} 满足 JD 要求 {jd_education}")
        else:
            gap = j_level - r_level
            score = max(0, 100 - gap * 30)
            reasons.append(f"⚠️ 学历 {resume_education} 低于 JD 要求 {jd_education}")

        return score, reasons

    def _score_semantic(
        self,
        resume_skills: list[str],
        jd_requirements: list[str],
    ) -> tuple[float, list[str]]:
        """
        评分语义相关性（简化版）

        实际生产中应使用 Embedding 模型计算向量相似度
        这里用技能词与要求句子的关键词重叠度估算
        """
        reasons = []
        score = 75.0  # 基准分

        if not resume_skills or not jd_requirements:
            return score, ["ℹ️ 语义评分使用默认分（缺少数据）"]

        # 统计技能在要求中出现的次数
        skill_mentions = 0
        all_text = " ".join(jd_requirements).lower()

        for skill in resume_skills:
            if skill.lower() in all_text:
                skill_mentions += 1

        # 计算重叠率
        overlap_rate = min(1.0, skill_mentions / max(1, len(resume_skills) * 0.5))
        score = 60 + overlap_rate * 40  # 60-100 分

        if overlap_rate > 0.5:
            reasons.append(f"✅ 简历技能与 JD 要求高度相关（重叠率 {overlap_rate:.0%}）")
        elif overlap_rate > 0.2:
            reasons.append(f"ℹ️ 简历技能与 JD 要求部分相关（重叠率 {overlap_rate:.0%}）")

        return round(score, 1), reasons


# ============ 快捷函数 ============
def quick_score(resume: ResumeData, jd: JDData) -> ScoreResult:
    """使用默认权重快速评分"""
    engine = ScoringEngine()
    return engine.score(resume, jd)


# ============ 测试代码 ============
if __name__ == "__main__":
    import json

    # 演示数据
    demo_resume = ResumeData(
        id="resume-demo-001",
        filename="张三_高级Python工程师.pdf",
        raw_text="",
        name="张三",
        email="zhangsan@example.com",
        phone="13812345678",
        education="硕士",
        years_experience=5,
        skills=["Python", "Django", "PostgreSQL", "Redis", "Docker", "AWS", "Git"],
        raw_json={},
        created_at=datetime.now().isoformat(),
    )

    demo_jd = JDData(
        id="jd-demo-001",
        title="高级 Python 后端工程师",
        company="字节跳动",
        requirements=[
            "本科及以上学历，计算机相关专业",
            "5年以上 Python 开发经验",
            "熟练掌握 Django 或 Flask 框架",
            "精通 MySQL、Redis",
            "有 Docker 经验",
        ],
        preferred_skills=["AWS", "Kubernetes", "LangChain"],
        experience_years=5,
        experience_range=(5, 10),
        education_level="本科",
        salary_range=(30, 60),
        raw_text="",
        created_at=datetime.now().isoformat(),
    )

    print("=" * 60)
    print("胜任力评分引擎 - 演示结果")
    print("=" * 60)

    # 使用默认权重评分
    engine = ScoringEngine()
    result = engine.score(demo_resume, demo_jd)

    print(f"\n📊 综合得分: {result['overall_score']} / 100")
    print(f"\n📈 分项得分:")
    print(f"   技能匹配: {result['skill_match_score']}")
    print(f"   工作经验: {result['experience_score']}")
    print(f"   学历:     {result['education_score']}")
    print(f"   语义:     {result['semantic_score']}")

    print(f"\n✅ 匹配技能: {', '.join(result['top_matches'])}")
    print(f"❌ 差距项:  {', '.join(result['gaps'])}")

    print(f"\n📝 评分理由:")
    for reason in result['reasons']:
        print(f"   {reason}")

    print(f"\n🔢 使用权重: {result['weights_used']}")

    print("\n完整 JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
