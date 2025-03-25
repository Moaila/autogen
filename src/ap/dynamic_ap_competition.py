"""
@Author: 李文皓
@Description: 完整动态双AP协商系统（含大模型集成）
"""
import random
import json
import time
import math
import logging
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from typing import Dict, Any, List
from autogen import ConversableAgent, config_list_from_json

# ---------- 配置日志系统 ----------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("APSimulation")

# ---------- 动态环境生成器 ----------
class DynamicEnvironment:
    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)
        self._init_interference_profiles()
        
    def _init_interference_profiles(self):
        """随机初始化干扰参数"""
        self.base_params = {
            1: {'amplitude': self.rng.uniform(15,25), 'frequency': self.rng.uniform(0.1,0.5), 'phase': self.rng.uniform(0,2*math.pi)},
            6: {'amplitude': self.rng.uniform(15,25), 'frequency': self.rng.uniform(0.1,0.5), 'phase': self.rng.uniform(0,2*math.pi)},
            11: {'amplitude': self.rng.uniform(15,25), 'frequency': self.rng.uniform(0.1,0.5), 'phase': self.rng.uniform(0,2*math.pi)}
        }
        self.mobility_params = {
            'cycle': self.rng.integers(20,40),
            'intensity': self.rng.uniform(3.0,7.0)
        }
        self.burst_params = {
            'probability': self.rng.uniform(0.1,0.2),
            'impact_range': (-self.rng.uniform(10,20), self.rng.uniform(5,10))
        }
    
    def generate(self, time_step: int) -> Dict[int, float]:
        """生成动态干扰数据"""
        base = {
            ch: -50 + params['amplitude'] * math.sin(params['frequency']*time_step + params['phase'])
            for ch, params in self.base_params.items()
        }
        
        # 突发干扰
        if self.rng.random() < self.burst_params['probability']:
            ch = self.rng.choice([1,6,11])
            base[ch] += self.rng.uniform(*self.burst_params['impact_range'])
            
        # 移动性影响
        mobile_effect = {
            ch: self.mobility_params['intensity'] * math.exp(-0.1*((time_step%self.mobility_params['cycle'])-15)**2)
            for ch in [1,6,11]
        }
        
        return {
            ch: round(base[ch] + mobile_effect[ch] + self.rng.normal(0,3),1)
            for ch in [1,6,11]
        }

# ---------- 协议协商框架 ----------
class ProtocolNegotiator:
    def __init__(self):
        self.protocol_stack = [self._default_protocol()]
        
    def _default_protocol(self):
        return {
            'version': '1.0',
            'formats': ['proposal', 'counter'],
            'rules': {'timeout': 5, 'retries': 3}
        }
    
    def evolve(self, history: List[Dict]):
        """基于交互历史演进协议"""
        new_proto = self.protocol_stack[-1].copy()
        new_proto['version'] = f"1.{len(self.protocol_stack)}"
        
        # 自动发现新消息格式
        new_formats = set()
        for msg in history[-10:]:
            if 'type' in msg and msg['type'] not in new_proto['formats']:
                new_formats.add(msg['type'])
        if new_formats:
            new_proto['formats'].extend(new_formats)
            logger.info(f"发现新协议格式: {new_formats}")
        
        self.protocol_stack.append(new_proto)
        return new_proto

# ---------- 增强AP智能体 ----------
class SmartAP(ConversableAgent):
    def __init__(self, name: str, env: DynamicEnvironment, model_config: Dict):
        super().__init__(
            name=name,
            system_message=self._build_system_prompt(),
            llm_config=model_config,
            max_consecutive_auto_reply=2
        )
        self.env = env
        self.protocol = ProtocolNegotiator()
        self.current_channel = 6  # 默认信道
        self._init_metrics()
        
    def _build_system_prompt(self):
        return """作为智能AP协调器，您需要：
1. 分析实时频谱扫描数据
2. 与其他AP协商信道分配
3. 动态调整通信协议
4. 生成JSON格式的技术响应"""

    def _init_metrics(self):
        """初始化性能指标"""
        self.metrics = {
            ch: {'snr': -90, 'util': 0.0, 'score': 0.0}
            for ch in [1,6,11]
        }
        self.strategy = {'aggressive': 0.5, 'cooperative': 0.5}
    
    def scan_environment(self, t: int):
        """执行环境扫描并更新指标"""
        scan_data = self.env.generate(t)
        for ch in scan_data:
            self.metrics[ch]['snr'] = scan_data[ch]
            self.metrics[ch]['util'] = max(0.0, (scan_data[ch] + 90) / 40)
            self.metrics[ch]['score'] = (
                self.strategy['aggressive'] * self.metrics[ch]['util'] +
                self.strategy['cooperative'] * (scan_data[ch] + 90)/40
            )
        return scan_data
    
    def generate_proposal(self) -> Dict:
        """生成协商提案（调用大模型）"""
        prompt = f"""当前信道状态：
{json.dumps(self.metrics, indent=2)}

请根据以下要求生成提案：
1. 选择最优信道并说明技术理由
2. 预测未来3个时间步的干扰变化
3. 使用当前协议版本 {self.protocol.protocol_stack[-1]['version']}
4. 返回JSON格式：{{"type": "proposal", "channel": X, "reason": "..."}}"""

        try:
            response = self.generate_reply(
                messages=[{"role": "user", "content": prompt}],
                sender=self
            )
            proposal = json.loads(response["content"])
            proposal['protocol'] = self.protocol.protocol_stack[-1]
            logger.info(f"{self.name} 生成提案: {proposal['channel']}")
            return proposal
        except Exception as e:
            logger.error(f"提案生成失败: {str(e)}")
            return {"type": "error", "reason": "proposal_failed"}

    def evaluate_proposal(self, proposal: Dict) -> Dict:
        """评估提案并生成响应（调用大模型）"""
        prompt = f"""收到来自{proposal.get('sender', '')}的提案：
{json.dumps(proposal, indent=2)}

当前环境状态：
{json.dumps(self.metrics, indent=2)}

评估要求：
1. 分析提案的技术合理性 
2. 预测接受后的网络性能变化
3. 返回JSON格式：{{"action": "accept/reject", "channel": X, "confidence": 0.X}}"""

        try:
            response = self.generate_reply(
                messages=[{"role": "user", "content": prompt}],
                sender=self
            )
            decision = json.loads(response["content"])
            logger.info(f"{self.name} 决策: {decision['action']} ({decision['confidence']:.2f})")
            
            # 协议演进
            self.protocol.evolve(self._message_history)
            return decision
        except Exception as e:
            logger.error(f"评估失败: {str(e)}")
            return {"action": "reject", "reason": "evaluation_failed"}

