from autogen import ConversableAgent, config_list_from_json
import re
import logging

# 配置日志级别
logging.basicConfig(level=logging.CRITICAL)

# 精确加载配置
config_list = config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={"model": ["deepseek-reasoner"]}
)[:1]  # 确保只取第一个配置

# 强化版提示词结构
SYSTEM_PROMPT = """联邦学习模式切换决策规则

【输入分析要求】
1. 识别以下关键词特征：
安全类：干扰/攻击/入侵/异常/可疑/恶意/漏洞/非法/伪造/篡改/
资源类：资源占用/卡顿/延迟/负载/内存不足/CPU满载/性能下降/成本高

2. 判断优先级：
- 安全类关键词存在 → 模式1（区块链）
- 仅资源类关键词 → 模式0（传统）
- 双重特征 → 安全优先

【输出规范】
必须严格按以下格式{"decision": 0或1}

示例：
用户：检测到中间人攻击 → {"decision":1}
用户：内存占用率过高 → {"decision":0}
用户：网络延迟增加且有可疑IP → {"decision":1}"""

agent = ConversableAgent(
    name="FL_Switch_Expert",
    system_message=SYSTEM_PROMPT,
    llm_config={
        "config_list": config_list,
        "temperature": 0.7,
        "max_tokens": 50,
        "seed": 42  # 固定随机种子保证稳定性
    }
)

def secure_decision(user_input):
    """强化决策流程"""
    try:
        # 强制JSON格式请求
        response = agent.generate_reply(messages=[{
            "role": "user",
            "content": f"{user_input}。请按指定JSON格式响应。"
        }])
        
        # 强化解析逻辑
        if match := re.search(r'\{\s*"decision"\s*:\s*([01])\s*\}', str(response)):
            return match.group(1)
        return "0"  # 格式错误时默认传统模式
    except Exception as e:
        logging.error(f"决策异常: {str(e)}")
        return "0"

# 测试用例验证
test_cases = [
    ("我的系统现在好像被干扰了", "1"),
    ("电脑资源占用太高了", "0"),
    ("检测到异常流量和未授权访问", "1"),
    ("处理速度变慢但未发现安全问题", "0")
]

print("【验证测试】")
for input_text, expected in test_cases:
    result = secure_decision(input_text)
    print(f"输入：{input_text.ljust(25)} 预期：{expected} 实际：{result}")

# 正式交互
print("\n联邦学习决策系统启动（输入‘exit’或者‘quit’或者‘退出’退出）")
while True:
    try:
        user_input = input("\n状态描述 > ").strip()
        if user_input.lower() in ('exit', 'quit', '退出'):
            break
        print(secure_decision(user_input))
    except KeyboardInterrupt:
        break

print("系统安全关闭")