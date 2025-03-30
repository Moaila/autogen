"""
TDMA动态多时隙协调系统
@作者：李文皓
ap流量动态变化
三AP版本
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
import matplotlib
matplotlib.use('TkAgg')  
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False 
from collections import defaultdict
import matplotlib.pyplot as plt
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
NUM_CHANNELS = 8
NUM_APS = 3
MAX_ATTEMPTS = 200
SAVE_FILE = "success_records_3ap.json"
DEBUG_MODE = False

class EnhancedChannelPool:
    """三AP时隙资源池"""
    def __init__(self, num_channels):
        self.heatmap = defaultdict(int)
        self.available = list(range(num_channels))
        self.usage_queue = []
        self.conflict_history = defaultdict(int)
        
    def update_stats(self, *ap_slots):
        """更新统计信息"""
        all_slots = [ch for ap in ap_slots for ch in ap]
        conflict_count = 0
        
        # 检测多AP冲突
        slot_users = defaultdict(list)
        for idx, slots in enumerate(ap_slots):
            for ch in slots:
                slot_users[ch].append(f"AP{idx+1}")
        
        for ch, users in slot_users.items():
            if len(users) > 1:
                self.conflict_history[ch] += 1
                conflict_count += 1
        
        # 更新热度图
        for ch in self.available:
            self.heatmap[ch] += all_slots.count(ch)
            heapq.heappush(self.usage_queue, (self.heatmap[ch], ch))
            
    def get_feedback(self, *ap_slots):
        """生成三AP反馈信息"""
        all_slots = [ch for ap in ap_slots for ch in ap]
        slot_users = defaultdict(list)
        
        for idx, slots in enumerate(ap_slots):
            for ch in slots:
                slot_users[ch].append(f"AP{idx+1}")
        
        conflict_slots = [ch for ch, users in slot_users.items() if len(users) > 1]
        idle_slots = [ch for ch in self.available if ch not in all_slots]
        
        return {
            "conflict": {
                "count": len(conflict_slots),
                "slots": conflict_slots,
                "details": {ch: users for ch, users in slot_users.items() if len(users) > 1}
            },
            "utilization": {
                "used": len(set(all_slots)),
                "idle": idle_slots,
                "rate": len(set(all_slots)) / NUM_CHANNELS
            },
            "heat_ranking": sorted(self.heatmap.items(), key=lambda x: x[1])
        }

class RealTimeVisualizer:
    """三AP可视化界面"""
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.color_map = {
            "AP1": "#1f77b4",
            "AP2": "#2ca02c", 
            "AP3": "#9467bd",
            "conflict": "#d62728"
        }
        self._init_visualization()

    def _init_visualization(self):
        """初始化可视化面板"""
        plt.ion()
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # 时隙分配图
        self.ax1.set_title('三AP时隙分配', fontsize=14)
        self.ax1.set_xlim(-0.5, NUM_CHANNELS-0.5)
        self.ax1.set_ylim(-0.5, 2.5)
        self.ax1.set_xticks(range(NUM_CHANNELS))
        self.ax1.set_yticks([0, 1, 2])
        self.ax1.set_yticklabels(["AP1", "AP2", "AP3"])
        self.ax1.grid(True, axis='x')
        
        # 使用频次图
        self.ax2.set_title('时隙使用频次', fontsize=14)
        self.ax2.set_xlabel('时隙索引')
        self.ax2.set_ylabel('使用次数')
        self.ax2.set_xticks(range(NUM_CHANNELS))
        self.ax2.grid(True)

    def _draw_legend(self):
        """绘制动态图例"""
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', label='AP1',
                      markerfacecolor=self.color_map["AP1"], markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='AP2',
                      markerfacecolor=self.color_map["AP2"], markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='AP3',
                      markerfacecolor=self.color_map["AP3"], markersize=10),
            plt.Line2D([0], [0], marker='X', color='w', label='冲突',
                      markerfacecolor=self.color_map["conflict"], markersize=10)
        ]
        self.ax1.legend(handles=legend_elements, loc='upper right')

    def update(self, feedback_history):
        """更新可视化"""
        # 清空画布
        self.ax1.cla()
        self.ax2.cla()
        
        # 绘制时隙分配
        latest = self.coordinator.feedback_history[-1]
        for ap_idx, ap_name in enumerate(["AP1", "AP2", "AP3"]):
            slots = self.coordinator.last_selections[ap_name]
            for ch in slots:
                # 检测冲突
                is_conflict = ch in latest["conflict"]["slots"]
                color = self.color_map["conflict"] if is_conflict else self.color_map[ap_name]
                marker = 'X' if is_conflict else 'o'
                
                self.ax1.scatter(
                    ch, ap_idx, 
                    c=color,
                    s=100 if is_conflict else 80,
                    marker=marker,
                    edgecolors='black'
                )
        
        # 绘制使用频次
        heatmap = defaultdict(int)
        for ap in ["AP1", "AP2", "AP3"]:
            for ch in self.coordinator.last_selections[ap]:
                heatmap[ch] += 1
                
        bars = self.ax2.bar(
            range(NUM_CHANNELS),
            [heatmap[ch] for ch in range(NUM_CHANNELS)],
            color=[self.color_map["conflict"] if ch in latest["conflict"]["slots"] 
                  else '#7f7f7f' for ch in range(NUM_CHANNELS)]
        )
        
        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                self.ax2.text(
                    bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom'
                )
        
        # 更新标题和标签
        self.ax1.set_title(f'时隙分配（轮次 {len(feedback_history)}）')
        self.ax2.set_title(f'总利用率 {latest["utilization"]["rate"]:.0%}')
        self._draw_legend()
        
        plt.draw()
        plt.pause(0.8)

class FeedbackCoordinator:
    def __init__(self):
        self.channel_pool = EnhancedChannelPool(NUM_CHANNELS)
        self.traffic_demand = self._generate_demand()
        self.success_records = []
        self.current_rounds = 0
        self._init_agents()
        self.visualizer = RealTimeVisualizer(self)
        self.feedback_history = []
        self.last_selections = {"AP1": [], "AP2": [], "AP3": []}

    def _init_agents(self):
        """初始化三智能体"""
        config_list = config_list_from_json("OAI_CONFIG_LIST.json")
        
        self.agents = {
            "AP1": ConversableAgent(
                name="AP1-Controller",
                system_message=self._build_system_prompt("AP1"),
                llm_config={
                    "config_list": [config_list[0]],
                    "temperature": 1.5
                }
            ),
            "AP2": ConversableAgent(
                name="AP2-Optimizer",
                system_message=self._build_system_prompt("AP2"),
                llm_config={
                    "config_list": [config_list[1]],
                    "temperature": 1.2
                }
            ),
            "AP3": ConversableAgent(
                name="AP3-Adaptive",
                system_message=self._build_system_prompt("AP3"),
                llm_config={
                    "config_list": [config_list[2]],
                    "temperature": 0.8
                }
            )
        }

    def _build_system_prompt(self, agent):
        """三AP系统提示"""
        return f"""作为无线网络{agent}的智能控制器，请严格遵循以下规则：

        1. 当前需要分配 {NUM_CHANNELS} 个时隙（0-{NUM_CHANNELS-1}）
        2. 需要与另外两个AP协调时隙
        3. 必须使用JSON格式响应，示例：{{"channels": [1,3,5], "reason": "..."}}

        约束条件：
        - 每个时隙最多只能被一个AP使用
        - 当前需求：需要选择 {self.traffic_demand[agent]} 个时隙
        - 优先使用低热度时隙
        - 当检测到冲突时，必须重新选择替代时隙

        策略建议：
        - 初始阶段优先选择边缘时隙（如0、7）
        - 中段时隙（3-4）作为备选
        - 根据历史反馈动态调整策略"""

    def _generate_demand(self):
        """生成三AP有效需求"""
        while True:
            base = [random.randint(1, 4) for _ in range(NUM_APS)]
            total = sum(base)
            
            if total <= NUM_CHANNELS:
                remainder = NUM_CHANNELS - total
                # 按权重分配余量
                weights = [b/sum(base) for b in base]
                additions = [int(round(remainder * w)) for w in weights]
                
                # 处理四舍五入误差
                while sum(additions) < remainder:
                    idx = random.randint(0, NUM_APS-1)
                    additions[idx] += 1
                
                final = {
                    f"AP{i+1}": base[i] + additions[i]
                    for i in range(NUM_APS)
                }
                
                if sum(final.values()) == NUM_CHANNELS:
                    return final
            
            else:
                # 按比例缩减
                scale_factor = NUM_CHANNELS / total
                scaled = {
                    f"AP{i+1}": max(1, int(round(base[i] * scale_factor)))
                    for i in range(NUM_APS)
                }
                
                # 二次调整
                current_total = sum(scaled.values())
                if current_total != NUM_CHANNELS:
                    diff = NUM_CHANNELS - current_total
                    for _ in range(abs(diff)):
                        ap = random.choice(list(scaled.keys()))
                        scaled[ap] += 1 if diff > 0 else -1
                
                return scaled

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

    def _fallback_strategy(self, agent):
        """备选策略"""
        expected = self.traffic_demand[agent]
        return sorted(random.sample(range(NUM_CHANNELS), expected))

    def _save_records(self):
        """保存成功记录"""
        with open(SAVE_FILE, 'w') as f:
            json.dump(self.success_records, f, indent=2)
            print(f"\n成功保存{len(self.success_records)}条记录到{SAVE_FILE}")

    def _check_success(self, ap1, ap2, ap3):
        """成功检测"""
        all_slots = set(ap1 + ap2 + ap3)
        conflicts = len(ap1) + len(ap2) + len(ap3) - len(all_slots)
        return len(all_slots) == NUM_CHANNELS and conflicts == 0
    
    def _negotiation_round(self):
        """三阶段协商流程"""
        # AP1初始选择
        ap1_init = self._get_agent_decision("AP1")
        
        # AP2基于AP1选择
        feedback1 = self.channel_pool.get_feedback(ap1_init, [], [])
        ap2_response = self.agents["AP2"].generate_reply(messages=[{
            "role": "user",
            "content": json.dumps({
                "existing_slots": ap1_init,
                "feedback": feedback1
            }, indent=2)
        }])
        ap2_init = self._parse_response(ap2_response, "AP2")
        
        # AP3综合调整
        feedback2 = self.channel_pool.get_feedback(ap1_init, ap2_init, [])
        ap3_response = self.agents["AP3"].generate_reply(messages=[{
            "role": "user",
            "content": json.dumps({
                "ap1_slots": ap1_init,
                "ap2_slots": ap2_init,
                "feedback": feedback2
            }, indent=2)
        }])
        ap3_init = self._parse_response(ap3_response, "AP3")
        
        # 冲突解决
        ap1_final = self._validate_channels(ap1_init, "AP1")
        ap2_final = self._resolve_conflicts(ap1_final, ap2_init)
        ap3_final = self._resolve_conflicts(ap1_final + ap2_final, ap3_init)
        
        # 更新状态
        self.last_selections = {
            "AP1": ap1_final,
            "AP2": ap2_final,
            "AP3": ap3_final
        }
        self.channel_pool.update_stats(ap1_final, ap2_final, ap3_final)
        
        return ap1_final, ap2_final, ap3_final

    def _resolve_conflicts(self, existing, new):
        """多AP冲突解决"""
        conflict = set(existing) & set(new)
        if not conflict:
            return new
        
        resolved = []
        for ch in new:
            if ch not in conflict:
                resolved.append(ch)
            else:
                alternatives = [c for c in range(NUM_CHANNELS) 
                              if c not in existing and c not in resolved]
                if alternatives:
                    resolved.append(random.choice(alternatives))
        
        # 补充缺失
        while len(resolved) < len(new):
            available = [c for c in range(NUM_CHANNELS)
                        if c not in existing and c not in resolved]
            if not available:
                break
            resolved.append(random.choice(available))
        
        return sorted(resolved[:len(new)])


    def run(self):
        """主运行循环"""
        print(f"三AP协调系统启动 | 需求分配: {self.traffic_demand}")
        
        for attempt in range(1, MAX_ATTEMPTS+1):
            ap1, ap2, ap3 = self._negotiation_round()
            feedback = self.channel_pool.get_feedback(ap1, ap2, ap3)
            
            print(f"\n轮次 {attempt} 结果:")
            print(f"AP1: {ap1} | AP2: {ap2} | AP3: {ap3}")
            print(f"冲突时隙: {feedback['conflict']['slots'] or '无'}")
            print(f"利用率: {feedback['utilization']['rate']:.0%}")
            
            self.feedback_history.append(feedback)
            self.visualizer.update(self.feedback_history)
            
            # 成功检测
            if (len(set(ap1 + ap2 + ap3)) == NUM_CHANNELS and 
                not feedback['conflict']['slots']):
                print("\n达成完美分配！")
                self._save_records()
                self.traffic_demand = self._generate_demand()
                print(f"新需求分配: {self.traffic_demand}")
                
            time.sleep(1)

if __name__ == "__main__":
    coordinator = FeedbackCoordinator()
    coordinator.run()