# AI 简历筛选助手

> GSD + OpenSpec + Superpowers + gstack 完整流水线实战项目

AI 简历筛选系统：上传 PDF/DOCX 简历 + 粘贴 JD → 自动解析 → 胜任力评分 → 可视化结果

---

## 快速开始

### 1. 安装依赖

```bash
cd /mnt/c/Users/wangl/ai-resume-screener

pip install streamlit pdfplumber python-docx python-dotenv -q
```

### 2. 运行 Web UI

```bash
python -m streamlit run app.py --server.port 8501 --server.headless true
```

浏览器打开 http://localhost:8501

### 3. 运行 Agent 流水线

```bash
# 运行全部 Agent
python agents/run_agents.py

# 只运行架构师
python agents/run_agents.py --role architect

# 列出所有 Agent
python agents/run_agents.py --list
```

---

## 项目架构

```
ai-resume-screener/
├── app.py                          # Streamlit Web UI
├── src/
│   ├── llm_wrapper.py              # LLM 统一接口
│   ├── parsers/
│   │   ├── resume_parser.py        # 简历解析（PDF/DOCX）
│   │   └── jd_parser.py           # JD 解析
│   ├── scoring/
│   │   └── scoring_engine.py      # 胜任力评分引擎
│   └── db/
│       └── database.py            # SQLite 持久化
├── agents/
│   ├── run_agents.py              # gstack Agent 执行器
│   └── prompts/                   # 角色 System Prompt
│       ├── architect.md
│       ├── developer.md
│       ├── reviewer.md
│       └── qa.md
├── skills/                        # Superpowers Skills
│   ├── resume-parser/
│   ├── jd-parser/
│   ├── scoring-engine/
│   └── ui-builder/
├── GOAL.md                        # GSD 目标文档
├── spec.yaml                      # OpenSpec 规格说明
└── README.md
```

---

## 四个模块的串联逻辑

### Step 1: GSD（Goal-Spec-Do）

**确定"做什么"**，输出 GOAL.md

```markdown
## 最终目标
构建一个 AI 简历筛选系统，能够：
- 上传 PDF/Word 简历，自动解析关键信息
- 上传岗位职责描述（JD）
- 基于 JD 和简历计算匹配度评分
```

### Step 2: OpenSpec

**写成"机器可读的标准"**，输出 spec.yaml

```yaml
# 定义数据模型
data_models:
  Resume:
    fields:
      name: string
      email: string
      skills: list[string]

# 定义验收标准
acceptance_criteria:
  - "上传 PDF 简历后，系统正确提取姓名、邮箱、技能列表"
  - "评分接口返回 5 项分项得分 + 综合得分 + 匹配理由"
```

### Step 3: Superpowers

**定义"怎么做"的 SOP**，输出 skills/*/SKILL.md

```bash
skills/
├── resume-parser/
│   ├── SKILL.md       # 简历解析 SOP
│   └── parse.sh       # 执行脚本
├── jd-parser/
│   ├── SKILL.md
│   └── parse.sh
└── scoring-engine/
    ├── SKILL.md
    └── score.sh
```

### Step 4: gstack

**按角色分工执行**，输出文档

```bash
python agents/run_agents.py
# 输出:
# ✅ ARCHITECT.md      (架构师)
# ✅ DEVELOPER_STATUS.md (开发者)
# ✅ REVIEW.md         (审查者)
# ✅ TEST_REPORT.md    (QA)
```

---

## 核心功能演示

### 简历解析

```python
from src.parsers import parse_resume

resume = parse_resume("张三_高级工程师.pdf")
print(resume["name"])        # "张三"
print(resume["skills"])      # ["Python", "Django", "PostgreSQL"]
print(resume["years_experience"])  # 5
```

### JD 解析

```python
from src.parsers import parse_jd

jd_text = """
招聘高级 Python 工程师
要求：
1. 5年以上 Python 开发经验
2. 熟悉 Django/Flask
3. 本科及以上学历
"""

jd = parse_jd(jd_text)
print(jd["title"])           # "高级 Python 工程师"
print(jd["requirements"])    # [...]
print(jd["education_level"]) # "本科"
```

### 评分

```python
from src.scoring import ScoringEngine

engine = ScoringEngine()
result = engine.score(resume, jd)

print(result["overall_score"])      # 85.5
print(result["skill_match_score"])  # 90.0
print(result["top_matches"])        # ["Python", "Django"]
print(result["gaps"])              # ["AWS", "Kubernetes"]
```

---

## LLM 配置（可选）

系统支持多个 LLM Provider，会自动检测：

### OpenAI
```bash
export OPENAI_API_KEY=sk-...
```

### Anthropic Claude
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 阿里云通义千问
```bash
export DASHSCOPE_API_KEY=sk-...
```

### MiniMax
```bash
export MINIMAX_API_KEY=...
export MINIMAX_GROUP_ID=...
```

**注意**：没有配置 LLM 时，系统会使用规则解析模式，不依赖 API。

---

## 数据库

数据存储在 `data/resume_screener.db`（SQLite）

```python
from src.db import save_resume, get_resume, get_stats

# 保存
save_resume(resume)

# 查询
r = get_resume("resume-id")
print(r["name"])

# 统计
stats = get_stats()
print(stats)  # {'resume_count': 10, 'jd_count': 5, 'score_count': 30, 'avg_score': 72.5}
```

---

## Agent 流水线详解

### 角色定义

| 角色 | System Prompt | 产出 |
|------|--------------|------|
| **Architect** | agents/prompts/architect.md | ARCHITECTURE.md |
| **Developer** | agents/prompts/developer.md | DEVELOPER_STATUS.md |
| **Reviewer** | agents/prompts/reviewer.md | REVIEW.md |
| **QA** | agents/prompts/qa.md | TEST_REPORT.md |

### 执行顺序

```
Architect → Developer → Reviewer → QA
   ↓          ↓            ↓         ↓
ARCHITECT  DEVELOPER   REVIEW    TEST
.md        _STATUS.md   .md      REPORT
                                     .md
```

### 自定义角色

1. 在 `agents/prompts/` 添加新的 `.md` 文件
2. 在 `run_agents.py` 的 `get_agent()` 函数中注册
3. 继承 `AgentRole` 类实现 `execute()` 方法

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `app.py` | Streamlit 主应用 |
| `src/parsers/resume_parser.py` | 简历解析模块 |
| `src/parsers/jd_parser.py` | JD 解析模块 |
| `src/scoring/scoring_engine.py` | 胜任力评分引擎 |
| `src/db/database.py` | SQLite 数据库 |
| `src/llm_wrapper.py` | LLM 统一接口 |
| `agents/run_agents.py` | gstack Agent 执行器 |
| `GOAL.md` | GSD 目标文档 |
| `spec.yaml` | OpenSpec 规格说明 |
| `requirements.txt` | Python 依赖 |

---

## 常见问题

**Q: 简历解析准确率不高？**
A: 系统使用规则解析，准确率依赖简历格式规范化。可以配置 LLM API Key 启用增强解析模式。

**Q: 评分结果如何校准？**
A: 评分权重在 `src/scoring/scoring_engine.py` 的 `ScoringWeights` 类中定义，可以按需调整。

**Q: 如何添加新的评分维度？**
A: 在 `ScoringEngine._score_*` 方法中添加新评分逻辑，在 `ScoreResult` TypedDict 中添加字段。

**Q: 支持批量简历评分吗？**
A: 当前版本 V1 只支持单简历评分，批量功能在 V2 计划中。

---

*Generated with GSD + OpenSpec + Superpowers + gstack*
