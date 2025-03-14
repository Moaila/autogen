"""
TDMA动态多信道协调系统（生产级优化版）
功能特性：
1. 智能JSON解析引擎
2. 动态优先级冲突解决
3. 流量预测机制
4. 专业级可视化
"""
import json
import random
import time
import re
import logging
import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']  
matplotlib.rcParams['axes.unicode_minus'] = False  
import logging
logging.getLogger('matplotlib').setLevel(logging.ERROR)  
from matplotlib.font_manager import FontProperties
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
NUM_CHANNELS = 8
MAX_ATTEMPTS = 50
CONVERGENCE_THRESHOLD = 10
TRAFFIC_UPDATE_INTERVAL = 3
DEBUG_MODE = False  # 开启调试日志

# ---------- 模型配置 ----------
MODEL_CONFIG = {
    "deepseek-chat": {
        "temperature": 0.7,
        "role_prompt": "根据流量需求选择最佳信道组合",
        "response_template": {"channels": [], "reason": ""}
    },
    "deepseek-reasoner": {
        "temperature": 0.3,
        "role_prompt": "计算最优多信道分配方案",
        "response_template": {"channels": [], "reason": ""}
    }
}

class SimpleExpSmoothing:
    """指数平滑流量预测器"""
    def __init__(self, alpha=0.5):
        self.alpha = alpha
        self.level = None
        
    def predict(self):
        return self.level if self.level is not None else 1
        
    def update(self, new_value):
        self.level = new_value if self.level is None else \
            self.alpha * new_value + (1 - self.alpha) * self.level

