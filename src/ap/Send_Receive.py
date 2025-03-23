"""
双Agent通信协议协商系统
@作者：李文皓
基于Deepseek模型的通信参数协商
"""
import json
import re
import time
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
MAX_ROUNDS = 8
DEBUG_MODE = True

class NegotiationCoordinator:
    def __init__(self):
        self.negotiation_log = []
        self._setup_constraints()  # 先初始化约束
        self._init_agents()       # 再初始化Agent

    def _setup_constraints(self):
        """设置通信约束条件"""
        self.constraints = {
            "AP1": {
                "max_bandwidth": 80,  # MHz
                "supported_frequencies": [2.4, 5.0, 5.8],  # GHz
                "max_power": 28  # dBm
            },
            "AP2": {
                "min_bandwidth": 20,
                "acceptable_frequencies": {
                    2.4: [1, 6, 11],
                    5.0: list(range(36, 165, 4)),
                    5.8: [149, 153, 157, 161]
                },
                "sensitivity": -65  # dBm
            }
        }

    def _init_agents(self):
        """初始化双Agent"""
        config_list = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={"model": ["deepseek-chat", "deepseek-reasoner"]}
        )
        
        # 分离不同模型的配置
        sender_config = [c for c in config_list if c["model"] == "deepseek-chat"]
        receiver_config = [c for c in config_list if c["model"] == "deepseek-reasoner"]

        self.agents = {
            "AP1": ConversableAgent(
                name="AP1-Sender",
                system_message=self._build_system_prompt("AP1"),
                llm_config={
                    "config_list": sender_config,
                    "temperature": 1.5,
                    "timeout": 600
                }
            ),
            "AP2": ConversableAgent(
                name="AP2-Receiver",
                system_message=self._build_system_prompt("AP2"),
                llm_config={
                    "config_list": receiver_config,
                    "temperature": 1.2,
                    "timeout": 600
                }
            )
        }

    def _build_system_prompt(self, agent):
        """构建角色系统提示"""
        role = "发送方" if agent == "AP1" else "接收方"
        return f"""作为{role}（{agent}），请严格遵循：

1. 必须使用JSON格式：
{{
  "status": "提议/接受/拒绝",
  "bandwidth": 数值（MHz）,
  "frequency": 数值（GHz）,
  "channel": 整数,
  "power": 数值（dBm）,
  "reason": "技术理由说明"
}}

2. 你的硬件约束：
{json.dumps(self.constraints[agent], indent=2, ensure_ascii=False)}

3. 协商规则：
- AP1先提案，AP2评估后响应
- 最多{MAX_ROUNDS}轮协商
- 最终方案需满足双方约束

4. 优化目标：
✓ 带宽利用率 > 80%
✓ 优先选择低干扰信道
✓ 功率效率最大化"""

    def _format_proposal(self, agent: str, proposal: dict) -> str:
        """格式化显示提案"""
        border = "═" * 40
        return (
            f"\n{border}\n"
            f"║ {agent} 提案 [{proposal.get('status', '未知')}] \n"
            f"{border}"
            f"\n• 带宽：{proposal.get('bandwidth', 'N/A')}MHz"
            f"\n• 频率：{proposal.get('frequency', 'N/A')}GHz"
            f"\n• 信道：{proposal.get('channel', 'N/A')}"
            f"\n• 功率：{proposal.get('power', 'N/A')}dBm"
            f"\n• 理由：{proposal.get('reason', '')}"
            f"\n{border.replace('═', '─')}"
        )

    def _get_initial_proposal(self, agent: str) -> dict:
        """获取初始提案"""
        try:
            response = self.agents[agent].generate_reply(messages=[{
                "role": "user",
                "content": "请根据约束条件提出初始通信方案"
            }])
            return self._parse_response(response)
        except Exception as e:
            print(f"{agent} 初始化失败: {str(e)}")
            return self._default_proposal(agent)

    def _parse_response(self, response) -> dict:
        """解析响应并验证格式"""
        try:
            content = response.content if hasattr(response, 'content') else str(response)
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                raise ValueError("未找到JSON数据")
                
            proposal = json.loads(match.group())
            return {
                "status": proposal.get("status", "提议"),
                "bandwidth": float(proposal.get("bandwidth", 20)),
                "frequency": round(float(proposal.get("frequency", 5.0)), 1),
                "channel": int(proposal.get("channel", 36)),
                "power": float(proposal.get("power", 20)),
                "reason": proposal.get("reason", "")
            }
        except Exception as e:
            print(f"解析异常: {str(e)}")
            return self._default_proposal()

    def _default_proposal(self, agent=None) -> dict:
        """生成安全默认提案"""
        base = {
            "status": "提议",
            "bandwidth": 40,
            "frequency": 5.0,
            "channel": 36,
            "power": 20,
            "reason": "系统自动生成的默认方案"
        }
        if agent == "AP1":
            base.update({"bandwidth": 60, "power": 25})
        elif agent == "AP2":
            base.update({"bandwidth": 30, "channel": 149})
        return base

    def _validate_proposal(self, proposal: dict, role: str) -> bool:
        """验证提案可行性"""
        constraints = self.constraints["AP1" if role == "sender" else "AP2"]
        
        if role == "sender":
            if proposal["bandwidth"] > constraints["max_bandwidth"]:
                return False
            if proposal["frequency"] not in constraints["supported_frequencies"]:
                return False
            if proposal["power"] > constraints["max_power"]:
                return False
        else:
            if proposal["bandwidth"] < constraints["min_bandwidth"]:
                return False
            freq_band = round(proposal["frequency"], 1)
            if proposal["channel"] not in constraints["acceptable_frequencies"].get(freq_band, []):
                return False
            if (proposal["power"] - proposal["bandwidth"]/10) < constraints["sensitivity"]:
                return False
        return True

    def run_negotiation(self):
        """运行协商主流程"""
        print("\n=== 通信协议协商启动 ===")
        
        # 初始提案
        ap1_proposal = self._get_initial_proposal("AP1")
        print(self._format_proposal("AP1", ap1_proposal))
        
        for round in range(1, MAX_ROUNDS + 1):
            print(f"\n▶ 第 {round} 轮协商")
            
            # AP2响应
            ap2_response = self.agents["AP2"].generate_reply(
                messages=[{"role": "user", "content": json.dumps(ap1_proposal)}]
            )
            ap2_proposal = self._parse_response(ap2_response)
            print(self._format_proposal("AP2", ap2_proposal))
            
            # 检查接受状态
            if ap2_proposal["status"] == "接受":
                if self._validate_proposal(ap1_proposal, "sender"):
                    print("\n✅ 协商成功！")
                    self._show_final_protocol(ap1_proposal)
                    return
            
            # AP1响应反提案
            ap1_response = self.agents["AP1"].generate_reply(
                messages=[{"role": "user", "content": json.dumps(ap2_proposal)}]
            )
            ap1_proposal = self._parse_response(ap1_response)
            print(self._format_proposal("AP1", ap1_proposal))

        print("\n❌ 协商失败，未达成协议")

    def _show_final_protocol(self, protocol: dict):
        """显示最终协议详情"""
        print("\n" + "★" * 40)
        print(" 最终通信协议 ".center(40, "☆"))
        for k, v in protocol.items():
            if k != "reason":
                print(f"{k.upper()}: {v}")
        print(f"协议理由: {protocol.get('reason', '')}")
        print("☆" * 40 + "\n")

if __name__ == "__main__":
    coordinator = NegotiationCoordinator()
    coordinator.run_negotiation()