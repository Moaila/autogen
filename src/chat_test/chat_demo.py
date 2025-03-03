"""
@Author: 李文皓
@Date: 2025/2/26
@Description: 一个简单的对话系统演示v1.0
"""
from autogen import AssistantAgent, UserProxyAgent, config_list_from_json, GroupChat, GroupChatManager

# 加载 DeepSeek 配置
config_list = config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={"model": ["deepseek-chat"]}
)

# 创建辩论主题
TOPIC = "人工智能是否应该拥有情感能力？"

# 定义智能体角色
debater_1 = AssistantAgent(
    name="正方辩手",
    llm_config={
        "config_list": config_list,
        "messages": [
            {
                "role": "system",
                "content": f"你坚定支持{TOPIC}，请用严谨的逻辑和案例维护观点"
            }
        ]
    }
)

debater_2 = AssistantAgent(
    name="反方辩手", 
    llm_config={
        "config_list": config_list,
        "messages": [
            {
                "role": "system",
                "content": f"你坚决反对{TOPIC}，需找出对方逻辑漏洞并提供反例"
            }
        ]
    }
)

# 创建用户代理控制器
user_proxy = UserProxyAgent(
    name="主持人",
    human_input_mode="TERMINATE",
    code_execution_config={"work_dir": "debate"},
    system_message="负责维持辩论秩序，当双方达成共识或争论超过5轮时终止对话"
)

# 启动群组对话
group_chat = GroupChat(
    agents=[user_proxy, debater_1, debater_2],
    messages=[],
    max_round=8,  # 最大对话轮次
    speaker_selection_method="auto"
)

manager = GroupChatManager(
    groupchat=group_chat,
    llm_config={"config_list": config_list}
)

# 开始辩论
user_proxy.initiate_chat(
    manager,
    message=f"现在开始关于『{TOPIC}』的辩论，首先请正方陈述观点"
)