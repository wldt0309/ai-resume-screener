"""
AI 简历筛选助手 - Streamlit Web UI
GSD + OpenSpec + Superpowers + gstack 实战项目

运行方式:
    streamlit run app.py --server.port 8501 --server.headless true
"""

import streamlit as st
import time
import json
from pathlib import Path
from datetime import datetime

# 导入项目模块
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers import ResumeData, JDData, parse_resume, parse_jd
from src.scoring import ScoringEngine, quick_score
from src.db import (
    ensure_db, save_resume, get_resume, list_resumes,
    save_jd, get_jd, list_jds,
    save_score_result, get_scores_for_resume,
    get_stats
)
from src.llm_wrapper import get_llm

# ============ 页面配置 ============
st.set_page_config(
    page_title="AI 简历筛选助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============ 自定义样式 ============
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .score-excellent { color: #28a745; font-weight: bold; }
    .score-good { color: #17a2b8; font-weight: bold; }
    .score-average { color: #ffc107; font-weight: bold; }
    .score-poor { color: #dc3545; font-weight: bold; }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


# ============ 辅助函数 ============
def get_score_color(score: float) -> str:
    """根据分数返回颜色类"""
    if score >= 80:
        return "score-excellent"
    elif score >= 60:
        return "score-good"
    elif score >= 40:
        return "score-average"
    else:
        return "score-poor"


def format_score(score: float) -> str:
    """格式化分数显示"""
    return f"{score:.1f}"


def render_score_gauge(score: float, label: str) -> None:
    """渲染单个得分指标"""
    color = get_score_color(score)
    st.metric(
        label=label,
        value=f"{format_score(score)}/100",
        help=f"得分: {score}"
    )


# ============ 初始化 ============
def init_session_state():
    """初始化 session state"""
    if "current_resume" not in st.session_state:
        st.session_state.current_resume = None
    if "current_jd" not in st.session_state:
        st.session_state.current_jd = None
    if "current_score" not in st.session_state:
        st.session_state.current_score = None
    if "history" not in st.session_state:
        st.session_state.history = []
    if "llm_manager" not in st.session_state:
        st.session_state.llm_manager = get_llm()


init_session_state()

def main():
    # ============ 头部 ============
    st.markdown('<p class="main-header">🤖 AI 简历筛选助手</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">'
        '上传简历 JD → 自动解析 → 胜任力评分 → 智能匹配建议'
        '</p>',
        unsafe_allow_html=True
    )

    # ============ 主布局 ============
    col_upload, col_result = st.columns([1, 2], gap="large")

    # --- 左侧：上传区域 ---
    with col_upload:
        st.header("📤 上传数据")

        # 简历上传
        st.subheader("简历上传")
        resume_file = st.file_uploader(
            "支持 PDF / DOCX",
            type=["pdf", "docx"],
            help="上传候选人简历"
        )

        if resume_file:
            with st.spinner("解析简历中..."):
                # 保存到临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(
                    suffix=Path(resume_file.name).suffix,
                    delete=False
                ) as f:
                    f.write(resume_file.getbuffer())
                    temp_path = f.name

                try:
                    resume_data = parse_resume(temp_path)
                    st.session_state.current_resume = resume_data
                    save_resume(resume_data)

                    st.success(f"✅ 解析完成")
                    with st.expander("📋 简历信息", expanded=True):
                        st.write(f"**姓名:** {resume_data.get('name') or '未提取'}")
                        st.write(f"**邮箱:** {resume_data.get('email') or '未提取'}")
                        st.write(f"**学历:** {resume_data.get('education') or '未提取'}")
                        st.write(f"**工作年限:** {resume_data.get('years_experience') or '未提取'} 年")
                        skills = resume_data.get('skills', [])
                        if skills:
                            st.write(f"**技能 ({len(skills)}):**")
                            st.write(", ".join(skills[:10]))
                        else:
                            st.write("**技能:** 未提取")
                except Exception as e:
                    st.error(f"❌ 解析失败: {e}")
                finally:
                    Path(temp_path).unlink(missing_ok=True)

        st.divider()

        # JD 输入
        st.subheader("📝 岗位职责 (JD)")

        # JD 历史选择
        existing_jds = list_jds(limit=10)
        jd_options = ["-- 新建 JD --"] + [
            f"{jd.get('title') or '未命名'} ({jd.get('company') or '未知公司'})"
            for jd in existing_jds
        ]
        selected_jd = st.selectbox("选择已保存的 JD", jd_options)

        if selected_jd != "-- 新建 JD --":
            jd_index = jd_options.index(selected_jd) - 1
            jd_data = existing_jds[jd_index]
            st.session_state.current_jd = jd_data
            st.success(f"已加载: {jd_data.get('title')}")

        jd_text = st.text_area(
            "粘贴 JD 内容",
            height=200,
            placeholder="例如:\n招聘高级Python工程师\n要求:\n1. 本科及以上学历\n2. 5年以上Python开发经验\n3. 熟悉Django/Flask\n4. 精通MySQL/Redis",
            help="粘贴完整的岗位描述"
        )

        if jd_text and jd_text != st.session_state.get("last_jd_text"):
            with st.spinner("解析 JD 中..."):
                try:
                    jd_data = parse_jd(jd_text)
                    st.session_state.current_jd = jd_data
                    save_jd(jd_data)
                    st.session_state.last_jd_text = jd_text
                    st.success("✅ JD 解析完成")
                except Exception as e:
                    st.error(f"❌ JD 解析失败: {e}")

        # JD 预览
        if st.session_state.current_jd:
            jd = st.session_state.current_jd
            with st.expander("📋 JD 解析结果", expanded=True):
                st.write(f"**岗位:** {jd.get('title') or '未提取'}")
                st.write(f"**公司:** {jd.get('company') or '未提取'}")
                st.write(f"**学历要求:** {jd.get('education_level') or '未提取'}")
                st.write(f"**经验要求:** {jd.get('experience_years') or '未提取'} 年")
                if jd.get('preferred_skills'):
                    st.write(f"**加分技能:** {', '.join(jd.get('preferred_skills', []))}")

        st.divider()

        # 评分按钮
        analyze_disabled = not (st.session_state.current_resume and st.session_state.current_jd)
        if st.button(
            "🚀 开始评分",
            type="primary",
            disabled=analyze_disabled,
            use_container_width=True
        ):
            if st.session_state.current_resume and st.session_state.current_jd:
                with st.spinner("AI 正在评分，请稍候..."):
                    time.sleep(1)  # 模拟处理时间

                    # 执行评分
                    engine = ScoringEngine()
                    score_result = engine.score(
                        st.session_state.current_resume,
                        st.session_state.current_jd
                    )

                    # 保存结果
                    save_score_result(score_result)
                    st.session_state.current_score = score_result

                    # 添加到历史
                    st.session_state.history.append({
                        "resume": st.session_state.current_resume["filename"],
                        "jd": st.session_state.current_jd.get("title", "JD"),
                        "score": score_result["overall_score"],
                        "timestamp": datetime.now().isoformat(),
                    })

                    st.rerun()

        # 统计信息
        st.divider()
        st.subheader("📊 统计")
        stats = get_stats()
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric("简历数", stats["resume_count"])
        with col_s2:
            st.metric("JD 数", stats["jd_count"])

    # --- 右侧：评分结果 ---
    with col_result:
        st.header("📊 评分结果")

        if st.session_state.current_score:
            score = st.session_state.current_score
            overall = score["overall_score"]

            # 综合得分大卡片
            color_class = get_score_color(overall)
            score_label = (
                "🌟 优秀" if overall >= 80 else
                "👍 良好" if overall >= 60 else
                "⚠️ 一般" if overall >= 40 else
                "❌ 较差"
            )

            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 15px;
                padding: 2rem;
                text-align: center;
                color: white;
                margin-bottom: 1rem;
            ">
                <div style="font-size: 1rem; opacity: 0.9;">综合匹配度</div>
                <div style="font-size: 4rem; font-weight: bold;">{overall:.1f}<span style="font-size: 1.5rem;">/100</span></div>
                <div style="font-size: 1.2rem; margin-top: 0.5rem;">{score_label}</div>
            </div>
            """, unsafe_allow_html=True)

            # 分项得分
            st.subheader("📈 分项得分")
            cols = st.columns(4)
            metrics = [
                ("🎯 技能匹配", score["skill_match_score"]),
                ("💼 经验匹配", score["experience_score"]),
                ("🎓 学历匹配", score["education_score"]),
                ("🔍 语义匹配", score["semantic_score"]),
            ]
            for col, (label, val) in zip(cols, metrics):
                with col:
                    st.metric(label, f"{val:.1f}/100")

            # 技能对比
            st.subheader("🎯 技能对比")

            matched = score.get("top_matches", [])
            gaps = score.get("gaps", [])

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ 已匹配**")
                if matched:
                    for skill in matched[:8]:
                        st.markdown(f":green[• {skill}]")
                else:
                    st.write("无")

            with c2:
                st.markdown("**❌ 差距项**")
                if gaps:
                    for gap in gaps[:8]:
                        st.markdown(f":red[• {gap}]")
                else:
                    st.write("无")

            # 评分理由
            st.subheader("📝 评分依据")
            reasons = score.get("reasons", [])
            if reasons:
                for reason in reasons:
                    st.markdown(f"- {reason}")
            else:
                st.info("暂无评分理由")

            # 权重信息
            with st.expander("⚙️ 评分配置"):
                weights = score.get("weights_used", {})
                st.json(weights)

        else:
            # 无结果状态
            st.info("👆 请上传简历和 JD，然后点击「开始评分」")

            # 显示示例
            st.subheader("💡 示例评分结果")
            st.markdown("""
            | 候选人 | 岗位 | 综合得分 | 技能 | 经验 | 学历 |
            |-------|------|---------|------|------|------|
            | 张三 (5年硕士) | Python工程师 | 85.5 | 90 | 80 | 85 |
            | 李四 (3年本科) | Python工程师 | 72.3 | 75 | 85 | 80 |
            | 王五 (8年博士) | 技术总监 | 65.0 | 60 | 95 | 100 |
            """)

    # ============ 历史记录 ============
    if st.session_state.history:
        st.divider()
        st.header("📜 评分历史")

        history_data = []
        for i, h in enumerate(reversed(st.session_state.history[-10:])):
            history_data.append({
                "序号": i + 1,
                "简历": h["resume"],
                "岗位": h["jd"],
                "得分": f"{h['score']:.1f}",
                "时间": h["timestamp"][:16].replace("T", " ")
            })

        import pandas as pd
        df = pd.DataFrame(history_data)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ============ 入口 ============
if __name__ == "__main__":
    # 确保数据库存在
    ensure_db()
    main()
