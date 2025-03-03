"""
@Author: 李文皓
@Date: 2024/3/1
@Description: 完全兼容版双AP协商系统
"""
import random
import json
from typing import Dict, Any
from autogen import ConversableAgent, config_list_from_json

# ---------- API配置加载 ----------
config_list = config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={
        "model": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": ["https://api.deepseek.com"]
    }
)
assert len(config_list) >= 2, "请检查API配置"

# ---------- 物理层参数配置 ----------
CHANNELS = [1, 6, 11]
MAX_INTERFERENCE = -65  # dBm

# ---------- 智能体角色定义 ----------
class APAgent(ConversableAgent):
    def __init__(self, name: str, model_type: str):
        super().__init__(
            name=name,
            system_message=self._build_system_prompt(),
            llm_config={
                "config_list": [c for c in config_list if c["model"] == model_type],
                "temperature": 0.5,
                "timeout": 300
            },
            max_consecutive_auto_reply=3
        )
        self.current_channel = random.choice(CHANNELS)
        self.interference_log = {}
        
        # 注册消息处理器
        self.register_reply(
            trigger="proposal",
            reply_func=self.handle_proposal
        )

    def _build_system_prompt(self):
        return """您是一个无线网络专家，请按以下规则处理信道协商：
1. 分析JSON格式的干扰数据
2. 生成包含技术参数和自然语言解释的响应
3. 必须使用Markdown格式回复"""

    def scan_environment(self):
        """模拟环境扫描"""
        return {
            ch: round(random.uniform(-90, -40), 1)
            for ch in CHANNELS
        }

    def handle_proposal(self, recipient, messages, sender, config):
        """处理提案的核心逻辑"""
        last_msg = messages[-1]
        
        try:
            # 解析JSON数据
            proposal = json.loads(last_msg["content"])
            self.interference_log = self.scan_environment()
            
            # 技术评估
            tech_response = self._generate_tech_eval(proposal)
            
            # 调用大模型生成解释
            llm_reply = self.generate_reply(
                messages=[{
                    "role": "user",
                    "content": f"技术分析：{tech_response}\n请用专业术语解释决策"
                }],
                sender=recipient
            )
            
            # 构建响应
            response_data = {
                "action": "accept" if tech_response["score"] > 0.7 else "reject",
                "channel": self.current_channel,
                "analysis": llm_reply,
                "metrics": tech_response
            }
            
            return True, json.dumps(response_data, ensure_ascii=False)
            
        except json.JSONDecodeError:
            return False, "ERROR: 无效的提案格式"

    def _generate_tech_eval(self, proposal):
        """生成技术评估报告"""
        current_snr = self.interference_log.get(self.current_channel, -90)
        proposed_snr = self.interference_log.get(proposal["channel"], -90)
        
        return {
            "score": round((proposed_snr - current_snr) * proposal["priority"], 2),
            "current_channel": self.current_channel,
            "proposed_channel": proposal["channel"],
            "snr_diff": round(proposed_snr - current_snr, 1)
        }

# ---------- 初始化与执行 ----------
if __name__ == "__main__":
    # 创建两个使用不同模型的AP
    ap1 = APAgent("AP-Controller", "deepseek-chat")
    ap2 = APAgent("AP-AccessPoint", "deepseek-reasoner")

    # 生成初始提案
    initial_proposal = {
        "channel": 6,
        "priority": 0.8,
        "reason": "检测到信道1存在微波炉干扰"
    }

    # 启动协商
    chat_result = ap1.initiate_chat(
        ap2,
        message=json.dumps(initial_proposal, ensure_ascii=False),
        max_turns=4
    )

    # 打印最终配置
    print("\n最终信道分配:")
    print(f"{ap1.name}: 信道 {ap1.current_channel}")
    print(f"{ap2.name}: 信道 {ap2.current_channel}")