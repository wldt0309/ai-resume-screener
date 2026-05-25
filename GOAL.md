# AI 简历筛选助手 - Goal

## 1. 最终目标

构建一个 AI 简历筛选系统，能够：

- 上传 PDF/Word 简历，自动解析关键信息（姓名、学历、工作年限、核心技能）
- 上传岗位职责描述（JD）
- 基于 JD 和简历计算匹配度评分（胜任力模型）
- 提供 Streamlit 前端界面

## 2. 成功标准

- ✅ 支持 PDF 和 Word (.docx) 简历上传
- ✅ 自动提取简历字段（姓名、邮箱、工作年限、技能列表）
- ✅ 解析 JD 并提取关键要求
- ✅ 输出 0-100 匹配度评分 + 详细理由
- ✅ Web 界面可访问

## 3. 约束条件

- 使用 Python（Streamlit + LangChain）
- 本地运行，无需云服务
- 单机版，数据库用 SQLite

## 4. 里程碑

- [x] M1: 简历解析核心（PDF/Word → 结构化数据）
- [x] M2: JD 解析 + 胜任力评分模型
- [x] M3: Streamlit 前端界面
- [x] M4: Agent 流水线（gstack 角色化执行）

## 5. 技术栈

- Python 3.10+
- Streamlit (Web UI)
- pdfplumber (PDF 解析)
- python-docx (Word 解析)
- SQLite (持久化)
- LLM 包装器（支持 OpenAI/Anthropic/阿里云/MiniMax）

## 6. 四个模块的集成

```
GSD (Goal-Spec-Do)
    ↓ 确定"做什么"
    产出: GOAL.md + spec.yaml

OpenSpec (精确规格)
    ↓ 写成机器可读的标准
    产出: spec.yaml (acceptance_criteria, data_models, api_endpoints)

Superpowers (Skills 封装)
    ↓ 定义 SOP
    产出: skills/*/SKILL.md + scripts

gstack (角色化 Agent 执行)
    ↓ 按角色分工执行
    产出: ARCHITECTURE.md / src/*.py / REVIEW.md / TEST_REPORT.md
```
