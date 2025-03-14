"""
TDMA信道协调模拟系统
特点：
1. 8个可选信道，时隙划分为100ms/段
2. 冲突检测与Q-learning策略
3. 实时协调可视化
"""
import random
import numpy as np
import matplotlib.pyplot as plt
import time
from collections import defaultdict
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统参数 ----------
NUM_CHANNELS = 8
TIME_SLOT_DURATION = 0.1  # 100ms
FRAME_SIZE = 10           # 10个时隙为一帧

# ---------- TDMA环境生成器 ----------
class TDMAScheduler:
    def __init__(self):
        self.current_slot = 0
        self.collision_log = defaultdict(int)
    
    def next_slot(self):
        self.current_slot = (self.current_slot + 1) % FRAME_SIZE
        return self.current_slot
    
    def record_collision(self, channel):
        self.collision_log[channel] += 1
    
    def get_channel_usage(self):
        return dict(self.collision_log)

# ---------- 强化学习AP智能体 ----------
class TDMAAPAgent(ConversableAgent):
    def __init__(self, name, config):
        super().__init__(
            name=name,
            system_message=self._build_system_prompt(),
            llm_config=config,
            max_consecutive_auto_reply=1
        )
        self.q_table = {ch: 1.0 for ch in range(NUM_CHANNELS)}
        self.epsilon = 0.3
        self.last_reward = 0
        self._init_history()
    
    def _build_system_prompt(self):
        return f"""作为TDMA AP智能体，您需要：
1. 在{FRAME_SIZE}时隙帧中选择可用信道
2. 避免与其他AP发生冲突
3. 学习长期最优信道分配策略
4. 响应必须为信道编号(0-{NUM_CHANNELS-1})"""

    def _init_history(self):
        self.history = {
            'success': defaultdict(int),
            'collision': defaultdict(int)
        }
    
    def choose_channel(self, slot):
        """ε-greedy策略选择信道"""
        if random.random() < self.epsilon:
            return random.randint(0, NUM_CHANNELS-1)
        else:
            return max(self.q_table, key=self.q_table.get)
    
    def update_q(self, channel, reward):
        """Q值更新规则"""
        alpha = 0.1  # 学习率
        gamma = 0.9  # 折扣因子
        self.q_table[channel] += alpha * (reward + gamma * self.last_reward - self.q_table[channel])
        self.last_reward = reward
    
    def record_outcome(self, channel, success):
        """记录传输结果"""
        if success:
            self.history['success'][channel] += 1
        else:
            self.history['collision'][channel] += 1
    
    def generate_reply(self, messages, sender, **kwargs):
        """生成信道选择响应"""
        prompt = f"""历史统计（成功率/冲突率）：
{self.history}

当前时隙：{kwargs['current_slot']}
请选择信道(0-{NUM_CHANNELS-1})："""
        
        try:
            response = super().generate_reply(
                messages=[{"role": "user", "content": prompt}],
                sender=sender
            )
            return int(response['content'].strip())
        except:
            return random.randint(0, NUM_CHANNELS-1)

# ---------- 冲突检测系统 ----------
class ConflictDetector:
    @staticmethod
    def detect(ap1_ch, ap2_ch):
        return ap1_ch == ap2_ch
    
    @classmethod
    def calculate_throughput(cls, success_count, total_slots):
        return success_count / total_slots

# ---------- 可视化系统 ----------
class TDMAVisualizer:
    def __init__(self):
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(15,6))
        self.data = {
            'ap1_ch': [],
            'ap2_ch': [],
            'throughput': []
        }
    
    def update(self, slot, ap1, ap2, throughput):
        # 信道选择轨迹
        self.data['ap1_ch'].append(ap1)
        self.data['ap2_ch'].append(ap2)
        self.data['throughput'].append(throughput)
        
        # 实时更新图表
        self._plot_channels()
        self._plot_throughput()
        plt.pause(0.001)
    
    def _plot_channels(self):
        self.ax1.clear()
        self.ax1.set_title('Channel Selection')
        self.ax1.plot(self.data['ap1_ch'], 'r-', label='AP1')
        self.ax1.plot(self.data['ap2_ch'], 'b--', label='AP2')
        self.ax1.set_ylim(-1, NUM_CHANNELS)
        self.ax1.legend()
    
    def _plot_throughput(self):
        self.ax2.clear()
        self.ax2.set_title('Network Throughput')
        self.ax2.plot(self.data['throughput'], 'g-', label='Success Rate')
        self.ax2.set_ylim(0, 1.0)
        self.ax2.legend()

# ---------- 模拟引擎 ----------
class TDMASimulation:
    def __init__(self, total_slots=500):
        self.total_slots = total_slots
        self.scheduler = TDMAScheduler()
        self.visualizer = TDMAVisualizer()
        
        # 初始化AP
        config = config_list_from_json("OAI_CONFIG_LIST.json")
        self.ap1 = TDMAAPAgent("AP1", {"config_list": config})
        self.ap2 = TDMAAPAgent("AP2", {"config_list": config})
        
        # 性能统计
        self.success_count = 0
    
    def run(self):
        print("启动TDMA协调模拟...")
        try:
            for _ in range(self.total_slots):
                current_slot = self.scheduler.next_slot()
                
                # AP选择信道
                ap1_ch = self.ap1.generate_reply(
                    [], self.ap2, current_slot=current_slot
                )
                ap2_ch = self.ap2.generate_reply(
                    [], self.ap1, current_slot=current_slot
                )
                
                # 冲突检测
                collision = ConflictDetector.detect(ap1_ch, ap2_ch)
                
                # 更新学习策略
                if not collision:
                    self.success_count += 1
                    self.ap1.update_q(ap1_ch, 1.0)
                    self.ap2.update_q(ap2_ch, 1.0)
                    self.ap1.record_outcome(ap1_ch, True)
                    self.ap2.record_outcome(ap2_ch, True)
                else:
                    self.scheduler.record_collision(ap1_ch)
                    self.ap1.update_q(ap1_ch, -2.0)
                    self.ap2.update_q(ap2_ch, -2.0)
                    self.ap1.record_outcome(ap1_ch, False)
                    self.ap2.record_outcome(ap2_ch, False)
                
                # 更新可视化
                throughput = ConflictDetector.calculate_throughput(
                    self.success_count, _+1
                )
                self.visualizer.update(current_slot, ap1_ch, ap2_ch, throughput)
                
                time.sleep(TIME_SLOT_DURATION)
            
            print(f"最终吞吐量: {throughput:.2%}")
        except KeyboardInterrupt:
            print("模拟提前终止")
        finally:
            plt.show()

if __name__ == "__main__":
    sim = TDMASimulation()
    sim.run()