class DynamicChannelCoordinator:
    def __init__(self):
        # 系统状态
        self.traffic_demand = {"AP1": 1, "AP2": 1}
        self.traffic_predictor = {
            "AP1": SimpleExpSmoothing(alpha=0.7),
            "AP2": SimpleExpSmoothing(alpha=0.5)
        }
        
        # 初始化组件
        self._init_history()
        self._init_agents()
        self._init_visualization()
        
        # 调试模式
        if DEBUG_MODE:
            self._enable_debug_logging()

    def _init_history(self):
        """初始化历史记录"""
        self.channel_history = {
            "AP1": [],
            "AP2": [],
            "conflicts": 0,
            "throughput": []
        }

    def _init_agents(self):
        """初始化智能体"""
        config_list = config_list_from_json(
            "OAI_CONFIG_LIST.json",
            filter_dict={
                "model": ["deepseek-chat", "deepseek-reasoner"],
                "base_url": ["https://api.deepseek.com"]
            }
        )
        
        self.agents = {
            "AP1": ConversableAgent(
                name="AP1-Traffic",
                system_message=self._build_system_prompt("AP1"),
                llm_config={
                    "config_list": [c for c in config_list if c["model"] == "deepseek-chat"],
                    "temperature": MODEL_CONFIG["deepseek-chat"]["temperature"],
                    "timeout": 30000
                },
                human_input_mode="NEVER",
                max_consecutive_auto_reply=2
            ),
            "AP2": ConversableAgent(
                name="AP2-Optimizer",
                system_message=self._build_system_prompt("AP2"),
                llm_config={
                    "config_list": [c for c in config_list if c["model"] == "deepseek-reasoner"],
                    "temperature": MODEL_CONFIG["deepseek-reasoner"]["temperature"],
                    "timeout": 30000
                },
                human_input_mode="NEVER",
                max_consecutive_auto_reply=2
            )
        }

    def _build_system_prompt(self, agent_type):
        """生成强化约束的提示词"""
        model_type = "deepseek-chat" if agent_type == "AP1" else "deepseek-reasoner"
        example = json.dumps(MODEL_CONFIG[model_type]['response_template'], ensure_ascii=False)
        
        return f"""# 信道分配智能体指令（{agent_type}）

## 核心任务
1. 根据当前流量需求（AP1:{self.traffic_demand['AP1']}x，AP2:{self.traffic_demand['AP2']}x）选择信道
2. 从0到{NUM_CHANNELS-1}号中选择{self.traffic_demand[agent_type]}个正交信道

## 硬性要求
• 必须使用严格JSON格式
• channels数组元素为整数
• 示例格式：
{example}

## 禁止事项
❌ 不要添加解释性文字
❌ 不要使用中文标点
❌ 不要超出指定范围"""

    def _update_traffic_demand(self, attempt):
        """带预测的动态更新"""
        if attempt % TRAFFIC_UPDATE_INTERVAL == 0:
            # 生成预测需求
            new_demand = {
                "AP1": max(1, round(
                    self.traffic_predictor["AP1"].predict() + random.uniform(-0.5, 1)
                )),
                "AP2": max(1, round(
                    self.traffic_predictor["AP2"].predict() + random.uniform(-0.3, 0.8)
                ))
            }
            
            # 更新预测模型
            self.traffic_predictor["AP1"].update(self.traffic_demand["AP1"])
            self.traffic_predictor["AP2"].update(self.traffic_demand["AP2"])
            
            self.traffic_demand = new_demand
            print(f"\n流量更新 | AP1: {new_demand['AP1']}x | AP2: {new_demand['AP2']}x")

    def _negotiate_round(self, attempt):
        """智能协商流程"""
        self._update_traffic_demand(attempt)
        
        # AP1选择
        ap1_res = self.agents["AP1"].generate_reply(
            messages=[{"role": "user", "content": "请选择当前信道"}],
            sender=self.agents["AP2"]
        )
        ap1_chs = self._parse_response(ap1_res, "AP1")
        
        # AP2优化
        ap2_res = self.agents["AP2"].generate_reply(
            messages=[{
                "role": "user",
                "content": f"已知AP1选择：{ap1_chs}，请优化分配"
            }],
            sender=self.agents["AP1"]
        )
        ap2_chs = self._parse_response(ap2_res, "AP2")
        
        return ap1_chs, ap2_chs

    def _parse_response(self, response, agent_name):
        """增强型解析引擎"""
        try:
            content = str(getattr(response, 'content', response))
            if DEBUG_MODE:
                logging.debug(f"[{agent_name}原始响应] {content}")

            # 多阶段JSON清洗
            json_str = self._robust_json_extract(content)
            data = self._safe_json_load(json_str, agent_name)
            
            # 信道验证逻辑保持不变
            return self._validate_channels(data.get("channels", []), agent_name)
            
        except Exception as e:
            logging.warning(f"[{agent_name}] 解析异常，启用回退策略: {str(e)}")  # 降级为警告
            return self._fallback_strategy(agent_name)
    
    # def _validate_channels(self, channels, agent_name):
    #     expected_num = self.traffic_demand[agent_name]
    #     valid_channels = []
    #     seen = set()
        
    #     for ch in channels:
    #         if not isinstance(ch, int):
    #             try: ch = int(ch)
    #             except: continue
    #         if 0 <= ch < NUM_CHANNELS and ch not in seen:
    #             valid_channels.append(ch)
    #             seen.add(ch)
        
    #     current_num = len(valid_channels)
    #     available = [ch for ch in range(NUM_CHANNELS) if ch not in seen]
        
    #     if current_num < expected_num:
    #         need = expected_num - current_num
    #         add_num = min(need, len(available))
    #         valid_channels += available[:add_num]
    #         if add_num < need:
    #             valid_channels += random.choices(range(NUM_CHANNELS), k=need-add_num)
    #     elif current_num > expected_num:
    #         valid_channels = valid_channels[:expected_num]
        
    #     while len(valid_channels) < expected_num:
    #         valid_channels.append(random.randint(0, NUM_CHANNELS-1))
        
    #     return sorted(valid_channels[:expected_num])

    def _validate_channels(self, channels, agent_name):
        expected_num = self.traffic_demand[agent_name]
        valid = []
        
        # 类型转换与去重
        for ch in channels:
            try:
                ch_int = int(float(ch))  # 兼容浮点型输入
                if 0 <= ch_int < NUM_CHANNELS:
                    valid.append(ch_int)
            except:
                pass
        
        # 去重处理
        seen = set()
        unique = []
        for ch in valid:
            if ch not in seen:
                seen.add(ch)
                unique.append(ch)
        
        # 动态补充策略
        current_num = len(unique)
        if current_num < expected_num:
            # 优先补充未使用的信道
            available = [ch for ch in range(NUM_CHANNELS) if ch not in seen]
            need = expected_num - current_num
            add = min(need, len(available))
            unique += available[:add]
            
            # 允许重复补充剩余数量
            if (remaining := need - add) > 0:
                unique += random.choices(range(NUM_CHANNELS), k=remaining)
        
        # 保证最终数量
        return sorted(unique[:expected_num])
        
    def _robust_json_extract(self, content):
        """多层级JSON提取"""
        # 增强正则表达式模式
        patterns = [
            r'({[\s\S]*?})',  # 宽松匹配最外层{}
            r'$$[\s\S]*?$$'    # 匹配数组结构
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                # 选择最长的候选结果
                return max(matches, key=len, default='{}')
        return '{}'
    
    def _safe_json_load(self, json_str, agent_name):
        """安全JSON解析"""
        max_retries = 3
        for i in range(max_retries):
            try:
                # 自动修复常见语法错误
                corrected = json_str.replace("'", '"').replace("，", ",")
                corrected = re.sub(r'(\w+)(\s*:\s*)', r'"\1"\2', corrected)
                return json.loads(corrected)
            except json.JSONDecodeError as e:
                # 自动截断错误位置后的内容
                json_str = json_str[:e.pos]
        return {"channels": []}

    def _extract_json(self, content):
        """多模式JSON提取"""
        patterns = [
            r'```json\n([\s\S]+?)\n```',
            r'\{[\s\S]*\}'
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1) if '```' in pattern else match.group()
        return None

    def _correct_json(self, json_str):
        """自动语法修正"""
        corrections = [
            (r"(\w+)(\s*:\s*)", r'"\1"\2'),  # 键加引号
            (r"'", '"'),                     # 单引号转换
            (r'[\u4e00-\u9fff]', ''),        # 去除中文
            (r'，', ',')                      # 标点转换
        ]
        for pattern, repl in corrections:
            json_str = re.sub(pattern, repl, json_str)
        return json_str

    def _fallback_strategy(self, agent_name):
        """智能回退策略"""
        base = self.traffic_demand.get(agent_name, 1)
        return sorted(random.sample(range(NUM_CHANNELS), min(base, 3)))

    def _resolve_conflict(self, ap1_chs, ap2_chs):
        """动态冲突解决"""
        conflict = set(ap1_chs) & set(ap2_chs)
        if not conflict:
            return ap2_chs
        
        # 计算流量权重
        weight = self.traffic_demand["AP1"] / sum(self.traffic_demand.values())
        
        if weight > 0.6:
            return self._priority_resolution(ap1_chs, ap2_chs)
        elif weight < 0.4:
            return self._priority_resolution(ap2_chs, ap1_chs)
        else:
            return self._balanced_resolution(ap1_chs, ap2_chs)

    def _priority_resolution(self, priority_chs, other_chs):
        """优先级解决方案"""
        available = [ch for ch in range(NUM_CHANNELS) if ch not in priority_chs]
        required = len(other_chs) - len(set(other_chs) - set(priority_chs))
        
        if len(available) >= required:
            new_chs = list(set(other_chs) - set(priority_chs))
            new_chs += random.sample(available, required)
            return sorted(new_chs)[:3]
        return random.sample(range(NUM_CHANNELS), len(other_chs))

    def _balanced_resolution(self, ap1_chs, ap2_chs):
        """均衡分配方案"""
        common = list(set(ap1_chs) & set(ap2_chs))
        unique_ap2 = list(set(ap2_chs) - set(common))
        available = [ch for ch in range(NUM_CHANNELS) if ch not in ap1_chs + ap2_chs]
        
        # 重新分配
        keep_num = min(len(common), 1)
        new_chs = unique_ap2 + common[:keep_num]
        new_chs += available[:3 - len(new_chs)]
        
        return sorted(new_chs)[:3]

    def _init_visualization(self):
        """专业可视化初始化"""
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(14, 7))

        # 通用字体配置
        font_options = [
            'DejaVu Sans', 
            'Arial Unicode MS', 
            'Microsoft YaHei', 
            'sans-serif'  # 系统默认
        ]
        
        # 新字体配置方案
        try:
            # 尝试加载常见中文字体
            self.font = FontProperties(family=font_options)
            plt.rcParams['font.sans-serif'] = font_options
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示
        except Exception as e:
            print(f"字体配置异常: {str(e)}，使用系统默认设置")
        
        # 增强可视化元素
        self.ax.set_title('Dynamic Channel Coordination', 
                     fontsize=14, pad=15, 
                     fontproperties=self.font)
        self.ax.set_xlabel('Iteration Rounds', 
                        labelpad=12, 
                        fontproperties=self.font)
        self.ax.set_ylabel('Channel Allocation', 
                        labelpad=12, 
                        fontproperties=self.font)
        
        # 添加辅助图形元素
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.ax.tick_params(axis='both', which='major', labelsize=9)
        
        # 吞吐量曲线配置
        self.ax2 = self.ax.twinx()
        self.ax2.set_ylabel('Throughput (Mbps)', 
                        color='#2ca02c', 
                        fontsize=10,
                        fontproperties=self.font)
        
        # 添加图例
        self.ax.plot([], [], 'o', c='#FF6F61', label='AP1')
        self.ax.plot([], [], 'X', c='#6B5B95', label='AP2')
        self.ax.legend(loc='upper left', prop=self.font)

    def _update_display(self, attempt):
        """实时可视化更新"""
        self.ax.cla()
        self.ax2.cla()
        
        # 绘制信道分布
        for ap in ['AP1', 'AP2']:
            data = [(i, ch) for i, chs in enumerate(self.channel_history[ap]) for ch in chs]
            if data:
                x, y = zip(*data)
                self.ax.scatter(
                    x, y, 
                    c='#FF6F61' if ap == 'AP1' else '#6B5B95',
                    marker='o' if ap == 'AP1' else 'X',
                    s=80, 
                    alpha=0.5,
                    label=ap
                )
        
        # 绘制吞吐量曲线
        steps = range(len(self.channel_history["throughput"]))
        self.ax2.plot(
            steps, self.channel_history["throughput"], 
            color='#2ca02c', 
            linestyle='--',
            marker='o',
            markersize=5,
            linewidth=1.5,
            alpha=0.8
        )
        
        # 标注最大吞吐量
        max_tp = max(self.channel_history["throughput"])
        if max_tp > 0:
            max_idx = self.channel_history["throughput"].index(max_tp)
            self.ax2.annotate(
                f'峰值: {max_tp}', 
                xy=(max_idx, max_tp),
                xytext=(max_idx+2, max_tp*0.8),
                arrowprops=dict(facecolor='black', arrowstyle='->'),
                fontsize=8
            )
        
        # 动态布局
        self.ax.set_xlim(-1, attempt+1)
        self.ax2.set_ylim(0, max(self.channel_history["throughput"] + [5]) * 1.2)
        self.ax.legend(loc='upper left', prop=self.font)
        plt.pause(0.1)

    def run(self):
        """持续运行模式"""
        print("🚀 启动动态信道协调系统（持续运行模式）")
        attempt = 1
        
        while True:  # 无限循环
            try:
                print(f"\n=== 第 {attempt} 轮协调 ===")
                ap1_chs, ap2_chs = self._negotiate_round(attempt)
                final_ap2 = self._resolve_conflict(ap1_chs, ap2_chs)
                
                self._record_history(ap1_chs, final_ap2)
                self._update_display(attempt)
                
                # 降低刷新频率
                time.sleep(1)  
                attempt += 1
                
            except KeyboardInterrupt:
                print("\n🔴 用户主动终止运行")
                break
            except Exception as e:
                logging.warning(f"运行时异常，继续执行: {str(e)}")
                time.sleep(3)  # 错误冷却时间
                continue
        
        # 生成报告
        plt.ioff()
        plt.show()
        self._generate_report()

    def _record_history(self, ap1_chs, ap2_chs):
        """记录历史数据"""
        self.channel_history["AP1"].append(ap1_chs)
        self.channel_history["AP2"].append(ap2_chs)
        
        # 计算吞吐量
        valid_ap1 = len(ap1_chs) * self.traffic_demand["AP1"]
        valid_ap2 = len(ap2_chs) * self.traffic_demand["AP2"]
        conflict = len(set(ap1_chs) & set(ap2_chs))
        self.channel_history["throughput"].append(valid_ap1 + valid_ap2 - conflict*2)
        
        # 记录冲突
        if conflict > 0:
            self.channel_history["conflicts"] += conflict
            print(f"! 检测到{conflict}处信道冲突")

    def _check_convergence(self, attempt, ap1_chs, ap2_chs):
        """检查收敛条件"""
        conflict = len(set(ap1_chs) & set(ap2_chs))
        if conflict == 0:
            if hasattr(self, '_last_success'):
                self._last_success += 1
                if self._last_success >= CONVERGENCE_THRESHOLD:
                    print(f"✅ 连续{CONVERGENCE_THRESHOLD}轮无冲突，系统收敛！")
                    return True
            else:
                self._last_success = 1
        else:
            self._last_success = 0
        return False

    def _generate_report(self):
        """生成分析报告"""
        print("\n" + "="*40)
        print("系统运行分析报告".center(40))
        print("="*40)
        print(f"总运行轮次: {len(self.channel_history['AP1'])}")
        print(f"总冲突次数: {self.channel_history['conflicts']}")
        print(f"平均吞吐量: {sum(self.channel_history['throughput'])/len(self.channel_history['throughput'])}")

def main():
    # 初始化协调器
    coordinator = DynamicChannelCoordinator()
    
    try:
        # 启动协调系统
        coordinator.run()
    except KeyboardInterrupt:
        print("\n 用户中断操作")
    finally:
        # 确保可视化窗口保持
        if plt.get_fignums():
            plt.show(block=True)

if __name__ == "__main__":
    main()