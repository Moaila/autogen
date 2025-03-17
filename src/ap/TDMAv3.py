"""
TDMA动态多时隙协调系统
@作者：李文皓
核心改进：动态负载均衡 + 智能时隙复用
"""
import json
import random
import time
import re
import logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s - %(message)s'
)

# 禁用所有AutoGen相关日志
for log_name in ['autogen', 'autogen.', 'autogen.agent', 'autogen.runtime']:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)

# 禁用Matplotlib日志
logging.getLogger('matplotlib').setLevel(logging.ERROR)
import heapq
from collections import defaultdict
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']  # 按优先级排列
rcParams['axes.unicode_minus'] = False 
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('TkAgg')  
from matplotlib.font_manager import FontProperties
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
NUM_CHANNELS = 8
MAX_ATTEMPTS = 200
TRAFFIC_UPDATE_INTERVAL = 5
DEBUG_MODE = False
LOAD_BALANCE_WINDOW = 10  # 负载均衡观察窗口

# ---------- 高级配置 ----------
CHANNEL_WEIGHTS = {
    "throughput": 0.6,
    "conflict": -1.2,
    "heat_balance": 0.3
}

class ChannelPool:
    """配置可用时隙池"""
    def __init__(self, num_channels):
        self.heatmap = defaultdict(int)
        self.available = list(range(num_channels))
        self.usage_queue = []
        
    def update_heat(self, channels):
        """更新时隙热度"""
        for ch in channels:
            self.heatmap[ch] += 1
            heapq.heappush(self.usage_queue, (self.heatmap[ch], ch))
            
    def get_coolest(self, n):
        """获取最空闲的时隙"""
        coolest = []
        seen = set()
        while len(coolest) < n and self.usage_queue:
            heat, ch = heapq.heappop(self.usage_queue)
            if ch not in seen:
                coolest.append(ch)
                seen.add(ch)
        # 补充未使用的时隙
        coolest += [ch for ch in self.available if ch not in seen][:n-len(coolest)]
        return coolest[:n]

