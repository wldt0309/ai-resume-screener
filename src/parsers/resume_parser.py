"""
简历解析模块 - Resume Parser
支持 PDF 和 DOCX 格式，自动提取关键字段
"""

import re
import uuid
from pathlib import Path
from typing import TypedDict, Optional
from datetime import datetime

import pdfplumber
from docx import Document as DocxDocument

# 学历关键词映射
EDUCATION_KEYWORDS = {
    "博士": ["博士", "PhD", "Doctor", " Doctorate"],
    "硕士": ["硕士", "MBA", "研究生", "Master", "MSc", "MA "],
    "本科": ["本科", "学士", "Bachelor", "BS ", "BA ", "BSc", "BA"],
    "大专": ["大专", "Associate", "College"],
}

# 常见技能关键词
SKILL_KEYWORDS = [
    # 编程语言
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R ", "MATLAB", "Perl",
    # Web/框架
    "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI",
    "Spring", "Spring Boot", "Rails", "Laravel", "Next.js", "Nuxt",
    # 数据/AI
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Keras",
    "LangChain", "LLM", "OpenAI", "GPT", "Claude",
    # 云/DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
    "Jenkins", "GitLab CI", "GitHub Actions", "Linux", "Nginx",
    # 数据工程
    "Spark", "Hadoop", "Kafka", "Flink", "Airflow", "dbt",
    "ETL", "DataPipeline", "Hive", "HBase",
    # 其他
    "Git", "REST", "GraphQL", "gRPC", "Microservices", "Agile", "Scrum",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "Excel", "Power BI", "Tableau", "Figma",
]


class ResumeData(TypedDict):
    """简历解析结果数据结构"""
    id: str
    filename: str
    raw_text: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    education: Optional[str]
    years_experience: Optional[int]
    skills: list[str]
    raw_json: dict
    created_at: str


class ResumeParseError(Exception):
    """简历解析异常"""
    pass


class UnsupportedFormatError(ResumeParseError):
    """不支持的文件格式"""
    pass


class ParseFailedError(ResumeParseError):
    """解析失败"""
    pass


def extract_email(text: str) -> Optional[str]:
    """从文本中提取邮箱"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else None


def extract_phone(text: str) -> Optional[str]:
    """从文本中提取手机号（中国大陆格式）"""
    # 移除空格和连字符
    cleaned = re.sub(r'[\s\-]', '', text)
    # 匹配中国大陆手机号（1开头11位）
    pattern = r'(?:86)?1[3-9]\d{9}'
    matches = re.findall(pattern, cleaned)
    if matches:
        phone = matches[0]
        # 清理非数字字符
        return re.sub(r'\D', '', phone)[-11:]
    return None


def extract_name(text: str) -> Optional[str]:
    """从文本中提取姓名（启发式：文件开头、非邮箱格式的短词）"""
    lines = text.strip().split('\n')
    for line in lines[:5]:  # 看前5行
        line = line.strip()
        # 跳过空行和邮箱
        if not line or '@' in line:
            continue
        # 跳过包含关键词的行
        skip_patterns = ['简历', 'Resume', 'CV', '电话', 'Tel', 'Email',
                         '地址', 'Address', '教育', 'Education', '经验',
                         'Experience', '技能', 'Skills']
        if any(p in line for p in skip_patterns):
            continue
        # 姓名通常是2-4个汉字或2-20个英文字母
        if re.match(r'^[\u4e00-\u9fa5]{2,4}$', line):
            return line
        if re.match(r'^[A-Za-z][A-Za-z\s]{1,19}$', line):
            return line
    return None


def extract_education(text: str) -> Optional[str]:
    """从文本中提取最高学历"""
    for level, keywords in EDUCATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return level
    return None


def extract_skills(text: str) -> list[str]:
    """从文本中提取技能关键词"""
    found = []
    text_upper = text.upper()
    for skill in SKILL_KEYWORDS:
        # 精确匹配（处理 Rust vs Rusty 这样的问题）
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            # 避免重复（小写后去重）
            if skill.lower() not in [s.lower() for s in found]:
                found.append(skill)
    return found


def extract_years_experience(text: str) -> Optional[int]:
    """从文本中提取工作年限"""
    # 匹配 "X年经验"、"X 年工作经验"、"工作 X 年" 等模式
    patterns = [
        r'(\d+)\s*年\s*(?:以上\s*)?(?:工作\s*)?经验',
        r'工作\s*(\d+)\s*年',
        r'(\d+)\s*年\s*以上',
    ]
    years_list = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            years = int(m)
            if 0 < years <= 50:  # 合理范围
                years_list.append(years)
    return max(years_list) if years_list else None


def parse_pdf(file_path: str | Path) -> str:
    """
    解析 PDF 文件，提取纯文本

    Args:
        file_path: PDF 文件路径

    Returns:
        提取的纯文本内容

    Raises:
        ParseFailedError: 解析失败
    """
    try:
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n'.join(text_parts)
    except Exception as e:
        raise ParseFailedError(f"PDF 解析失败: {e}") from e


def parse_docx(file_path: str | Path) -> str:
    """
    解析 DOCX 文件，提取纯文本

    Args:
        file_path: DOCX 文件路径

    Returns:
        提取的纯文本内容

    Raises:
        ParseFailedError: 解析失败
    """
    try:
        doc = DocxDocument(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return '\n'.join(paragraphs)
    except Exception as e:
        raise ParseFailedError(f"DOCX 解析失败: {e}") from e


def parse_resume(file_path: str | Path) -> ResumeData:
    """
    解析简历文件（PDF/DOCX），提取结构化信息

    Args:
        file_path: 简历文件路径

    Returns:
        ResumeData 结构，包含解析结果

    Raises:
        UnsupportedFormatError: 不支持的格式
        ParseFailedError: 解析失败
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()

    # 提取文本
    if suffix == '.pdf':
        raw_text = parse_pdf(path)
    elif suffix == '.docx':
        raw_text = parse_docx(path)
    else:
        raise UnsupportedFormatError(
            f"不支持的格式: {suffix}，仅支持 PDF 和 DOCX"
        )

    if not raw_text or len(raw_text.strip()) < 20:
        raise ParseFailedError("文件内容过少，无法解析")

    # 提取各字段
    name = extract_name(raw_text)
    email = extract_email(raw_text)
    phone = extract_phone(raw_text)
    education = extract_education(raw_text)
    skills = extract_skills(raw_text)
    years_experience = extract_years_experience(raw_text)

    return ResumeData(
        id=str(uuid.uuid4()),
        filename=path.name,
        raw_text=raw_text,
        name=name,
        email=email,
        phone=phone,
        education=education,
        years_experience=years_experience,
        skills=skills,
        raw_json={
            "parsing_method": "rule_based",
            "fields_extracted": {
                "name": name is not None,
                "email": email is not None,
                "phone": phone is not None,
                "education": education is not None,
                "skills": len(skills),
                "years_experience": years_experience is not None,
            }
        },
        created_at=datetime.now().isoformat(),
    )


