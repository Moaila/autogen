"""
@Author: 李文皓
@Description: 自动环境生成的双AP协商系统（可视化增强版）
"""
import random
import json
import time
import math
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from typing import Dict, Any, List
from autogen import ConversableAgent, config_list_from_json
import numpy as np

# ---------- 增强API配置加载 ----------
config_list = config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={
        "model": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": ["https://api.deepseek.com"]
    }
)
assert len(config_list) >= 2, "API配置错误：至少需要2个有效配置"

# ---------- 物理层增强参数 ----------
CHANNELS = [1, 6, 11]
MAX_INTERFERENCE = -65  # dBm
SIMULATION_FPS = 30     # 帧率控制

# ---------- 自动环境生成器 ----------
class EnvironmentGenerator:
    def __init__(self):
        self.time_step = 0
        self._init_patterns()
        
    def _init_patterns(self):
        """初始化环境干扰模式"""
        self.base_pattern = {
            1: {"amplitude": 20, "frequency": 0.2, "phase": 0},
            6: {"amplitude": 15, "frequency": 0.3, "phase": 1},
            11: {"amplitude": 10, "frequency": 0.4, "phase": 2}
        }
        
        # 设备移动性参数
        self.mobility = {
            "cycle": 30,
            "intensity": 5.0
        }
        
        # 突发干扰参数
        self.burst_config = {
            "probability": 0.15,
            "range": (-15, 5)
        }
    
    def generate(self) -> Dict[int, float]:
        """生成动态环境数据"""
        self.time_step += 1
        
        # 基础干扰模式
        base = {
            ch: -50 + params["amplitude"] * math.sin(
                self.time_step * params["frequency"] + params["phase"]
            )
            for ch, params in self.base_pattern.items()
        }
        
        # 突发干扰
        if random.random() < self.burst_config["probability"]:
            ch = random.choice(CHANNELS)
            base[ch] += random.uniform(*self.burst_config["range"])
            
        # 设备移动性影响
        mobile_effect = {
            ch: self.mobility["intensity"] * math.exp(
                -0.1 * ((self.time_step % self.mobility["cycle"]) - 15)**2
            )
            for ch in CHANNELS
        }
        
        # 噪声叠加
        return {
            ch: round(base[ch] + mobile_effect[ch] + random.uniform(-5, 5), 1)
            for ch in CHANNELS
        }

# ---------- 高性能可视化类 ----------
class NetworkVisualizer:
    def __init__(self):
        plt.rcParams['figure.figsize'] = [12, 8]
        plt.rcParams['animation.html'] = 'html5'
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1)
        self.time_buffer = []
        self.data_buffers = {
            "channels": {},
            "interference": {ch: [] for ch in CHANNELS}
        }
        
        self._init_plots()
    
    def _init_plots(self):
        """初始化绘图元素"""
        # 信道选择图
        self.ax1.set_title('Dynamic Channel Selection')
        self.ax1.set_ylabel('Channel Number')
        self.ax1.set_ylim(0, 12)
        self.ax1.set_yticks(CHANNELS)
        self.ax1.grid(True)
        
        # 干扰变化图
        self.ax2.set_title('Real-time Interference Level')
        self.ax2.set_xlabel('Simulation Time (s)')
        self.ax2.set_ylabel('Signal Strength (dBm)')
        self.ax2.grid(True)
        
        # 初始化线条
        self.lines = {
            "ap1": self.ax1.plot([], [], 'ro-', label='AP-Controller')[0],
            "ap2": self.ax1.plot([], [], 'bs-', label='AP-AccessPoint')[0]
        }
        
        self.interf_lines = {
            ch: self.ax2.plot([], [], linestyle='--', label=f'Ch {ch}')[0]
            for ch in CHANNELS
        }
        
        self.ax1.legend(loc='upper right')
        self.ax2.legend(loc='lower left')
    
    def streaming_update(self, time_step: int, aps: List['APAgent']):
        """流式数据更新方法"""
        # 更新缓冲区
        self.time_buffer.append(time_step)
        
        # 更新信道数据
        for i, ap in enumerate(aps):
            ap_name = f"ap{i+1}"
            if ap_name not in self.data_buffers["channels"]:
                self.data_buffers["channels"][ap_name] = []
            self.data_buffers["channels"][ap_name].append(ap.current_channel)
        
        # 更新干扰数据（取第一个AP的扫描结果）
        scan_data = aps[0].latest_scan
        for ch in CHANNELS:
            self.data_buffers["interference"][ch].append(scan_data.get(ch, -90))
        
        # 仅保留最近100个数据点
        max_points = 100
        self.time_buffer = self.time_buffer[-max_points:]
        for key in self.data_buffers["channels"]:
            self.data_buffers["channels"][key] = self.data_buffers["channels"][key][-max_points:]
        for ch in CHANNELS:
            self.data_buffers["interference"][ch] = self.data_buffers["interference"][ch][-max_points:]
        
        # 更新绘图数据
        self.lines["ap1"].set_data(self.time_buffer, self.data_buffers["channels"].get("ap1", []))
        self.lines["ap2"].set_data(self.time_buffer, self.data_buffers["channels"].get("ap2", []))
        
        for ch in CHANNELS:
            self.interf_lines[ch].set_data(self.time_buffer, self.data_buffers["interference"][ch])
        
        # 调整坐标轴范围
        self.ax1.set_xlim(max(0, time_step - max_points + 10), time_step + 2)
        self.ax2.set_xlim(max(0, time_step - max_points + 10), time_step + 2)
        
        return [*self.lines.values(), *self.interf_lines.values()]

