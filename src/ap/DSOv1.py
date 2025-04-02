"""
Wi-Fi信道动态分配系统
@作者：李文皓
@场景：多设备Wi-Fi信道优化
@版本：路由器+双设备版
@面向场景：
Jimmy 邀请同学到他的公寓学习，准备参加即将到来的考试。
由于公寓是⼤学的⼀部分，因此他们拥有 1Gbps 的互联⽹接⼊。
为了享受速度，Jimmy 拥有 Wi-Fi 7 旗 舰 BE19000 AP。在讨论过程中，他们发现需要从学校⻔⼾⽹站下载⼀个⼤⽂件。
他们所有⼈都同时开始下载同⼀个⽂件，发现没有⼈能获得良好的速度。
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

from collections import defaultdict
import matplotlib
matplotlib.use('TkAgg')  
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False 
import matplotlib.pyplot as plt
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
TOTAL_BW = 1600  # 总带宽(MHz)
MAX_CHANNELS = 12  # 可用信道数(6GHz频段)
SAVE_FILE = "wifi_allocation_report.json"
DEVICE_TYPES = {
    "iPhone": {"bw": 160, "mimo": 2, "qos": 5},
    "Laptop": {"bw": 80, "mimo": 3, "qos": 3}
}

class DeviceProfile:
    """设备能力配置文件"""
    def __init__(self, name):
        self.name = name
        self.device_type = "iPhone" if "iPhone" in name else "Laptop"
        self.max_bw = DEVICE_TYPES[self.device_type]["bw"]
        self.mimo = DEVICE_TYPES[self.device_type]["mimo"]
        self.qos = DEVICE_TYPES[self.device_type]["qos"]
        self.rssi = random.randint(-70, -40)
        self.interference = random.randint(5, 30)
        self.throughput = 0

class RouterResourceManager:
    """路由器资源管理引擎"""
    def __init__(self):
        self.channels = list(range(37, 37+MAX_CHANNELS*16, 16))  # 6GHz信道
        self.allocations = defaultdict(dict)
        self.history = []
        
    def _generate_initial(self):
        """生成随机初始分配"""
        allocation = {}
        remaining_bw = TOTAL_BW
        
        # 随机选择主设备
        main_devices = random.sample(DEVICE_TYPES.keys(), 2)
        for dev in main_devices:
            bw = min(DEVICE_TYPES[dev]["bw"], remaining_bw)
            if bw > 0:
                allocation[dev] = {
                    "channels": random.sample(self.channels, 2),
                    "bw": bw,
                    "mimo": f'{DEVICE_TYPES[dev]["mimo"]}x{DEVICE_TYPES[dev]["mimo"]}'
                }
                remaining_bw -= bw
        return allocation

    def optimize(self, feedback_data):
        """智能优化分配"""
        # 按QoS优先级排序
        sorted_devices = sorted(feedback_data.items(),
                              key=lambda x: (-x[1].qos, x[1].rssi),
                              reverse=True)
        
        allocation = {}
        used_channels = set()
        remaining_bw = TOTAL_BW
        
        for dev_name, profile in sorted_devices:
            req_bw = profile.max_bw
            available_ch = [ch for ch in self.channels if ch not in used_channels]
            
            if len(available_ch) >= 2 and req_bw <= remaining_bw:
                selected = random.sample(available_ch, 2)
                allocation[dev_name] = {
                    "channels": selected,
                    "bw": req_bw,
                    "mimo": f"{profile.mimo}x{profile.mimo}"
                }
                used_channels.update(selected)
                remaining_bw -= req_bw
            elif remaining_bw >= 40:  # 最低保障
                allocation[dev_name] = {
                    "channels": [random.choice(available_ch)],
                    "bw": 40,
                    "mimo": "1x1"
                }
                remaining_bw -= 40
                
        self.history.append(allocation)
        return allocation

class WiFiVisualizer:
    """动态可视化引擎"""
    def __init__(self, router):
        self.fig = plt.figure(figsize=(14, 8))
        self.colors = {'iPhone': '#1f77b4', 'Laptop': '#2ca02c'}
        self.channels = router.channels
        self.ax1 = None  # 初始化坐标轴引用
        self.ax2 = None
        self._init_axes()  # 创建坐标轴
        
    def _init_axes(self):
        """初始化绘图区域"""
        self.ax1 = self.fig.add_subplot(121)  # 左侧频谱图
        self.ax2 = self.fig.add_subplot(122)  # 右侧状态表
        self.ax1.set_title('信道分配状态')
        self.ax1.set_xlabel('带宽 (MHz)')
        self.ax1.set_ylabel('信道频率 (MHz)')
        self.ax2.axis('off')  # 关闭右侧坐标轴

    def update(self, allocation):
        """更新可视化内容"""
        # 清空之前内容
        self.ax1.clear()
        self.ax2.clear()
        
        # 绘制频谱分配
        for dev, info in allocation.items():
            color = self.colors['iPhone' if 'iPhone' in dev else 'Laptop']
            for ch in info['channels']:
                self.ax1.barh(
                    str(ch), info['bw'], 
                    height=0.6, 
                    color=color,
                    edgecolor='black'
                )
        
        # 绘制设备状态表
        cell_data = [
            [dev, info['bw'], info['mimo'], f"{info['bw'] * 5}Mbps"]  # 简化速率计算
            for dev, info in allocation.items()
        ]
        self.ax2.table(
            cellText=cell_data,
            colLabels=['设备', '带宽', 'MIMO', '预估速率'],
            loc='center',
            cellLoc='center',
            colWidths=[0.2, 0.2, 0.2, 0.3]
        )
        
        plt.tight_layout()
        plt.draw()
        plt.pause(0.8)

class WiFiCoordinator:
    """系统协调中枢"""
    def __init__(self):
        self.router = RouterResourceManager()
        self.visualizer = WiFiVisualizer(self.router)
        self.devices = {}
        self._init_agents()
        
    def _init_agents(self):
        """初始化智能体"""
        config_list = config_list_from_json("OAI_CONFIG_LIST.json")
        
        # 路由器代理
        self.router_agent = ConversableAgent(
            name="BE19000-Router",
            system_message="""您是Wi-Fi 7路由器的控制核心，具备以下能力：
