"""
双Agent动态协商系统（兼容最新AutoGen API）
"""
import json
import re
import random
from autogen import ConversableAgent, config_list_from_json

class NegotiationSystem:
    def __init__(self):
        self.config = config_list_from_json("OAI_CONFIG_LIST.json")
        self._setup_agents()
        
    def _setup_agents(self):
        """初始化Agent和约束条件"""
        self.constraints = {
            "AP1": {
                "sender": {
                    "max_bw": 80,
                    "freqs": [5.0, 5.8],
                    "max_power": 28
                },
                "receiver": {
                    "min_bw": 40,
                    "channels": {
                        5.0: list(range(36, 165, 4)),
                        5.8: [149,153,157,161]
                    }
                }
            },
            "AP2": {
                "sender": {
                    "max_bw": 160,
                    "freqs": [2.4,5.0,5.8],
                    "max_power": 24
                },
                "receiver": {
                    "min_bw": 20,
                    "channels": {
                        2.4: [1,6,11],
                        5.0: [36,40,44,48]
                    }
                }
            }
        }

    def _assign_roles(self):
        """随机分配收发角色"""
        self.sender, self.receiver = random.sample(["AP1", "AP2"], 2)
        print(f"\n=== 角色分配 ===\n发送方: {self.sender}\n接收方: {self.receiver}")

    def _build_system_message(self, agent: str, role: str) -> str:
        """构建角色系统提示"""
        constraints = self.constraints[agent][role]
        return f"""作为{agent}的{role.upper()}，必须遵守：
        
1. 硬件约束：
{json.dumps(constraints, indent=2, ensure_ascii=False)}

2. 通信规则：
- 使用严格JSON格式
- 包含：bandwidth(MHz)/frequency(GHz)/channel/power(dBm)/status
- 协商轮数不限，必须得到合适方案"""

    def _validate_proposal(self, proposal: dict) -> tuple:
        """验证提案可行性"""
        rc = self.constraints[self.receiver]["receiver"]
        
        # 带宽检查
        if proposal.get("bandwidth", 0) < rc["min_bw"]:
            return False, f"带宽不足（最低要求：{rc['min_bw']}MHz）"
        
        # 信道检查
        freq = round(proposal.get("frequency", 0), 1)
        allowed = rc["channels"].get(freq, [])
        if proposal.get("channel") not in allowed:
            return False, f"非法信道（允许值：{allowed}）"
        
        return True, "验证通过"

    def run_negotiation(self):
        """执行协商流程"""
        self._assign_roles()
        
        # 创建动态Agent
        sender = ConversableAgent(
            name=f"{self.sender}_Sender",
            system_message=self._build_system_message(self.sender, "sender"),
            llm_config={"config_list": self.config}
        )
        receiver = ConversableAgent(
            name=f"{self.receiver}_Receiver",
            system_message=self._build_system_message(self.receiver, "receiver"),
            llm_config={"config_list": self.config}
        )

        # 执行协商会话
        chat_result = sender.initiate_chat(
            receiver,
            message={"content": "请提出初始通信方案"},
            max_turns=4
        )
        
        # 获取最终消息（兼容新版API）
        final_msg = chat_result.chat_history[-1]["content"]
        protocol = self._parse_protocol(final_msg)
        valid, reason = self._validate_proposal(protocol)
        
        print(f"\n=== 协商结果 ===\n{'✅ 成功' if valid else '❌ 失败'}：{reason}")
        return protocol

    def _parse_protocol(self, content: str) -> dict:
        """解析协议内容"""
        try:
            return json.loads(re.search(r'\{.*\}', content, re.DOTALL).group())
        except:
            return {"status": "解析失败"}

if __name__ == "__main__":
    for session in range(3):
        print(f"\n{'#'*40}\n第{session+1}次协商\n{'#'*40}")
        system = NegotiationSystem()
        protocol = system.run_negotiation()
        print("\n最终协议：")
        print(json.dumps(protocol, indent=2, ensure_ascii=False))