# ---------- 自适应AP智能体 ----------
class APAgent(ConversableAgent):
    def __init__(self, name: str, model_type: str):
        super().__init__(
            name=name,
            system_message=self._build_system_prompt(),
            llm_config={
                "config_list": [c for c in config_list if c["model"] == model_type],
                "temperature": 0.7,
                "timeout": 300
            },
            max_consecutive_auto_reply=5
        )
        self.current_channel = random.choice(CHANNELS)
        self.env_gen = EnvironmentGenerator()
        self.latest_scan = self.env_gen.generate()
        self._init_network_params()
    
    def _build_system_prompt(self):
        return """作为智能无线网络协调器，请基于以下策略进行决策：
1. 分析实时频谱扫描数据
2. 评估网络吞吐量需求
3. 预测信道质量变化趋势
4. 生成JSON格式的优化方案"""
    
    def _init_network_params(self):
        """初始化网络参数"""
        self.traffic_profile = {
            "throughput": 1.0,
            "latency": 50  # ms
        }
        
        # 信道质量历史
        self.channel_metrics = {ch: {
            "snr": [],
            "throughput": [],
            "quality": 1.0
        } for ch in CHANNELS}
    
    def dynamic_scan(self):
        """执行环境扫描"""
        self.latest_scan = self.env_gen.generate()
        return self.latest_scan
    
    def analyze_performance(self):
        """综合性能分析"""
        current_metrics = {
            "snr": self.latest_scan[self.current_channel],
            "throughput": self.traffic_profile["throughput"],
            "latency": self.traffic_profile["latency"]
        }
        
        # 更新信道指标
        self.channel_metrics[self.current_channel]["snr"].append(current_metrics["snr"])
        self.channel_metrics[self.current_channel]["throughput"].append(current_metrics["throughput"])
        
        # 计算质量指数
        for ch in CHANNELS:
            snr_avg = np.mean(self.channel_metrics[ch]["snr"][-10:]) if self.channel_metrics[ch]["snr"] else -90
            thr_avg = np.mean(self.channel_metrics[ch]["throughput"][-10:]) if self.channel_metrics[ch]["throughput"] else 0
            self.channel_metrics[ch]["quality"] = 0.7 * (snr_avg + 90)/50 + 0.3 * thr_avg
    
    def make_decision(self, proposal: Dict) -> Dict:
        """智能决策引擎"""
        self.analyze_performance()
        
        decision = {
            "action": "stay",
            "channel": self.current_channel,
            "confidence": 0.0,
            "metrics": {
                "current_snr": self.latest_scan[self.current_channel],
                "best_alternative": None
            }
        }
        
        # 寻找更优信道
        for ch in CHANNELS:
            if ch == self.current_channel:
                continue
                
            quality_diff = self.channel_metrics[ch]["quality"] - self.channel_metrics[self.current_channel]["quality"]
            if quality_diff > 0.1:
                decision.update({
                    "action": "switch",
                    "channel": ch,
                    "confidence": min(1.0, quality_diff * 2),
                    "metrics.best_alternative": {
                        "channel": ch,
                        "snr": self.latest_scan[ch],
                        "quality": self.channel_metrics[ch]["quality"]
                    }
                })
                break
                
        return decision

# ---------- 自动化模拟系统 ----------
class AutoAPSystem:
    def __init__(self, duration=300):
        self.duration = duration
        self.visualizer = NetworkVisualizer()
        self.ap1 = APAgent("AP-Controller", "deepseek-chat")
        self.ap2 = APAgent("AP-AccessPoint", "deepseek-reasoner")
        self._init_simulation()
    
    def _init_simulation(self):
        """初始化模拟参数"""
        self.start_time = time.time()
        self.frame_count = 0
    
    def run(self):
        """执行自动化模拟"""
        def update(frame):
            # 环境扫描
            self.ap1.dynamic_scan()
            self.ap2.dynamic_scan()
            
            # 每5秒协商
            if frame % (SIMULATION_FPS * 5) == 0:
                self._perform_negotiation()
            
            # 更新可视化
            return self.visualizer.streaming_update(frame, [self.ap1, self.ap2])
        
        ani = FuncAnimation(
            self.visualizer.fig,
            update,
            frames=range(self.duration * SIMULATION_FPS),
            interval=1000//SIMULATION_FPS,
            blit=True
        )
        
        plt.show()
    
    def _perform_negotiation(self):
        """执行协商协议"""
        proposal = {
            "type": "auto_probe",
            "timestamp": time.time(),
            "channels": self.ap1.latest_scan,
            "throughput": self.ap1.traffic_profile["throughput"]
        }
        
        try:
            self.ap1.initiate_chat(
                self.ap2,
                message=json.dumps(proposal, indent=2),
                max_turns=2
            )
            
            # 应用协商结果
            resp = json.loads(self.ap2.last_message()["content"])
            if resp["action"] == "switch":
                self.ap1.current_channel = resp["channel"]
                print(f"[{time.strftime('%H:%M:%S')}] 信道切换：{self.ap1.name} -> 信道{resp['channel']}")
        
        except Exception as e:
            print(f"协商异常：{str(e)}")

if __name__ == "__main__":
    simulator = AutoAPSystem(duration=300)  # 5分钟模拟
    simulator.run()