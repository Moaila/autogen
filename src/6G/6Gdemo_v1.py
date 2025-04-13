from autogen import ConversableAgent, config_list_from_json
import json
import re

# 禁用所有非必要输出
import logging
logging.basicConfig(level=logging.CRITICAL)

# def load_single_config():
#     """安全加载单个API配置"""
#     try:
#         configs = config_list_from_json(
#             "OAI_CONFIG_LIST.json",
#             filter_dict={"model": ["deepseek-chat"]}
#         )
#         return [configs[0]] if configs else None
#     except Exception as e:
#         logging.error("配置加载失败: " + str(e))
#         return None
def load_single_config():
    try:
        configs = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={"model": ["deepseek-reasoner"]}  # 确保筛选目标模型
        )
        print("[调试] 加载的配置:", json.dumps(configs, indent=2))  # 添加调试输出
        return [configs[0]] if configs else None
    except Exception as e:
        print("[错误] 配置加载失败:", str(e))
        return None
# 初始化单模型代理
config_list = load_single_config()
agent = ConversableAgent(
    name="FL_Switch",
    system_message="""严格按以下规则决策：
    
    【模式特征】
    触发模式1（区块链）的安全信号词：
    干扰/入侵/攻击/漏洞/异常/可疑/未授权访问/恶意/篡改/伪造
    相关表述示例：
    * "系统被干扰" → 1  
    * "流量异常波动" → 1
    * "检测到可疑行为" → 1
    * "数据完整性存疑" → 1

    触发模式0（传统）的资源信号词：
    资源占用/卡顿/延迟/性能下降/负载过高/内存不足/CPU满载
    相关表述示例：
    * "资源占用过多" → 0
    * "程序运行卡顿" → 0 
    * "内存不够用" → 0

    语义分析规则
    1. 优先识别安全威胁相关词汇（即使没有直接提到"攻击"）
    2. 资源问题描述中若含安全要素，仍优先判定为模式1
    3. 双重因素存在时，安全优先于资源效率
    
    【输出规范】
    - 只输出单个数字0或1
    - 禁止任何解释性文字
    - 示例：
      用户：检测到异常节点 → 1
      用户：内存不足 → 0""",
    llm_config={
        "config_list": config_list,
        "temperature": 0.8,
        "request_timeout": 15
    }
)

def secure_execution(user_input):
    """安全执行流程"""
    try:
        response = agent.generate_reply(messages=[{
            "role": "user",
            "content": user_input
        }])
        return re.search(r'\b[01]\b', str(response)).group()
    except Exception as e:
        logging.debug(f"决策异常: {str(e)}")
        return "0"  # 故障安全默认值

print("联邦学习模式切换器（输入 exit 退出）")
while True:
    try:
        user_input = input("\n当前状态描述 > ").strip()
        if user_input.lower() in ['exit', 'quit']:
            break
            
        # 执行安全决策
        decision = secure_execution(user_input)
        print(decision)
        
    except KeyboardInterrupt:
        break

print("\n系统安全关闭")