1. 三频段并发：2.4G/5G/6G 同时工作
2. 4K QAM调制：提升20%传输效率
3. 320MHz带宽：支持连续/非连续信道绑定
4. 16条数据流：支持MU-MIMO动态分配

请根据设备反馈：
1. 优先保障时延敏感型设备
2. 为高带宽设备分配连续信道
3. 平衡各频段负载""",
            llm_config={"config_list": [config_list[0]], "temperature": 0.4}
        )
        
        # 设备代理
        self.device_agents = {
            "iPhone15-Pro": ConversableAgent(
                name="iPhone15-Pro",
                system_message="""您是支持Wi-Fi 7的iPhone 15 Pro，能力包括：
- 双频并发：5G+6G 同时连接
- 160MHz带宽：最高2.4Gbps速率
- 智能天线：波束成形技术
- 低时延模式：<10ms游戏模式

请反馈：
1. 当前使用的应用类型（游戏/视频/下载）
2. 信号强度（RSSI）
3. 首选频段（5G/6G）""",
                llm_config={"config_list": [config_list[1]], "temperature": 0.3}
            ),
            "ThinkPad-X1": ConversableAgent(
                name="ThinkPad-X1",
                system_message="""您是配备Killer Wi-Fi 7的笔记本电脑：
- 三频支持：2.4G/5G/6G 自动切换
- 240MHz总带宽：160+80双连接
- 多线程下载：支持6条并发流
- 4K QAM调制：提升25%吞吐量

请反馈：
1. 当前传输类型（大文件/视频流/云同步）
2. 需要的稳定带宽
3. 可接受的时延范围""",
                llm_config={"config_list": [config_list[2]], "temperature": 0.3}
            )
        }

    def _get_feedback(self, device):
        """获取设备反馈（带容错）"""
        try:
            response = self.device_agents[device].generate_reply(messages=[{
                "role": "user",
                "content": "请报告当前网络需求"
            }])
            return self._parse_feedback(response.content, device)
        except:
            return self._default_feedback(device)

    def _parse_feedback(self, content, device):
        """解析设备反馈"""
        try:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            return json.loads(match.group())
        except:
            return self._default_feedback(device)

    def _default_feedback(self, device):
        """默认反馈数据"""
        return {
            "iPhone15-Pro": {
                "app": "game",
                "rssi": -55,
                "band_preference": "6G"
            },
            "ThinkPad-X1": {
                "traffic": "download",
                "required_bw": 160,
                "latency": 50
            }
        }.get(device, {})

    def _generate_report(self, allocation):
        """生成详细报告"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "allocations": allocation,
            "performance": {
                "total_throughput": sum(dev['bw']*2 for dev in allocation.values()),
                "channel_utilization": f"{len(allocation)*2/MAX_CHANNELS:.0%}",
                "qos_level": max(DEVICE_TYPES['iPhone' if 'iPhone' in d else 'Laptop']['qos'] for d in allocation)
            }
        }
        with open(SAVE_FILE, 'w') as f:
            json.dump(report, f, indent=2)
        return report

    def run(self):
        """主运行流程"""
        print("=== 初始化阶段 ===")
        init_alloc = self.router._generate_initial()
        print("初始分配方案：", json.dumps(init_alloc, indent=2))
        
        print("\n=== 设备反馈阶段 ===")
        feedbacks = {}
        for device in self.device_agents:
            fb = self._get_feedback(device)
            print(f"{device}反馈：{json.dumps(fb, indent=2, ensure_ascii=False)}")
            feedbacks[device] = DeviceProfile(device)
            feedbacks[device].__dict__.update(fb)
        
        print("\n=== 优化分配阶段 ===")
        final_alloc = self.router.optimize(feedbacks)
        print("最终分配：", json.dumps(final_alloc, indent=2))
        
        print("\n=== 生成报告 ===")
        report = self._generate_report(final_alloc)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        
        self.visualizer.update(final_alloc)
        plt.ioff()
        plt.show()

if __name__ == "__main__":
    coordinator = WiFiCoordinator()
    coordinator.run()