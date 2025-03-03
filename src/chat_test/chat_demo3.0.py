"""
@Author: 李文皓
@Date: 2024/3/1
@Description: DeepSeek双模型辩论系统 v3.6（稳定版）
"""
import os
import re
import shutil
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from autogen import ConversableAgent, config_list_from_json

# ---------- 跨平台缓存清理 ----------
def clean_autogen_cache():
    """智能清理所有可能的缓存路径"""
    cache_paths = [
        Path.home() / ".cache" / "autogen",  # Linux/macOS
        Path(os.environ.get("LOCALAPPDATA", "")) / "autogen" / "cache",  # Windows
        Path.cwd() / ".cache",  # 项目级缓存
    ]
    
    for path in cache_paths:
        try:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                print(f"♻️ 已清理缓存：{path}")
            else:
                print(f"✅ 无需清理：{path} 不存在")
        except Exception as e:
            print(f"⚠️ 清理异常：{path} - {str(e)}")

clean_autogen_cache()

# ---------- API配置加载 ----------
config_list = config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={
        "model": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": ["https://api.deepseek.com"]  # 确认API端点
    }
)

# 验证配置加载
assert len(config_list) >= 2, "至少需要配置两个模型，请检查OAI_CONFIG_LIST.json"

# ---------- 辩论参数配置 ----------
DEBATE_TOPIC = "人工智能是否应该拥有情感能力"
MAX_ROUNDS = 12  # 每个辩手发言次数
TOTAL_TURNS = MAX_ROUNDS * 2

# ---------- 模型配置 ----------
MODEL_CONFIG = {
    "deepseek-chat": {
        "temperature": 0.7,
        "role_prompt": "侧重情感表达和人文关怀论证"
    },
    "deepseek-reasoner": {
        "temperature": 0.3,
        "role_prompt": "强调逻辑严谨性和技术可行性"
    }
}

# ---------- 智能体初始化 ----------
def create_agent(position: str, model_type: str):
    return ConversableAgent(
        name=f"{position}_{model_type.split('-')[1]}",
        system_message=f"""作为{position}方辩手：
1. 每次发言必须包含：
   - 总结对方观点（引用原话）
   - 分析逻辑漏洞（至少2点）
   - 举证反驳（含技术案例）
2. 技术论点格式：arXiv:1234.5678
3. 伦理论点需明确哲学流派""",
        llm_config={
            "config_list": [c for c in config_list if c["model"] == model_type],
            "temperature": MODEL_CONFIG[model_type]["temperature"],
            "timeout": 1000  # 增加超时时间
        },
        human_input_mode="NEVER",
        max_consecutive_auto_reply=6
    )

# 初始化双方辩手
pro_agent = create_agent("正方", "deepseek-chat")
con_agent = create_agent("反方", "deepseek-reasoner")

# ---------- 辩论控制模块 ----------
def should_terminate(messages):
    """改进的终止条件检测"""
    pro_count = sum(1 for m in messages if "正方" in m["name"])
    con_count = sum(1 for m in messages if "反方" in m["name"])
    return pro_count >= MAX_ROUNDS and con_count >= MAX_ROUNDS

# ---------- 主辩论流程 ----------
try:
    debate_process = pro_agent.initiate_chat(
        con_agent,
        message=f"本次将进行{MAX_ROUNDS}轮深入辩论，主题：{DEBATE_TOPIC}",
        max_turns=TOTAL_TURNS,
        termination_condition=lambda _, msgs, __, ___: should_terminate(msgs)
    )
except Exception as e:
    print(f"辩论异常终止：{str(e)}")
    exit(1)

# ---------- 输出保存模块 ----------
def save_full_transcript(history, filename="debate_transcript.txt"):
    """保存完整对话记录"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"辩论主题：{DEBATE_TOPIC}\n")
        f.write(f"总回合数：{len(history)}\n")
        f.write("="*60 + "\n")
        
        for idx, msg in enumerate(history, 1):
            f.write(f"【第{(idx+1)//2}轮】{msg['name']}：\n")
            f.write(f"{msg['content']}\n")
            f.write("-"*60 + "\n")
        
        # 添加引用统计
        arxiv_refs = set()
        for msg in history:
            parts = msg["content"].split()
            for part in parts:
                if part.startswith("arXiv:"):
                    arxiv_refs.add(part[6:14])  # 提取8位编号
                    
        if arxiv_refs:
            f.write("\n学术引用清单：\n")
            f.write("\n".join(f"- arXiv:{ref}" for ref in sorted(arxiv_refs)))

save_full_transcript(debate_process.chat_history)
print("辩论记录已保存至 debate_transcript.txt")