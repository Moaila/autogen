"""
TDMA动态多时隙协调系统
@作者：李文皓
ap流量动态变化
多ap数量变化（上限5个因为只调用了5个api）且时隙数量自定
"""
"""
动态多AP时隙协调系统
@作者：李文皓
支持任意AP数量和时隙配置
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

# ---------- 系统常量 ----------
MAX_ATTEMPTS = 200
SAVE_FILE = "success_records.json"
DEBUG_MODE = False

class EnhancedChannelPool:
    """动态时隙资源池"""
    def __init__(self, num_channels):
        self.heatmap = defaultdict(int)
        self.available = list(range(num_channels))
        self.usage_queue = []
        self.conflict_history = defaultdict(int)
        
    def update_stats(self, *ap_slots):
        """更新统计信息"""
        all_slots = [ch for ap in ap_slots for ch in ap]
        conflict_count = 0
        
        # 动态冲突检测
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
        """生成动态反馈信息"""
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
                "rate": len(set(all_slots)) / len(self.available)
            },
            "heat_ranking": sorted(self.heatmap.items(), key=lambda x: x[1])
        }

class RealTimeVisualizer:
    """动态可视化系统"""
    def __init__(self, coordinator, num_aps, num_channels):
        self.coordinator = coordinator
        self.num_aps = num_aps
        self.num_channels = num_channels
        self.color_map = self._generate_colors()
        self._init_visualization()

    def _generate_colors(self):
        """生成动态颜色方案"""
        base_colors = ["#1f77b4", "#2ca02c", "#9467bd", "#d62728", "#ff7f0e"]
        return {f"AP{i+1}": base_colors[i % len(base_colors)] for i in range(self.num_aps)}

    def _init_visualization(self):
        """初始化可视化面板"""
        plt.ion()
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # 时隙分配图
        self.ax1.set_title(f'{self.num_aps}AP时隙分配', fontsize=14)
        self.ax1.set_xlim(-0.5, self.num_channels-0.5)
        self.ax1.set_ylim(-0.5, self.num_aps-0.5)
        self.ax1.set_xticks(range(self.num_channels))
        self.ax1.set_yticks(range(self.num_aps))
        self.ax1.set_yticklabels([f"AP{i+1}" for i in range(self.num_aps)])
        self.ax1.grid(True, axis='x')
        
        # 使用频次图
        self.ax2.set_title('时隙使用频次', fontsize=14)
        self.ax2.set_xlabel('时隙索引')
        self.ax2.set_ylabel('使用次数')
        self.ax2.set_xticks(range(self.num_channels))
        self.ax2.grid(True)

    def _draw_legend(self):
        """绘制动态图例"""
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', label=f'AP{i+1}',
                      markerfacecolor=self.color_map[f"AP{i+1}"], markersize=10)
            for i in range(self.num_aps)
        ]
        legend_elements.append(
            plt.Line2D([0], [0], marker='X', color='w', label='冲突',
                      markerfacecolor="#d62728", markersize=10)
        )
        self.ax1.legend(handles=legend_elements, loc='upper right')

    def update(self, feedback_history):
        """更新可视化"""
        self.ax1.cla()
        self.ax2.cla()
        
        # 绘制时隙分配
        latest = self.coordinator.feedback_history[-1]
        for ap_idx in range(self.num_aps):
            ap_name = f"AP{ap_idx+1}"
            slots = self.coordinator.last_selections[ap_name]
            for ch in slots:
                is_conflict = ch in latest["conflict"]["slots"]
                color = "#d62728" if is_conflict else self.color_map[ap_name]
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
        for ap_name in self.coordinator.last_selections:
            for ch in self.coordinator.last_selections[ap_name]:
                heatmap[ch] += 1
                
        bars = self.ax2.bar(
            range(self.num_channels),
            [heatmap[ch] for ch in range(self.num_channels)],
            color=["#d62728" if ch in latest["conflict"]["slots"] 
                  else '#7f7f7f' for ch in range(self.num_channels)]
        )
        
        # 数值标签
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                self.ax2.text(
                    bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom'
                )
        
        # 更新标题
        self.ax1.set_title(f'时隙分配（轮次 {len(feedback_history)}）')
        self.ax2.set_title(f'总利用率 {latest["utilization"]["rate"]:.0%}')
        self._draw_legend()
        
        plt.draw()
        plt.pause(0.8)

class FeedbackCoordinator:
    def __init__(self, num_aps, num_channels, config_list):
        self.num_aps = num_aps
        self.num_channels = num_channels
        self.channel_pool = EnhancedChannelPool(num_channels)
        self.traffic_demand = self._generate_demand()
        self.success_records = []
        self.current_rounds = 0
        self._init_agents(config_list)
        self.visualizer = RealTimeVisualizer(self, num_aps, num_channels)
        self.feedback_history = []
        self.last_selections = {f"AP{i+1}": [] for i in range(num_aps)}

    def _init_agents(self, config_list):
        """动态初始化智能体"""
        self.agents = {}
        for i in range(self.num_aps):
            ap_name = f"AP{i+1}"
            config = config_list[i % len(config_list)]
            self.agents[ap_name] = ConversableAgent(
                name=f"{ap_name}-Controller",
                system_message=self._build_system_prompt(ap_name),
                llm_config={
                    "config_list": [config],
                    "temperature": 1.5 - (0.3 * i)  # 差异化温度
                }
            )

    def _build_system_prompt(self, agent):
        """动态系统提示"""
        return f"""作为无线网络{agent}的智能控制器，请严格遵循以下规则：

        1. 当前需要分配 {self.num_channels} 个时隙（0-{self.num_channels-1}）
        2. 需要与另外{self.num_aps-1}个AP协调时隙
        3. 必须使用JSON格式响应，示例：{{"channels": [1,3,5], "reason": "..."}}

        约束条件：
        - 每个时隙最多只能被一个AP使用
        - 当前需求：需要选择 {self.traffic_demand[agent]} 个时隙
        - 优先使用低热度时隙
        - 当检测到冲突时，必须重新选择替代时隙

        策略建议：
        - 初始阶段优先选择边缘时隙（如0、{self.num_channels-1}）
        - 中段时隙作为备选
        - 根据历史反馈动态调整策略"""

    def _generate_demand(self):
        """动态需求生成算法"""
        while True:
            base = [random.randint(1, 4) for _ in range(self.num_aps)]
            total = sum(base)
            
            if total <= self.num_channels:
                remainder = self.num_channels - total
                weights = [b/total for b in base]
                additions = [int(round(remainder * w)) for w in weights]
                
                # 处理余量误差
                while sum(additions) != remainder:
                    if sum(additions) < remainder:
                        idx = random.randint(0, self.num_aps-1)
                        additions[idx] += 1
                    else:
                        idx = random.randint(0, self.num_aps-1)
                        if additions[idx] > 0:
                            additions[idx] -= 1
                
                final = {
                    f"AP{i+1}": base[i] + additions[i]
                    for i in range(self.num_aps)
                }
                
                if sum(final.values()) == self.num_channels:
                    return final
            else:
                # 按比例缩减
                scaled = [max(1, int(round(b * self.num_channels / total))) for b in base]
                current_total = sum(scaled)
                
                # 二次调整
                diff = self.num_channels - current_total
                step = 1 if diff > 0 else -1
                for _ in range(abs(diff)):
                    idx = random.randint(0, self.num_aps-1)
                    scaled[idx] += step
                
                return {f"AP{i+1}": scaled[i] for i in range(self.num_aps)}

    def _get_agent_decision(self, agent):
        """获取智能体决策"""
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
        """解析响应"""
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
        """验证时隙有效性"""
        expected = self.traffic_demand[agent]
        valid = [ch for ch in channels if 0 <= ch < self.num_channels]
        
        if len(valid) < expected:
            need = expected - len(valid)
            valid += random.sample(
                [ch for ch in range(self.num_channels) if ch not in valid],
                need
            )
        return sorted(valid[:expected])

    def _fallback_strategy(self, agent):
        """备选策略"""
        expected = self.traffic_demand[agent]
        return sorted(random.sample(range(self.num_channels), expected))

    def _save_records(self):
        """保存成功记录"""
        with open(SAVE_FILE, 'w') as f:
            json.dump(self.success_records, f, indent=2)
            print(f"\n成功保存{len(self.success_records)}条记录到{SAVE_FILE}")

    def _check_success(self, *ap_slots):
        """成功检测"""
        all_slots = set()
        for slots in ap_slots:
            all_slots.update(slots)
        return len(all_slots) == self.num_channels and not self.feedback_history[-1]["conflict"]["slots"]

    def _negotiation_round(self):
        """动态协商流程"""
        # 阶段1：顺序决策
        selections = {}
        for i in range(self.num_aps):
            ap_name = f"AP{i+1}"
            existing = [ch for s in selections.values() for ch in s]
            feedback = self.channel_pool.get_feedback(*selections.values())
            
            # 获取决策
            response = self.agents[ap_name].generate_reply(messages=[{
                "role": "user",
                "content": json.dumps({
                    "existing_slots": existing,
                    "feedback": feedback
                }, indent=2)
            }])
            selections[ap_name] = self._parse_response(response, ap_name)
        
        # 阶段2：冲突解决
        final_selections = {}
        existing = []
        for ap_name in [f"AP{i+1}" for i in range(self.num_aps)]:
            resolved = self._resolve_conflicts(existing, selections[ap_name])
            final_selections[ap_name] = resolved
            existing += resolved
        
        # 更新状态
        self.last_selections = final_selections
        self.channel_pool.update_stats(*final_selections.values())
        return list(final_selections.values())

    def _resolve_conflicts(self, existing, new):
        """动态冲突解决"""
        conflict = set(existing) & set(new)
        if not conflict:
            return new
        
        resolved = []
        for ch in new:
            if ch not in conflict:
                resolved.append(ch)
            else:
                alternatives = [c for c in range(self.num_channels) 
                              if c not in existing and c not in resolved]
                if alternatives:
                    resolved.append(random.choice(alternatives))
        
        # 补充缺失
        while len(resolved) < len(new):
            available = [c for c in range(self.num_channels)
                        if c not in existing and c not in resolved]
            if not available:
                break
            resolved.append(random.choice(available))
        
        return sorted(resolved[:len(new)])

    def run(self):
        """主运行循环"""
        print(f"\n动态协调系统启动 | AP数量: {self.num_aps} | 总时隙: {self.num_channels}")
        print(f"初始需求分配: {self.traffic_demand}")
        
        for attempt in range(1, MAX_ATTEMPTS+1):
            ap_slots = self._negotiation_round()
            feedback = self.channel_pool.get_feedback(*ap_slots)
            
            print(f"\n轮次 {attempt} 结果:")
            for ap_name in self.last_selections:
                print(f"{ap_name}: {self.last_selections[ap_name]}", end=" | ")
            print(f"\n冲突时隙: {feedback['conflict']['slots'] or '无'}")
            print(f"利用率: {feedback['utilization']['rate']:.0%}")
            
            self.feedback_history.append(feedback)
            self.visualizer.update(self.feedback_history)
            
            if self._check_success(*ap_slots):
                print("\n达成完美分配！")
                self._save_records()
                self.traffic_demand = self._generate_demand()
                print(f"新需求分配: {self.traffic_demand}")
                
            time.sleep(1)

def get_runtime_params(config_count):
    """获取运行时参数"""
    print("="*40)
    print("TDMA动态协调系统初始化")
    print(f"可用API配置数: {config_count}")
    
    while True:
        try:
            num_aps = int(input(f"请输入AP数量（1-{config_count}）: "))
            if 1 <= num_aps <= config_count:
                break
            print(f"输入值需在1到{config_count}之间")
        except ValueError:
            print("请输入有效数字")
    
    while True:
        try:
            num_channels = int(input("请输入总时隙数（≥AP数量）: "))
            if num_channels >= num_aps:
                break
            print("时隙数不能少于AP数量")
        except ValueError:
            print("请输入有效数字")
    
    return num_aps, num_channels

if __name__ == "__main__":
    # 加载配置文件
    with open("OAI_CONFIG_LIST.json") as f:
        config_list = json.load(f)
    
    # 获取运行参数
    num_aps, num_channels = get_runtime_params(len(config_list))
    
    # 初始化协调器
    coordinator = FeedbackCoordinator(num_aps, num_channels, config_list)
    
    try:
        coordinator.run()
    except KeyboardInterrupt:
        print("\n程序被用户终止")
    finally:
        # 关闭可视化
        plt.ioff()
        plt.close()
        print("系统资源已释放")