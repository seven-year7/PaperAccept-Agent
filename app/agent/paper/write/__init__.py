"""
论文写作子模块：三个相互独立的智能体（各文件自带系统/用户提示词常量），由子图串接。

- plan_agent：大纲规划（首版 + Replan），WRITE_PLAN_*_PROMPT
- execute_runner：并行章节写作，SECTION_WRITER_* / SECTION_REVIEWER_*
- global_reviewer_agent：全局总编辑，GLOBAL_EDITOR_*；驱动 writeAudit 路由

LangGraph 节点仅负责 phase SSE，智能体主体在 write/agents/ 各文件中。
"""
