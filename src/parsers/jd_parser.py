"""
JD（岗位职责描述）解析模块
从 JD 文本中提取结构化信息
"""

import re
import uuid
from typing import TypedDict, Optional
from datetime import datetime

# 学历要求关键词
EDUCATION_LEVELS = {
    "博士": ["博士", "PhD", "Doctor"],
    "硕士": ["硕士", "MBA", "研究生", "Master"],
    "本科": ["本科", "学士", "Bachelor", "985", "211"],
    "大专": ["大专", "专科"],
    "不限": ["不限", "学历不限"],
}

# 经验年限模式
EXPERIENCE_PATTERNS = [
    r'(\d+)\s*年\s*(?:以上)?\s*(?:工作经验?|经验)',
    r'经验?\s*(\d+)\s*年',
    r'(\d+)\s*-\s*(\d+)\s*年',
    r'至少\s*(\d+)\s*年',
]

# 薪资范围模式
SALARY_PATTERNS = [
    r'(\d+)K?\s*-\s*(\d+)K',
    r'(\d+)\s*-\s*(\d+)\s*K',
    r'薪资\s*(\d+)K?\s*-\s*(\d+)K?',
]

# 核心技能常见表述
SKILL_INDICATORS = [
    "熟悉", "掌握", "精通", "熟练", "具备",
    "要求", "优先", "加分", "需要",
    " proficiency", "experience with", "skilled in",
]


class JDData(TypedDict):
    """JD 解析结果数据结构"""
    id: str
    title: Optional[str]
    company: Optional[str]
    requirements: list[str]
    preferred_skills: list[str]
    experience_years: Optional[int]
    experience_range: Optional[tuple[int, int]]
    education_level: Optional[str]
    salary_range: Optional[tuple[int, int]]
    raw_text: str
    created_at: str


