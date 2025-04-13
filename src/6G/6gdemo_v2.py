"""
@Author: liwenhao
@功能：语音输入大模型决策系统
@Date: 2025/4/13
@需要安装SpeechRecognition pyaudio两个python库并保持联网
"""
import speech_recognition as sr
from autogen import ConversableAgent, config_list_from_json
import re
import logging

# 配置日志级别
logging.basicConfig(level=logging.CRITICAL)

# 初始化语音识别组件
recognizer = sr.Recognizer()
microphone = sr.Microphone()

# 联邦学习初始化
config_list = config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={"model": ["deepseek-reasoner"]}
)[:1]

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
        "seed": 42
    }
)

def enhanced_listener():
    """静默版语音监听"""
    with microphone as source:
        try:
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
            return recognizer.recognize_google(audio, language="zh-CN")
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return None
        except Exception as e:
            logging.error(f"Audio Error: {str(e)}")
            return None

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

# 交互主循环
print("联邦学习语音决策系统启动（说‘退出’结束）")
with microphone as source:
    recognizer.adjust_for_ambient_noise(source, duration=1)

# 用户提示
print("\n请提出您的需求：", end="", flush=True)

while True:
    # 语音捕获阶段
    voice_input = enhanced_listener()
    
    if voice_input:
        # 退出指令检测
        if any(kw in voice_input for kw in ["退出", "exit", "quit"]):
            print("\n接收到终止指令")
            break
        
        # 显示输入内容
        print(f"\n{voice_input}")
        
        # 执行决策逻辑
        decision = secure_decision(voice_input)
        print(f"{decision}")
        
        # 新提示等待下次输入
        print("\n请提出您的需求：", end="", flush=True)
    else:
        # 无输入时显示等待提示
        print(".", end="", flush=True)

print("系统安全关闭")