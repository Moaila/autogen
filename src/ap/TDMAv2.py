"""
TDMA动态多信道协调系统（生产级优化版）
功能特性：
1. 智能信道分配（AP1双倍配额）
2. 冲突避免机制
3. 信道利用率优化
4. 实时可视化监控
"""
import json
import random
import time
import re
import logging
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
NUM_CHANNELS = 8          # 总信道数
AP1_WEIGHT = 2            # AP1权重（发送量是AP2的2倍）
MIN_CHANNELS = 1          # 每个AP最小信道数
CONVERGENCE_THRESHOLD = 10 # 收敛检测阈值
TRAFFIC_UPDATE_INTERVAL = 3  # 流量更新间隔

# ---------- 模型配置 ----------
MODEL_CONFIG = {
    "deepseek-chat": {
        "temperature": 0.7,
        "response_template": {"channels": [], "reason": ""}
    },
    "deepseek-reasoner": {
        "temperature": 0.3,
        "response_template": {"channels": [], "reason": ""}
    }
}

class DynamicChannelOptimizer:
    def __init__(self):
        self.traffic_demand = {"AP1": 4, "AP2": 2}  # 初始需求（AP1双倍）
        self.utilization_history = []
        self._init_agents()
        self._init_visualization()
        
    def _init_agents(self):
        """初始化智能体"""
        config_list = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={"model": ["deepseek-chat", "deepseek-reasoner"]}
        )
        
        self.agents = {
            "AP1": ConversableAgent(
                name="AP1-Primary",
                system_message=self._build_prompt("AP1"),
                llm_config={"config_list": config_list},
                human_input_mode="NEVER"
            ),
            "AP2": ConversableAgent(
                name="AP2-Secondary",
                system_message=self._build_prompt("AP2"),
                llm_config={"config_list": config_list},
                human_input_mode="NEVER"
            )
        }

    def _build_prompt(self, ap_type):
        """构建强化提示词"""
        ratio = f"{AP1_WEIGHT}:1" if ap_type == "AP1" else f"1:{AP1_WEIGHT}"
        return f"""您负责{ap_type}的信道分配，需满足：
1. 总信道数：{NUM_CHANNELS}
2. 分配比例：{ratio}（AP1优先）
3. 当前需求：{self.traffic_demand[ap_type]}个信道
4. 避免与对方冲突
请返回JSON格式：{{"channels": [信道列表], "reason": "分配依据"}}"""

    def _parse_response(self, response, ap_type):
        """稳健响应解析"""
        try:
            content = str(getattr(response, 'content', response))
            json_str = re.search(r'\{.*\}', content).group()
            data = json.loads(json_str.replace("'", '"'))
            
            # 信道验证
            channels = [int(c) % NUM_CHANNELS for c in data.get("channels", [])]
            channels = list(set(channels))[:self.traffic_demand[ap_type]]  # 限制最大需求
            
            # 保证最小信道数
            if len(channels) < MIN_CHANNELS:
                channels += random.sample(range(NUM_CHANNELS), MIN_CHANNELS - len(channels))
            
            return sorted(channels)
        except Exception as e:
            logging.warning(f"[{ap_type}] 解析失败，启用回退策略: {str(e)}")
            return random.sample(range(NUM_CHANNELS), self.traffic_demand[ap_type])

    def _optimize_allocation(self, ap1_chs, ap2_chs):
        """智能优化分配"""
        # 冲突检测
        conflict_chs = set(ap1_chs) & set(ap2_chs)
        
        # 优先满足AP1
        final_ap2 = list(set(ap2_chs) - conflict_chs)
        
        # 补充AP2信道（从剩余信道中）
        remaining_chs = list(set(range(NUM_CHANNELS)) - set(ap1_chs))
        needed = self.traffic_demand["AP2"] - len(final_ap2)
        if needed > 0 and remaining_chs:
            final_ap2 += random.sample(remaining_chs, min(needed, len(remaining_chs)))
        
        return ap1_chs, final_ap2[:self.traffic_demand["AP2"]]

    def _update_traffic_demand(self, attempt):
        """动态需求调整"""
        if attempt % TRAFFIC_UPDATE_INTERVAL == 0:
            # 保持AP1需求是AP2的2倍
            base = random.randint(2, 4)
            self.traffic_demand = {
                "AP1": min(base*2, NUM_CHANNELS-1),
                "AP2": min(base, NUM_CHANNELS-1)
            }
            print(f"\n需求更新 | AP1: {self.traffic_demand['AP1']} | AP2: {self.traffic_demand['AP2']}")

    def _init_visualization(self):
        """初始化可视化"""
        plt.ion()
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # 信道分配图
        self.ax1.set_title('Real-time Channel Allocation')
        self.ax1.set_ylim(-0.5, NUM_CHANNELS-0.5)
        self.ax1.set_yticks(range(NUM_CHANNELS))
        self.ax1.grid(True, alpha=0.3)
        
        # 利用率统计图
        self.ax2.set_title('Channel Utilization Rate')
        self.ax2.set_ylim(0, 100)
        self.util_line, = self.ax2.plot([], [], 'g-')
        
        # 统一字体配置
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    def _update_display(self, attempt, ap1_chs, ap2_chs):
        """更新可视化"""
        # 清空当前图表
        self.ax1.cla()
        self.ax2.cla()
        
        # 绘制信道分配
        self.ax1.scatter([attempt]*len(ap1_chs), ap1_chs, c='red', label='AP1')
        self.ax1.scatter([attempt]*len(ap2_chs), ap2_chs, c='blue', marker='x', label='AP2')
        self.ax1.legend()
        
        # 计算利用率
        used = len(set(ap1_chs + ap2_chs))
        util_rate = (used / NUM_CHANNELS) * 100
        self.utilization_history.append(util_rate)
        
        # 绘制利用率曲线
        self.ax2.plot(range(len(self.utilization_history)), self.utilization_history, 'g-')
        self.ax2.set_ylim(0, 100)
        self.ax2.set_ylabel('Utilization (%)')
        
        # 实时标注
        self.ax2.annotate(f'{util_rate:.1f}%', 
                         xy=(attempt, util_rate),
                         xytext=(attempt+0.5, util_rate+5))
        
        plt.pause(0.1)

    def run(self):
        """主运行循环"""
        print("🚀 启动动态信道协调系统（Ctrl+C终止）")
        consecutive_success = 0
        
        try:
            for attempt in range(1, 100):  # 持续运行
                self._update_traffic_demand(attempt)
                
                # AP1选择
                ap1_res = self.agents["AP1"].generate_reply(
                    messages=[{"role": "user", "content": "请分配当前信道"}],
                    sender=self.agents["AP2"]
                )
                ap1_chs = self._parse_response(ap1_res, "AP1")
                
                # AP2选择
                ap2_res = self.agents["AP2"].generate_reply(
                    messages=[{"role": "user", "content": f"AP1已选：{ap1_chs}，请优化分配"}],
                    sender=self.agents["AP1"]
                )
                ap2_chs = self._parse_response(ap2_res, "AP2")
                
                # 优化分配
                final_ap1, final_ap2 = self._optimize_allocation(ap1_chs, ap2_chs)
                conflict = len(set(final_ap1) & set(final_ap2))
                
                # 记录状态
                print(f"\n轮次 {attempt}")
                print(f"AP1 信道: {final_ap1}")
                print(f"AP2 信道: {final_ap2}")
                print(f"冲突信道数: {conflict}")
                print(f"利用率: {len(set(final_ap1+final_ap2))}/{NUM_CHANNELS}")
                
                # 更新显示
                self._update_display(attempt, final_ap1, final_ap2)
                
                # 收敛检测
                if conflict == 0:
                    consecutive_success += 1
                    if consecutive_success >= CONVERGENCE_THRESHOLD:
                        print(f"✅ 连续{CONVERGENCE_THRESHOLD}轮无冲突！")
                        break
                else:
                    consecutive_success = 0
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🔴 用户终止运行")
        finally:
            plt.ioff()
            plt.show()

if __name__ == "__main__":
    coordinator = DynamicChannelOptimizer()
    coordinator.run()