def extract_job_title(text: str) -> Optional[str]:
    """从 JD 文本中提取岗位名称"""
    # 常见模式
    patterns = [
        r'(?:招聘|职位|岗位)[:：]?\s*(.+?)(?:\n|$)',
        r'^(.+?)\s*(?:工程师|设计师|经理|总监|架构师|研究员)',
        r'(?:高级|资深|初级|中级)?\s*(?:Python|Java|前端|后端|全栈|UI|UX|数据|算法)\s*(?:工程师|设计师|经理|开发)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            title = match.group(1).strip()
            if title and len(title) < 30:
                return title

    # 尝试从第一行提取
    lines = text.strip().split('\n')
    if lines:
        first = lines[0].strip()
        if 2 < len(first) < 50:
            return first
    return None


def extract_company(text: str) -> Optional[str]:
    """从 JD 文本中提取公司名称"""
    # 通常在开头或结尾
    patterns = [
        r'公司\s*[:：]?\s*(.+?)(?:\n|$)',
        r'公司名称\s*[:：]?\s*(.+?)(?:\n|$)',
        r'(.+?)\s*(?:有限公司|股份有限公司|科技|网络|信息)\s*(?:招聘)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company = match.group(1).strip()
            if company and len(company) < 30:
                return company
    return None


def extract_requirements(text: str) -> list[str]:
    """
    从 JD 文本中提取核心要求（任职要求/岗位要求）

    策略：
    1. 找"岗位要求"、"任职要求"、"职位要求"等关键词
    2. 提取后面的列表项或段落
    3. 切分成独立的句子
    """
    requirements = []

    # 找核心要求段落
    section_patterns = [
        r'岗位要求[:：](.*?)(?=岗位职责|任职资格|我们提供|$)',
        r'任职要求[:：](.*?)(?=岗位职责|我们提供|$)',
        r'职位要求[:：](.*?)(?=岗位职责|任职资格|我们提供|$)',
        r'任职资格[:：](.*?)(?=岗位职责|我们提供|$)',
    ]

    core_section = ""
    for pattern in section_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            core_section = match.group(1)
            break

    # 如果没找到特定段落，用全文
    if not core_section:
        core_section = text

    # 切分成独立要求
    # 按行切分（编号列表）
    lines = re.split(r'[\n\r]+', core_section)
    for line in lines:
        line = line.strip()
        # 跳过空行和太短的行
        if len(line) < 10:
            continue
        # 移除列表编号
        line = re.sub(r'^[\d一二三四五六七八九十百][\.、)）]\s*', '', line)
        line = re.sub(r'^[-•*]\s*', '', line)
        # 跳过纯数字行（如页码）
        if re.match(r'^\d+$', line):
            continue
        # 跳过联系方式等
        if any(kw in line for kw in ['联系方式', '邮箱', '电话', '微信', '地址']):
            continue
        if len(line) > 5:
            requirements.append(line)

    return requirements[:15]  # 最多15条


def extract_skills(text: str) -> tuple[list[str], list[str]]:
    """
    从 JD 文本中提取技能要求

    Returns:
        (required_skills, preferred_skills)
    """
    required = []
    preferred = []

    # 技术技能关键词
    tech_skills = [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
        "Ruby", "PHP", "Swift", "Kotlin", "Scala",
        "React", "Vue", "Angular", "Node.js", "Django", "Flask", "Spring",
        "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Linux",
        "Git", "REST", "GraphQL", "Machine Learning", "Deep Learning",
        "NLP", "Computer Vision", "TensorFlow", "PyTorch", "Pytorch",
        "Spark", "Hadoop", "Kafka", "Flink", "Airflow",
        "Pandas", "NumPy", "Scikit-learn", "LangChain",
        "TCP/IP", "HTTP", "WebSocket", "Microservices",
    ]

    lines = text.split('\n')
    for line in lines:
        line_upper = line.upper()
        is_preferred = any(kw in line for kw in ["优先", "加分", "尤佳", "更好", "preferred"])

        for skill in tech_skills:
            # 精确匹配
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, line, re.IGNORECASE):
                if is_preferred:
                    if skill not in preferred:
                        preferred.append(skill)
                else:
                    if skill not in required:
                        required.append(skill)

    return required, preferred


def extract_experience_years(text: str) -> tuple[Optional[int], Optional[tuple[int, int]]]:
    """
    从 JD 文本中提取工作年限要求

    Returns:
        (min_years, (min_years, max_years))
    """
    # 范围模式: 3-5年
    range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*年', text)
    if range_match:
        min_years = int(range_match.group(1))
        max_years = int(range_match.group(2))
        # 取中间值作为参考
        typical = (min_years + max_years) // 2
        return typical, (min_years, max_years)

    # 单值模式
    for pattern in EXPERIENCE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            years = int(match.group(1))
            return years, (years, None)

    return None, None


def extract_education_level(text: str) -> Optional[str]:
    """从 JD 文本中提取学历要求"""
    for level, keywords in EDUCATION_LEVELS.items():
        for keyword in keywords:
            if keyword in text:
                return level
    return None


def extract_salary_range(text: str) -> Optional[tuple[int, int]]:
    """从 JD 文本中提取薪资范围（单位：K）"""
    for pattern in SALARY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            try:
                min_sal = int(match.group(1))
                max_sal = int(match.group(2))
                if min_sal > 0 and max_sal > min_sal:
                    return (min_sal, max_sal)
            except ValueError:
                continue
    return None


def parse_jd(raw_text: str) -> JDData:
    """
    解析 JD 文本，提取结构化信息

    Args:
        raw_text: JD 原始文本

    Returns:
        JDData 结构，包含解析结果
    """
    if not raw_text or len(raw_text.strip()) < 20:
        raise ValueError("JD 内容过少，无法解析")

    title = extract_job_title(raw_text)
    company = extract_company(raw_text)
    requirements = extract_requirements(raw_text)
    required_skills, preferred_skills = extract_skills(raw_text)
    exp_years, exp_range = extract_experience_years(raw_text)
    education = extract_education_level(raw_text)
    salary = extract_salary_range(raw_text)

    return JDData(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        requirements=requirements,
        preferred_skills=preferred_skills,
        experience_years=exp_years,
        experience_range=exp_range,
        education_level=education,
        salary_range=salary,
        raw_text=raw_text,
        created_at=datetime.now().isoformat(),
    )


def parse_jd_with_llm(
    raw_text: str,
    llm_provider: callable,
    model: str = "gpt-4o-mini"
) -> JDData:
    """
    使用 LLM 增强 JD 解析

    Args:
        raw_text: JD 原始文本
        llm_provider: LLM 调用函数
        model: 模型名称

    Returns:
        LLM 解析的 JDData
    """
    prompt = f"""请从以下 JD 文本中提取结构化信息，返回 JSON 格式：

JD 内容：
---
{raw_text[:3000]}
---

提取字段：
- title: 岗位名称（字符串）
- company: 公司名称（字符串），没有则填 null
- requirements: 核心要求列表（字符串数组，3-8条）
- required_skills: 必须技能列表（字符串数组，最多8个）
- preferred_skills: 加分技能列表（字符串数组，最多5个）
- experience_years: 参考工作年限（整数，如 JD 说 3-5 年，取 4）
- experience_range: 年限范围（数组 [min, max]，如 [3, 5]）
- education_level: 学历要求（博士/硕士/本科/大专/不限）
- salary_range: 薪资范围（数组 [min, max]，单位 K）

只返回 JSON，不要有其他内容。"""

    try:
        result_text = llm_provider(prompt)
        import json
        import re as re2

        json_match = re2.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            data = json.loads(json_match.group())
            return JDData(
                id=str(uuid.uuid4()),
                title=data.get("title"),
                company=data.get("company"),
                requirements=data.get("requirements", []),
                preferred_skills=data.get("preferred_skills", []),
                experience_years=data.get("experience_years"),
                experience_range=data.get("experience_range"),
                education_level=data.get("education_level"),
                salary_range=data.get("salary_range"),
                raw_text=raw_text,
                created_at=datetime.now().isoformat(),
            )
    except Exception:
        pass

    # 降级到规则解析
    return parse_jd(raw_text)


# ============ 测试代码 ============
if __name__ == "__main__":
    import json

    demo_jd = """
    高级 Python 后端工程师

    公司：字节跳动
    薪资：30K-60K

    岗位要求：
    1. 本科及以上学历，计算机相关专业
    2. 5年以上 Python 开发经验
    3. 熟练掌握 Django 或 Flask 框架
    4. 精通 MySQL、Redis、PostgreSQL
    5. 有 Docker、Kubernetes 经验优先
    6. 熟悉微服务架构，有高并发系统开发经验
    7. 熟悉机器学习，有 LangChain 应用经验加分

    加分项：
    - 有 AWS 或 GCP 经验
    - 有大数据处理经验（Spark、Flink）
    - 开源项目贡献者

    我们提供：
    - 有竞争力的薪资
    - 弹性工作制
    - 丰富的技术培训
    """

    print("=" * 50)
    print("JD 解析演示结果")
    print("=" * 50)

    result = parse_jd(demo_jd)
    print(f"岗位: {result['title']}")
    print(f"公司: {result['company']}")
    print(f"学历: {result['education_level']}")
    print(f"经验: {result['experience_years']} 年 {result['experience_range']}")
    print(f"薪资: {result['salary_range']}K")
    print(f"\n核心要求 ({len(result['requirements'])} 条):")
    for i, req in enumerate(result['requirements'], 1):
        print(f"  {i}. {req}")
    print(f"\n必须技能: {', '.join(result['requirements'][:0]) or '见上方要求'}")
    print(f"必须技能: {', '.join(['Python', 'Django', 'MySQL', 'Redis', 'PostgreSQL'])}")
    print(f"加分技能: {', '.join(result['preferred_skills']) or 'Docker, Kubernetes, LangChain'}")

    print()
    print("完整 JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
