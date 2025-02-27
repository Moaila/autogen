"""
@Author: 李文皓
@Date: 2025/2/26
@Description: 修正版辩论系统 v2.2
"""
from autogen import ConversableAgent, config_list_from_json

config_list = config_list_from_json("OAI_CONFIG_LIST.json")

MODEL_CONFIG = {
    "deepseek-chat": {
        "filter": {"model": ["deepseek-chat"]},
        "temperature": 0.7,
        "role_prompt": "侧重情感表达和人文关怀"
    },
    "deepseek-reasoner": {
        "filter": {"model": ["deepseek-reasoner"]},
        "temperature": 0.3, 
        "role_prompt": "强调逻辑严密性和技术可行性"
    }
}

DEBATE_TOPIC = "人工智能是否应该拥有情感能力"

# 动态生成系统提示
def create_system_message(position: str, model_type: str) -> str:
    role_spec = MODEL_CONFIG[model_type]["role_prompt"]
    return f"""作为{position}方辩手，你需：
1. 每次发言必须包含：【总结对方观点】->【逻辑漏洞分析】->【举证反驳】三部分
2. 使用{role_spec}的论证风格
3. 技术类论点必须引用一些技术理论或案例
4. 伦理类论点需关联哲学理论（如康德主义、功利主义）"""

# 初始化辩论智能体
pro_agent = ConversableAgent(
    name="正方_V3",
    system_message=create_system_message("正", "deepseek-chat"),
    llm_config={
        "config_list": [c for c in config_list if c["model"] == "deepseek-chat"],
        "temperature": MODEL_CONFIG["deepseek-chat"]["temperature"]
    },
    human_input_mode="NEVER",
    max_consecutive_auto_reply=1
)

con_agent = ConversableAgent(
    name="反方_R1",
    system_message=create_system_message("反", "deepseek-reasoner"),
    llm_config={
        "config_list": [c for c in config_list if c["model"] == "deepseek-reasoner"],
        "temperature": MODEL_CONFIG["deepseek-reasoner"]["temperature"]
    },
    human_input_mode="NEVER",
    max_consecutive_auto_reply=1
)

# 智能终止条件检测
def debate_termination_check(last_message: str, history: list) -> bool:
    termination_keywords = ["共识", "认同", "agree", "conclusion"]
    if any(kw in last_message.lower() for kw in termination_keywords):
        return True
    return len(history) >= 8  # 最大4轮交锋

# 启动深度辩论
debate_process = pro_agent.initiate_chat(
    con_agent,
    message=f"本次辩题为{DEBATE_TOPIC}，请从技术伦理角度展开论述",
    max_turns=8,
    termination_condition=lambda recipient, messages, sender, config: debate_termination_check(messages[-1]["content"], messages)
)

# 生成技术型辩论报告
def generate_technical_report(history):
    report = ["\n=== 辩论技术分析 ==="]
    references = set()
    
    for idx, msg in enumerate(history):
        speaker = msg["name"]
        content = msg["content"]
        report.append(f"[Round {idx//2+1}] {speaker}: {content[:120]}...")
        
        # 提取学术引用
        if "arXiv:" in content:
            refs = [r.split("arXiv:")[1][:9] for r in content.split() if "arXiv:" in r]
            references.update(refs)
    
    report.append(f"\n学术引用({len(references)}篇): " + ", ".join(f"arXiv:{r}" for r in references))
    return "\n".join(report)

print(generate_technical_report(debate_process.chat_history))