# ---------- 可视化系统 ----------
class APVisualizer:
    def __init__(self):
        plt.rcParams["figure.figsize"] = (12, 8)
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1)
        self._init_axes()
        self.data = {
            'channels': [],
            'interference': {1: [], 6: [], 11: []},
            'decisions': []
        }
    
    def _init_axes(self):
        """初始化可视化界面"""
        # 信道分配图
        self.ax1.set_title('AP Channel Allocation')
        self.ax1.set_ylabel('Channel')
        self.ax1.set_ylim(0.5, 3.5)
        self.ax1.set_yticks([1,2,3])
        self.ax1.set_yticklabels(['Ch1', 'Ch6', 'Ch11'])
        
        # 干扰变化图
        self.ax2.set_title('Interference Level')
        self.ax2.set_xlabel('Time Step')
        self.ax2.set_ylabel('dBm')
        self.ax2.set_ylim(-90, -50)
    
    def update(self, t: int, ap1: SmartAP, ap2: SmartAP):
        """更新可视化数据"""
        # 记录信道分配
        self.data['channels'].append((ap1.current_channel, ap2.current_channel))
        
        # 记录干扰数据（使用AP1的扫描结果）
        scan_data = ap1.metrics
        for ch in [1,6,11]:
            self.data['interference'][ch].append(scan_data[ch]['snr'])
        
        # 更新绘图
        self._draw(t)
    
    def _draw(self, t: int):
        """重绘图表"""
        self.ax1.clear()
        self.ax2.clear()
        self._init_axes()
        
        # 绘制信道分配
        ap1_ch = [c[0] for c in self.data['channels']]
        ap2_ch = [c[1] for c in self.data['channels']]
        self.ax1.plot(ap1_ch, 'ro-', label='AP1')
        self.ax1.plot(ap2_ch, 'bs-', label='AP2')
        self.ax1.legend()
        
        # 绘制干扰变化
        for ch in [1,6,11]:
            self.ax2.plot(self.data['interference'][ch], 
                        linestyle='--' if ch==6 else '-',
                        label=f'Ch{ch}')
        self.ax2.legend()
        
        plt.tight_layout()
        plt.pause(0.01)

# ---------- 模拟引擎 ----------
class SimulationEngine:
    def __init__(self, duration=300):
        self.duration = duration
        self.env = DynamicEnvironment(seed=int(time.time()))
        self.visualizer = APVisualizer()
        
        # 初始化AP（使用不同模型）
        config = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={"model": ["deepseek-chat", "deepseek-reasoner"]}
        )
        self.ap1 = SmartAP("AP1", self.env, {
            "config_list": [c for c in config if c["model"]=="deepseek-chat"],
            "temperature": 0.7,
            "timeout": 60
        })
        self.ap2 = SmartAP("AP2", self.env, {
            "config_list": [c for c in config if c["model"]=="deepseek-reasoner"],
            "temperature": 0.5,
            "timeout": 60
        })
        
        logger.info("系统初始化完成")
        logger.info(f"AP1模型: {self.ap1.llm_config['config_list'][0]['model']}")
        logger.info(f"AP2模型: {self.ap2.llm_config['config_list'][0]['model']}")

    def run(self):
        """执行模拟"""
        logger.info("启动动态协商模拟...")
        try:
            for t in range(self.duration):
                # 环境扫描
                self.ap1.scan_environment(t)
                self.ap2.scan_environment(t)
                
                # 每5秒协商
                if t % 5 == 0:
                    proposal = self.ap1.generate_proposal()
                    decision = self.ap2.evaluate_proposal(proposal)
                    
                    # 应用决策
                    if decision['action'] == 'accept':
                        self.ap1.current_channel = proposal['channel']
                        self.ap2.current_channel = 11  # 默认避让信道
                    else:
                        self.ap1.current_channel = 6    # 默认中间信道
                        self.ap2.current_channel = decision.get('channel', 11)
                    
                    logger.info(f"时间步 {t} 最终分配: AP1@{self.ap1.current_channel}, AP2@{self.ap2.current_channel}")
                
                # 更新可视化
                self.visualizer.update(t, self.ap1, self.ap2)
                
                time.sleep(0.1)  # 控制运行速度
            
            logger.info("模拟正常结束")
        except KeyboardInterrupt:
            logger.warning("用户中断模拟")
        finally:
            plt.close('all')

if __name__ == "__main__":
    simulation = SimulationEngine(duration=300)
    simulation.run()