class DynamicChannelCoordinator:
    def __init__(self):
        # 系统状态
        self.traffic_demand = {"AP1": 1, "AP2": 1}
        self.channel_pool = ChannelPool(NUM_CHANNELS)
        
        # 初始化组件
        self._init_agents()
        self._init_history()
        self._init_visualization()

    def _init_history(self):
        """增强历史记录"""
        self.history = {
            "AP1": [],
            "AP2": [],
            "throughput": [],
            "conflicts": [],
            "utilization": []
        }

    def _init_agents(self):
        """初始化双智能体"""
        config_list = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={"model": ["deepseek-chat", "deepseek-reasoner"]}
        )
        
        self.agents = {
            "AP1": ConversableAgent(
                name="AP1-Traffic",
                system_message=self._build_prompt("AP1"),
                llm_config={"config_list": config_list}
            ),
            "AP2": ConversableAgent(
                name="AP2-Optimizer",
                system_message=self._build_prompt("AP2"),
                llm_config={"config_list": config_list}
            )
        }

    def _build_prompt(self, agent):
        """动态提示词生成"""
        return f"""作为无线网络{agent}的智能控制器，请严格遵循以下规则：

        1. 当前需要为{agent}分配{self.traffic_demand[agent]}个时隙
        2. 可用时隙范围：[0到{NUM_CHANNELS-1}]
        3. 要尽可能实现100%时隙利用率
        4. 必须使用严格JSON格式，示例：{{"channels": [1,3,5], "reason": ""}}

        历史时隙热度（使用次数越少优先级越高）：
        {self._get_heatmap_str()}

        请选择时隙组合，并确保："""
    
    def _get_heatmap_str(self):
        """生成可读的热度报告"""
        heat_list = sorted(self.channel_pool.heatmap.items(), key=lambda x: x[1])
        return " | ".join([f"CH{ch}:{cnt}" for ch, cnt in heat_list])

    def _dynamic_demand(self, attempt):
        """生成动态流量需求"""
        base = max(1, attempt // 20)  # 渐进增加复杂度
        new_demand = {
            "AP1": random.randint(1, min(6, NUM_CHANNELS-2)),
            "AP2": random.randint(1, min(6, NUM_CHANNELS-2))
        }
        
        while new_demand["AP1"] + new_demand["AP2"] > NUM_CHANNELS + 1:
            if new_demand["AP1"] > new_demand["AP2"]:
                new_demand["AP1"] -= 1
            else:
                new_demand["AP2"] -= 1
        self.traffic_demand = new_demand
        print(f"\n流量更新: AP1={new_demand['AP1']}x, AP2={new_demand['AP2']}x")

    def _negotiate(self):
        """智能体协商流程"""
        ap1_res = self.agents["AP1"].generate_reply(messages=[{
            "role": "user",
            "content": "请根据历史热度选择最佳时隙"
        }], sender=self.agents["AP2"])
        
        ap2_res = self.agents["AP2"].generate_reply(messages=[{
            "role": "user",
            "content": f"AP1选择：{self._parse_response(ap1_res, 'AP1')}，请优化分配"
        }], sender=self.agents["AP1"])
        
        return (
            self._parse_response(ap1_res, "AP1"),
            self._parse_response(ap2_res, "AP2")
        )

    def _parse_response(self, response, agent_name):
        """响应解析模块"""
        try:
            content = str(getattr(response, 'content', response))
            if DEBUG_MODE:
                logging.debug(f"[{agent_name}原始响应] {content}")

            # 多层级JSON匹配（支持换行和嵌套）
            json_str = re.search(r'\{[\s\S]*?\}', content, re.DOTALL)
            if not json_str:  # 新增空值检查
                raise ValueError("未检测到JSON结构")
            
            data = json.loads(json_str.group())
            return self._validate_channels(data.get("channels", []), agent_name)
            
        except Exception as e:
            logging.warning(f"[{agent_name}] 解析异常: {str(e)}，启用回退策略")
            return self._fallback_strategy(agent_name)
        
    def _fallback_strategy(self, agent_name):
        """回退策略"""
        expected = self.traffic_demand.get(agent_name, 1)
        # 优先选择低频使用的时隙
        coolest = self.channel_pool.get_coolest(expected)
        if len(coolest) >= expected:
            return sorted(coolest[:expected])
        # 补充随机选择
        return sorted(coolest + random.sample(
            [ch for ch in range(NUM_CHANNELS) if ch not in coolest],
            max(0, expected - len(coolest))
        ))

    def _validate_channels(self, channels, agent):
        """智能时隙验证"""
        expected = self.traffic_demand[agent]
        valid = list({int(ch) for ch in channels if 0 <= int(ch) < NUM_CHANNELS})
        
        # 动态补充策略
        if len(valid) < expected:
            need = expected - len(valid)
            valid += self.channel_pool.get_coolest(need)
        return sorted(valid[:expected])

    def _resolve_conflict(self, ap1, ap2):
        """多目标优化冲突解决"""
        conflict = set(ap1) & set(ap2)
        if not conflict:
            return ap2
        
        # 生成候选方案
        candidates = []
        for _ in range(20):
            new_ap2 = random.sample(range(NUM_CHANNELS), len(ap2))
            new_conflict = len(set(ap1) & set(new_ap2))
            utilization = len(set(new_ap2))
            score = CHANNEL_WEIGHTS['conflict'] * new_conflict \
                  + CHANNEL_WEIGHTS['throughput'] * utilization \
                  + CHANNEL_WEIGHTS['heat_balance'] * (1 - self._heat_variance(new_ap2))
            candidates.append((score, new_ap2))
        
        # 选择最优解
        return max(candidates, key=lambda x: x[0])[1]

    def _heat_variance(self, channels):
        """计算时隙使用热度方差"""
        heats = [self.channel_pool.heatmap[ch] for ch in channels]
        return sum((h - sum(heats)/len(heats))**2 for h in heats)

    def _record(self, ap1, ap2):
        """记录系统状态"""
        conflict = len(set(ap1) & set(ap2))
        used_channels = len(set(ap1 + ap2))
        
        self.history["AP1"].append(ap1)
        self.history["AP2"].append(ap2)
        self.history["conflicts"].append(conflict)
        self.history["utilization"].append(used_channels / NUM_CHANNELS)
        self.history["throughput"].append(
            len(ap1)*self.traffic_demand["AP1"] + 
            len(ap2)*self.traffic_demand["AP2"] - 
            conflict*2
        )
        self.channel_pool.update_heat(ap1 + ap2)

    def _init_visualization(self):
        """专业可视化面板"""
        plt.ion()
        self.fig, axs = plt.subplots(2, 2, figsize=(16, 10))
        
        # 分配图
        self.ax1 = axs[0, 0]
        self.ax1.set_title('时隙分配', fontsize=10)
        
        # 吞吐量曲线
        self.ax2 = axs[0, 1]
        self.ax2.set_title('网络吞吐量变化', fontsize=10)
        
        # 冲突统计
        self.ax3 = axs[1, 0]
        self.ax3.set_title('时隙冲突统计', fontsize=10)
        
        # 时隙热度
        self.ax4 = axs[1, 1]
        self.ax4.set_title('时隙使用热度', fontsize=10)
        
        plt.tight_layout()

    def _update_display(self, attempt):
        """实时可视化更新"""
        # 清除旧图
        for ax in [self.ax1, self.ax2, self.ax3, self.ax4]:
            ax.cla()
            
        #分配可视化
        for i, (ap, color) in enumerate(zip(["AP1", "AP2"], ['#FF6F61', '#6B5B95'])):
            data = [(idx, ch) for idx, chs in enumerate(self.history[ap][-20:]) for ch in chs]
            if data:
                x, y = zip(*data)
                self.ax1.scatter(x, y, c=color, label=ap, alpha=0.6)
        self.ax1.legend()
        
        # 吞吐量曲线
        self.ax2.plot(self.history["throughput"], 'g-', label='Throughput')
        self.ax2.set_ylim(0, max(self.history["throughput"]+[10])*1.2)
        
        # 冲突统计
        self.ax3.bar(range(len(self.history["conflicts"])), 
                    self.history["conflicts"], 
                    color='#FF9999')
        
        # 热度
        heats = sorted(self.channel_pool.heatmap.items())
        self.ax4.bar([f"CH{ch}" for ch, _ in heats], 
                    [cnt for _, cnt in heats])
        
        plt.pause(0.05)

    def run(self):
        """系统运行主循环"""
        print("🚀 系统启动 - TDMA动态时隙协调")
        for attempt in range(1, MAX_ATTEMPTS+1):
            try:
                # 动态调整
                if attempt % TRAFFIC_UPDATE_INTERVAL == 0:
                    self._dynamic_demand(attempt)
                
                # 协商流程
                ap1, ap2 = self._negotiate()
                final_ap2 = self._resolve_conflict(ap1, ap2)
                
                # 记录状态
                self._record(ap1, final_ap2)
                
                # 打印日志
                print(f"轮次 {attempt:02d} | AP1: {ap1} → AP2: {final_ap2} | "
                      f"冲突: {len(set(ap1)&set(final_ap2))} | "
                      f"利用率: {self.history['utilization'][-1]:.0%}")
                
                # 更新显示
                if attempt % 2 == 0:
                    self._update_display(attempt)
                
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\n🔴 用户终止")
                break
        
        # 生成最终报告
        plt.ioff()
        self._generate_report()
        plt.show()

    def _generate_report(self):
        """生成分析报告"""
        print("\n" + "="*40)
        print(" 系统运行分析报告 ".center(40, '='))
        print(f"总运行轮次: {len(self.history['AP1'])}")
        print(f"平均冲突数: {sum(self.history['conflicts'])/len(self.history['conflicts']):.1f}")
        print(f"平均利用率: {sum(self.history['utilization'])/len(self.history['utilization']):.0%}")
        print(f"峰值吞吐量: {max(self.history['throughput'])} Mbps")
        print("时隙热度排名:")
        for ch, cnt in sorted(self.channel_pool.heatmap.items(), key=lambda x: -x[1]):
            print(f"  CH{ch}: {cnt}次")

if __name__ == "__main__":
    coordinator = DynamicChannelCoordinator()
    coordinator.run()