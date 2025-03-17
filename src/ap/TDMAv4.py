"""
TDMA动态多时隙协调系统
@作者：李文皓
"""
import json
import random
import time
import re
import logging
logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')

# 禁用非关键日志
for log_name in ['autogen', 'matplotlib']:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)

import heapq
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False 
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('TkAgg')  
matplotlib.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei']
matplotlib.rcParams['axes.unicode_minus'] = False
from autogen import ConversableAgent, config_list_from_json

from matplotlib.font_manager import findSystemFonts, FontManager
# 测试系统可以正常显示的文字
# font_manager = FontManager()
# print("Available fonts:")
# print([f.name for f in font_manager.ttflist])

# ---------- 系统配置 ----------
NUM_CHANNELS = 8
MAX_ATTEMPTS = 200
TRAFFIC_UPDATE_INTERVAL = 5
SAVE_FILE = "success_records.json"
DEBUG_MODE = False

class EnhancedChannelPool:
    """时隙资源池"""
    def __init__(self, num_channels):
        self.heatmap = defaultdict(int)
        self.available = list(range(num_channels))
        self.usage_queue = []
        self.conflict_history = defaultdict(int)
        
    def update_stats(self, ap1, ap2):
        """更新统计信息"""
        conflict_slots = set(ap1) & set(ap2)
        for ch in conflict_slots:
            self.conflict_history[ch] += 1
        
        used_slots = set(ap1 + ap2)
        for ch in self.available:
            self.heatmap[ch] += 1 if ch in used_slots else 0
            heapq.heappush(self.usage_queue, (self.heatmap[ch], ch))
            
    def get_feedback(self, ap1, ap2):
        """生成反馈信息"""
        conflict_slots = list(set(ap1) & set(ap2))
        used_slots = set(ap1 + ap2)
        idle_slots = [ch for ch in self.available if ch not in used_slots]
        
        feedback = {
            "conflict": {
                "occurred": len(conflict_slots) > 0,
                "slots": conflict_slots,
                "count": len(conflict_slots)
            },
            "utilization": {
                "used": len(used_slots),
                "idle": idle_slots,
                "rate": len(used_slots) / NUM_CHANNELS
            },
            "heat_ranking": sorted(self.heatmap.items(), key=lambda x: x[1])
        }
        return feedback

class RealTimeVisualizer:
    """实时可视化界面"""
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.history = {
            "AP1": [],
            "AP2": [],
            "throughput": [],
            "conflicts": []
        }
        self.channel_pool = EnhancedChannelPool(NUM_CHANNELS)
        self._init_visualization()

    def _init_visualization(self):
        """初始化可视化面板"""
        plt.ion()
        self.fig, axs = plt.subplots(2, 1, figsize=(12, 10))  # 两行一列的布局

        # 时隙分配与冲突
        self.ax1 = axs[0]
        self.ax1.set_title('时隙分配与冲突', fontsize=14)
        self.ax1.set_xlabel('时隙索引', fontsize=12)
        self.ax1.set_ylabel('使用情况', fontsize=12)
        self.ax1.grid(True)

        # 时隙使用频次
        self.ax2 = axs[1]
        self.ax2.set_title('时隙使用频次', fontsize=14)
        self.ax2.set_xlabel('时隙索引', fontsize=12)
        self.ax2.set_ylabel('使用频次', fontsize=12)
        self.ax2.grid(True)

        plt.tight_layout()

    def _update_display(self, attempt):
        """实时更新图形化界面"""
        # 清除旧图
        self.ax1.cla()
        self.ax2.cla()

        # 更新时隙分配与冲突
        self.ax1.set_title('时隙分配与冲突', fontsize=14)
        self.ax1.set_xlabel('时隙索引', fontsize=12)
        self.ax1.set_ylabel('使用情况', fontsize=12)
        self.ax1.grid(True)

        # 获取最新的反馈信息
        if self.coordinator.feedback_history:
            latest_feedback = self.coordinator.feedback_history[-1]
            conflict_slots = latest_feedback["conflict"]["slots"]
            ap1_slots = self.coordinator.last_selections["AP1"]
            ap2_slots = self.coordinator.last_selections["AP2"]

            # 绘制时隙分配
            all_slots = set(ap1_slots + ap2_slots)
            for ch in range(NUM_CHANNELS):
                if ch in all_slots:
                    if ch in conflict_slots:
                        self.ax1.scatter(ch, 0, c='red', label='冲突' if ch == conflict_slots[0] else "", s=100, zorder=10)  # 冲突时隙
                    elif ch in ap1_slots:
                        self.ax1.scatter(ch, 0, c='blue', label='AP1' if ch == ap1_slots[0] else "", s=50)  # AP1 使用的时隙
                    elif ch in ap2_slots:
                        self.ax1.scatter(ch, 0, c='green', label='AP2' if ch == ap2_slots[0] else "", s=50)  # AP2 使用的时隙

        # 添加图例（只显示一次）
        if attempt == 1:
            self.ax1.scatter([], [], c='red', label='冲突', s=100)
            self.ax1.scatter([], [], c='blue', label='AP1', s=50)
            self.ax1.scatter([], [], c='green', label='AP2', s=50)
            self.ax1.legend(loc='upper right')

        # 更新时隙使用频次
        self.ax2.set_title('时隙使用频次', fontsize=14)
        self.ax2.set_xlabel('时隙索引', fontsize=12)
        self.ax2.set_ylabel('使用频次', fontsize=12)
        self.ax2.grid(True)

        # 统计时隙使用频次
        heatmap = defaultdict(int)
        for slots in [self.coordinator.last_selections["AP1"], self.coordinator.last_selections["AP2"]]:
            for ch in slots:
                heatmap[ch] += 1

        # 绘制时隙使用频次
        x = list(range(NUM_CHANNELS))
        y = [heatmap[ch] for ch in x]
        self.ax2.bar(x, y, color='skyblue', alpha=0.8)
        for i, cnt in enumerate(y):
            self.ax2.text(i, cnt + 0.1, str(cnt), ha='center', va='bottom', fontsize=8)

        # 刷新图形
        plt.draw()
        plt.pause(0.5)

    def update(self, feedback_history):
        """动态更新视图"""
        self.coordinator.feedback_history = feedback_history
        self._update_display(len(feedback_history))