def parse_resume_with_llm(
    file_path: str | Path,
    llm_provider: callable,
    model: str = "gpt-4o-mini"
) -> ResumeData:
    """
    使用 LLM 增强解析（当规则解析不理想时）

    Args:
        file_path: 简历文件路径
        llm_provider: LLM 调用函数，接收 prompt 返回文本
        model: 使用的模型

    Returns:
        LLM 解析的 ResumeData
    """
    # 先用规则解析获取原始文本
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == '.pdf':
        raw_text = parse_pdf(path)
    elif suffix == '.docx':
        raw_text = parse_docx(path)
    else:
        raise UnsupportedFormatError(f"不支持的格式: {suffix}")

    # 构建 LLM 解析 prompt
    prompt = f"""请从以下简历文本中提取关键信息，返回 JSON 格式：

简历内容：
---
{raw_text[:4000]}
---

提取字段：
- name: 姓名（字符串）
- email: 邮箱（字符串）
- phone: 电话（字符串）
- education: 最高学历（博士/硕士/本科/大专/未知）
- years_experience: 工作年限（整数）
- skills: 技能列表（字符串数组，最多10个核心技能）
- summary: 简历摘要（50字以内）

只返回 JSON，不要有其他内容。"""

    try:
        result_text = llm_provider(prompt)
        # 简单解析 JSON（实际应用中应使用 json.loads）
        import json
        # 尝试提取 JSON
        import re as re2
        json_match = re2.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            data = json.loads(json_match.group())
            return ResumeData(
                id=str(uuid.uuid4()),
                filename=path.name,
                raw_text=raw_text,
                name=data.get("name"),
                email=data.get("email"),
                phone=data.get("phone"),
                education=data.get("education"),
                years_experience=data.get("years_experience"),
                skills=data.get("skills", []),
                raw_json={
                    "parsing_method": "llm_enhanced",
                    "model": model,
                    "llm_raw": data,
                },
                created_at=datetime.now().isoformat(),
            )
    except Exception as e:
        # LLM 失败时降级到规则解析
        pass

    # 降级：使用规则解析
    return parse_resume(file_path)


# ============ 测试代码 ============
if __name__ == "__main__":
    import json

    # 演示用测试（无真实文件）
    demo_resume = ResumeData(
        id="demo-001",
        filename="张三_高级Python工程师.pdf",
        raw_text="""张三
        13812345678
        zhangsan@example.com
        
        教育背景
        北京大学 计算机科学 硕士 2015-2018
        
        工作经历
        字节跳动 高级工程师 2018-至今
        技能：Python Django LangChain PostgreSQL AWS Docker
        8年互联网后端开发经验""",
        name="张三",
        email="zhangsan@example.com",
        phone="13812345678",
        education="硕士",
        years_experience=8,
        skills=["Python", "Django", "LangChain", "PostgreSQL", "AWS", "Docker"],
        raw_json={"parsing_method": "demo"},
        created_at=datetime.now().isoformat(),
    )

    print("=" * 50)
    print("简历解析演示结果")
    print("=" * 50)
    print(f"姓名: {demo_resume['name']}")
    print(f"邮箱: {demo_resume['email']}")
    print(f"电话: {demo_resume['phone']}")
    print(f"学历: {demo_resume['education']}")
    print(f"年限: {demo_resume['years_experience']} 年")
    print(f"技能: {', '.join(demo_resume['skills'])}")
    print()
    print("完整 JSON:")
    print(json.dumps(demo_resume, ensure_ascii=False, indent=2))