class FeedbackCoordinator:
    def __init__(self):
        self.channel_pool = EnhancedChannelPool(NUM_CHANNELS)
        self.traffic_demand = {"AP1": 4, "AP2": 4}  # 初始比例
        self.success_records = []
        self.current_rounds = 0
        self._init_agents()
        self._load_previous_records()
        self.visualizer = RealTimeVisualizer(self)
        self.feedback_history = []
        self.last_selections = {"AP1": [], "AP2": []}

    def _init_agents(self):
        """初始化双智能体"""
        config_list = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={"model": ["deepseek-chat", "deepseek-reasoner"]}
        )
        
        self.agents = {
            "AP1": ConversableAgent(
                name="AP1-Controller",
                system_message=self._build_system_prompt("AP1"),
                llm_config={"config_list": config_list}
            ),
            "AP2": ConversableAgent(
                name="AP2-Optimizer",
                system_message=self._build_system_prompt("AP2"),
                llm_config={"config_list": config_list}
            )
        }

    def _build_system_prompt(self, agent):
        """动态生成系统提示"""
        return f"""作为无线网络{agent}的智能控制器，请严格遵循以下规则：

        1. 当前需要分配 {self.traffic_demand[agent]} 个时隙
        2. 可用时隙范围：0-{NUM_CHANNELS-1}
        3. 要尽可能实现100%时隙利用率
        4. 必须使用JSON格式响应，示例：{{"channels": [1,3,5], "reason": "..."}}

        重要约束：
        - 避免选择最近冲突的时隙
        - 优先使用低热度时隙
        - 确保总利用率最大化
        - 当流量需求变化时，动态调整分配策略以确保时隙充分利用
        - 在可能的情况下，优先填补未使用的时隙，避免空闲时隙过多

        额外指导：
        - 如果当前流量需求允许，尝试均匀分配时隙以减少冲突
        - 动态评估时隙的使用情况，优先选择那些能提高整体利用率的时隙
        - 在高负载情况下，尽量减少冲突并优化时隙的重用"""

    def _generate_demand(self):
        """生成有效流量需求"""
        while True:
            new_demand = {
                "AP1": random.randint(1, NUM_CHANNELS-1),
                "AP2": random.randint(1, NUM_CHANNELS-1)
            }
            if sum(new_demand.values()) <= NUM_CHANNELS:
                return new_demand

        # 把比例写死的死板操作
        # possible_ratios = [
        # {"AP1": 1, "AP2": 7},
        # {"AP1": 2, "AP2": 6},
        # {"AP1": 3, "AP2": 5},
        # {"AP1": 4, "AP2": 4},
        # {"AP1": 5, "AP2": 3},
        # {"AP1": 6, "AP2": 2},
        # {"AP1": 7, "AP2": 1}
        # ]
        # new_demand = random.choice(possible_ratios)
    
        # 返回新的流量需求
        # return new_demand

    def _negotiation_round(self):
        """完整协商流程"""
        # AP1初始选择
        ap1_init = self._get_agent_decision("AP1")
        feedback = self.channel_pool.get_feedback(ap1_init, [])
        
        # AP2优化选择（带反馈）
        ap2_response = self.agents["AP2"].generate_reply(messages=[{
            "role": "user",
            "content": json.dumps({
                "ap1_proposal": ap1_init,
                "feedback": feedback
            }, indent=2)
        }])
        
        # 解析最终方案
        ap1_final = self._validate_channels(ap1_init, "AP1")
        ap2_final = self._validate_channels(
            self._parse_response(ap2_response, "AP2"), 
            "AP2"
        )
        
        # 冲突解决
        ap2_final = self._resolve_conflicts(ap1_final, ap2_final)

        self.last_selections["AP1"] = ap1_final
        self.last_selections["AP2"] = ap2_final

        # 测试用
        # print(f"AP1 最终选择: {ap1_final}")
        # print(f"AP2 最终选择: {ap2_final}")

        return ap1_final, ap2_final

    def _get_agent_decision(self, agent):
        """获取智能体决策（带错误处理）"""
        try:
            response = self.agents[agent].generate_reply(messages=[{
                "role": "user",
                "content": "请根据当前网络状态选择最佳时隙"
            }])
            return self._parse_response(response, agent)
        except Exception as e:
            print(f"{agent} 决策异常，启用备选策略: {str(e)}")
            return self._fallback_strategy(agent)

    def _parse_response(self, response, agent):
        """增强型响应解析"""
        try:
            content = response.content if hasattr(response, 'content') else str(response)
            json_str = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_str:
                raise ValueError("无效的响应格式")
                
            data = json.loads(json_str.group())
            channels = sorted(list(set(int(ch) for ch in data.get("channels", []))))
            return self._validate_channels(channels, agent)
        except Exception as e:
            print(f"{agent} 解析错误: {str(e)}")
            return self._fallback_strategy(agent)

    def _validate_channels(self, channels, agent):
        """时隙验证逻辑"""
        expected = self.traffic_demand[agent]
        valid = [ch for ch in channels if 0 <= ch < NUM_CHANNELS]
        
        if len(valid) < expected:
            need = expected - len(valid)
            valid += random.sample(
                [ch for ch in range(NUM_CHANNELS) if ch not in valid],
                need
            )
        return sorted(valid[:expected])

    def _resolve_conflicts(self, ap1, ap2):
        """冲突解决引擎"""
        conflict = set(ap1) & set(ap2)
        if not conflict:
            return ap2
        
        # 冲突时隙替换策略
        new_ap2 = []
        for ch in ap2:
            if ch not in conflict:
                new_ap2.append(ch)
            else:
                alternatives = [c for c in range(NUM_CHANNELS) 
                               if c not in ap1 and c not in new_ap2]
                if alternatives:
                    new_ap2.append(random.choice(alternatives))
        
        # 补充缺失的时隙
        while len(new_ap2) < len(ap2):
            available = [c for c in range(NUM_CHANNELS) 
                        if c not in ap1 and c not in new_ap2]
            if not available:
                break
            new_ap2.append(random.choice(available))
        
        return sorted(new_ap2[:len(ap2)])

    def _save_records(self):
        """保存成功记录"""
        with open(SAVE_FILE, 'w') as f:
            json.dump(self.success_records, f, indent=2)
            print(f"\n成功保存{len(self.success_records)}条记录到{SAVE_FILE}")

    def _load_previous_records(self):
        """加载历史记录"""
        try:
            with open(SAVE_FILE, 'r') as f:
                self.success_records = json.load(f)
                print(f"已加载{len(self.success_records)}条历史记录")
        except FileNotFoundError:
            pass

    def _check_success(self, ap1, ap2):
        """成功方案检测"""
        conflict = len(set(ap1) & set(ap2))
        used = len(set(ap1 + ap2))
        return conflict == 0 and used == NUM_CHANNELS

    def run(self):
        """主运行循环"""
        print(f"TDMA协调系统启动 | 初始比例 AP1:{self.traffic_demand['AP1']} AP2:{self.traffic_demand['AP2']}")
        
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.current_rounds += 1
            
            # 执行协商
            ap1, ap2 = self._negotiation_round()
            self.channel_pool.update_stats(ap1, ap2)
            
            # 生成反馈报告
            feedback = self.channel_pool.get_feedback(ap1, ap2)
            print(f"\n轮次 {attempt} 反馈报告:")
            print(f"AP1时隙: {ap1}")
            print(f"AP2时隙: {ap2}")
            print(f"冲突时隙: {feedback['conflict']['slots'] or '无'}")
            print(f"空闲时隙: {feedback['utilization']['idle'] or '无'}")
            print(f"利用率: {feedback['utilization']['rate']:.0%}")

            # 增加可视化页面
            self.feedback_history.append(feedback)
            # print(f"反馈历史记录: {self.feedback_history}") # 测试用，正式使用时注释
            if len(self.feedback_history) % 1 == 0:  # 每1轮更新一次
                self.visualizer.update(self.feedback_history)
            
            # 成功检测和比例更新
            if self._check_success(ap1, ap2):
                print("\n达成完美分配！")
                self.success_records.append({
                    "ratio": dict(self.traffic_demand),
                    "ap1_slots": ap1,
                    "ap2_slots": ap2,
                    "rounds": self.current_rounds,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                self._save_records()
                
                # 更新流量比例
                self.traffic_demand = self._generate_demand()
                self.current_rounds = 0
                print(f"\n更新流量比例 AP1:{self.traffic_demand['AP1']} AP2:{self.traffic_demand['AP2']}")
            
            time.sleep(0.8)  # 控制协商节奏

if __name__ == "__main__":
    coordinator = FeedbackCoordinator()
    coordinator.run()