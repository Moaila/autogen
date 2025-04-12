"""
TDMA动态多时隙协调系统V2
@author: 李文皓
@功能：初步增加了VIP任务，但是只完成一次任务
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
from collections import deque, defaultdict
import matplotlib
matplotlib.use('TkAgg')
from matplotlib import pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False 
from autogen import ConversableAgent, config_list_from_json

# ---------- 系统配置 ----------
logging.basicConfig(level=logging.ERROR)
for logger in ['autogen', 'matplotlib']:
    logging.getLogger(logger).setLevel(logging.CRITICAL)

MAX_ATTEMPTS = 50
VIP_COLOR = '#FF4500'
NORMAL_COLOR = '#1E90FF'
CONFLICT_COLOR = '#DC143C'

class TransmissionTask:
    """传输任务类"""
    def __init__(self, priority, size):
        self.priority = priority  # 0:VIP 1:普通
        self.size = size
        self.remaining = size
        self.allocated = []
    
    def __repr__(self):
        return f"[{'VIP':<4}|{self.remaining}/{self.size:^5}]"

class EnhancedChannelPool:
    """时隙资源池"""
    def __init__(self, num_channels):
        self.num_channels = num_channels
        self.available = list(range(num_channels))
        self.vip_queue = deque()
        self.normal_queue = deque()
        self.carry_over = []
        self.conflict_history = defaultdict(int)
        self.usage_records = defaultdict(int)

    def add_task(self, task):
        """任务入队"""
        if task.priority == 0:
            self.vip_queue.append(task)
        else:
            self.normal_queue.append(task)

    def prepare_allocation(self):
        """准备分配队列"""
        candidates = list(self.carry_over)
        self.carry_over = []
        
        while len(candidates) < self.num_channels and self.vip_queue:
            candidates.append(self.vip_queue.popleft())
        while len(candidates) < self.num_channels and self.normal_queue:
            candidates.append(self.normal_queue.popleft())
        return candidates

    def allocate(self, requests):
        """执行分配"""
        allocation = defaultdict(list)
        used_slots = set()
        conflict_slots = set()

        # VIP分配
        for req in sorted(requests, key=lambda x: (-x['vip_need'], x['ap'])):
            selected = []
            for ch in req['vip_slots']:
                if ch in self.available and ch not in used_slots:
                    selected.append(ch)
                    if len(selected) == req['vip_need']:
                        break
            allocation[req['ap']].extend(selected)
            used_slots.update(selected)
        
        # 普通分配
        remaining = sorted(set(self.available) - used_slots)
        for req in requests:
            need = req['normal_need']
            selected = remaining[:need]
            allocation[req['ap']].extend(selected)
            remaining = remaining[need:]
            used_slots.update(selected)

        # 冲突检测
        for ap1 in allocation:
            for ap2 in allocation:
                if ap1 != ap2:
                    common = set(allocation[ap1]) & set(allocation[ap2])
                    conflict_slots.update(common)
                    for ch in common:
                        self.conflict_history[ch] += 1
        
        # 更新记录
        for ch in used_slots:
            self.usage_records[ch] += 1
            
        return allocation, conflict_slots

class RealTimeVisualizer:
    """可视化模块"""
    def __init__(self, num_aps, num_channels):
        plt.ion()
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(16, 6))
        self.num_aps = num_aps
        self.num_channels = num_channels
        self._init_views()
    
    def _init_views(self):
        """初始化视图"""
        self.ax1.set_title(f'时隙分配（AP数量：{self.num_aps}）')
        self.ax1.set_xlim(-0.5, self.num_channels-0.5)
        self.ax1.set_ylim(-0.5, self.num_aps-0.5)
        self.ax1.set_xticks(range(self.num_channels))
        self.ax1.set_yticks(range(self.num_aps))
        self.ax1.set_yticklabels([f"AP{i+1}" for i in range(self.num_aps)])
        self.ax1.grid(True)
        
        self.ax2.set_title('任务队列状态')
        self.ax2.set_xticks([0, 1])
        self.ax2.set_xticklabels(['VIP队列', '普通队列'])
        self.ax2.set_ylabel('待处理任务数')

    def update(self, coordinator):
        """更新视图"""
        self.ax1.cla()
        self.ax2.cla()
        self._init_views()
        
        # 绘制时隙分配
        for ap_idx in range(self.num_aps):
            ap_name = f"AP{ap_idx+1}"
            for task in coordinator.tasks[ap_name]:
                for ch in task.allocated:
                    color = VIP_COLOR if task.priority == 0 else NORMAL_COLOR
                    self.ax1.add_patch(
                        plt.Rectangle(
                            (ch-0.4, ap_idx-0.4), 0.8, 0.8,
                            facecolor=color, edgecolor='black', alpha=0.7
                        )
                    )
                    
        # 标记冲突
        for ch in coordinator.conflict_slots:
            self.ax1.axvline(x=ch, color=CONFLICT_COLOR, linestyle=':', linewidth=2)
        
        # 队列状态
        vip_count = len(coordinator.channel_pool.vip_queue)
        normal_count = len(coordinator.channel_pool.normal_queue)
        self.ax2.bar([0, 1], [vip_count, normal_count], 
                    color=[VIP_COLOR, NORMAL_COLOR], alpha=0.7)
        
        plt.draw()
        plt.pause(0.5)

class FeedbackCoordinator:
    """核心协调器"""
    def __init__(self, num_aps, num_channels, config_list):
        # 关键修复：先初始化基础属性
        self.num_aps = num_aps
        self.num_channels = num_channels
        self.used_slots = set()  # 提前初始化
        self.conflict_slots = set()
        self.round_count = 0
        
        # 初始化其他组件
        self.channel_pool = EnhancedChannelPool(num_channels)
        self.tasks = self._init_tasks()
        self.visualizer = RealTimeVisualizer(num_aps, num_channels)
        self.agents = self._init_agents(config_list)

    def _init_tasks(self):
        """任务初始化"""
        tasks = defaultdict(list)
        for ap_id in range(self.num_aps):
            ap_name = f"AP{ap_id+1}"
            
            # VIP任务
            for _ in range(random.randint(0, 8)):
                task = TransmissionTask(0, random.randint(1, 4))
                tasks[ap_name].append(task)
                self.channel_pool.add_task(task)
            
            # 普通任务
            for _ in range(random.randint(3, 9)):
                task = TransmissionTask(1, random.randint(2, 6))
                tasks[ap_name].append(task)
                self.channel_pool.add_task(task)
        
        return tasks

    def _init_agents(self, config_list):
        """智能体初始化"""
        agents = {}
        for i in range(self.num_aps):
            ap_name = f"AP{i+1}"
            agents[ap_name] = ConversableAgent(
                name=f"{ap_name}_Controller",
                system_message=self._build_prompt(ap_name),
                llm_config={"config_list": [config_list[i % len(config_list)]]}
            )
        return agents

    def _build_prompt(self, agent):
        """提示生成"""
        remaining_slots = sorted(list(set(range(self.num_channels)) - self.used_slots))
        vip_need = sum(t.remaining for t in self.tasks[agent] if t.priority == 0)
        normal_need = sum(t.remaining for t in self.tasks[agent] if t.priority == 1)
        
        return f"""作为{agent}的控制器，请遵循：

■ 系统参数：
- 总时隙：{self.num_channels}（0-{self.num_channels-1}）
- 可用时隙：{remaining_slots}
- VIP需求：{vip_need} 普通需求：{normal_need}

■ 分配策略：
1. 优先分配低冲突时隙（冲突历史：{dict(self.channel_pool.conflict_history)}）
2. VIP任务需优先分配（如[0,1,2]）
3. 尽量提高时隙利用率
4. 普通任务使用剩余时隙
5. 不得重复分配时隙

■ 响应格式：
{{"vip_slots": [时隙列表], "normal_slots": [时隙列表]}}
"""
    def _process_response(self, response, ap_name):
        """增强版响应解析方法"""
        try:
            # 确保处理消息字典格式
            if isinstance(response, dict):
                content = response.get('content', '')
            else:
                content = str(response)

            # 使用正则表达式提取JSON内容
            json_str = re.search(r'\{[\s\S]*\}', content).group()
            
            # 转换为字典并验证字段
            data = json.loads(json_str)
            if not all(k in data for k in ("vip_slots", "normal_slots")):
                raise ValueError("缺少必要字段")
            
            return {
                'vip_slots': list(map(int, data['vip_slots'])),
                'normal_slots': list(map(int, data['normal_slots']))
            }
        except Exception as e:
            print(f"{ap_name} 响应解析异常，使用备用策略: {str(e)}")
            return {'vip_slots': [], 'normal_slots': []}

    def _negotiation_round(self):
        """协商回合"""
        requests = []
        for ap_name in self.agents:
            response = self.agents[ap_name].generate_reply(messages=[{
                "role": "user",
                "content": "请提交时隙分配请求"
            }])
            alloc = self._process_response(response, ap_name)
            requests.append({
                'ap': ap_name,
                'vip_slots': alloc['vip_slots'],
                'vip_need': sum(1 for t in self.tasks[ap_name] if t.priority == 0 and t.remaining > 0),
                'normal_slots': alloc['normal_slots'],
                'normal_need': sum(1 for t in self.tasks[ap_name] if t.priority == 1 and t.remaining > 0)
            })
        
        allocation, self.conflict_slots = self.channel_pool.allocate(requests)
        self.used_slots = set().union(*allocation.values())
        return allocation

    def _update_tasks(self, allocation):
        """更新任务状态"""
        for ap_name in allocation:
            # VIP分配
            vip_slots = allocation[ap_name][:sum(1 for t in self.tasks[ap_name] if t.priority == 0)]
            for task in (t for t in self.tasks[ap_name] if t.priority == 0):
                if task.remaining > 0 and vip_slots:
                    allocate_num = min(task.remaining, len(vip_slots))
                    task.allocated.extend(vip_slots[:allocate_num])
                    task.remaining -= allocate_num
                    vip_slots = vip_slots[allocate_num:]
            
            # 普通分配
            normal_slots = allocation[ap_name][len(vip_slots):]
            for task in (t for t in self.tasks[ap_name] if t.priority == 1):
                if task.remaining > 0 and normal_slots:
                    allocate_num = min(task.remaining, len(normal_slots))
                    task.allocated.extend(normal_slots[:allocate_num])
                    task.remaining -= allocate_num
                    normal_slots = normal_slots[allocate_num:]

    def run(self):
        """主运行循环"""
        print(f"\n【系统启动】AP数量：{self.num_aps} 总时隙：{self.num_channels}")
        print("初始任务分布：")
        for ap in self.tasks:
            print(f"{ap}: VIP×{sum(1 for t in self.tasks[ap] if t.priority==0)} "
                  f"普通×{sum(1 for t in self.tasks[ap] if t.priority==1)}")

        try:
            while self.round_count < MAX_ATTEMPTS:
                self.round_count += 1
                print(f"\n=== 第 {self.round_count} 轮分配 ===")
                
                allocation = self._negotiation_round()
                self._update_tasks(allocation)
                self.visualizer.update(self)
                
                # 显示结果
                for ap in allocation:
                    print(f"{ap}: VIP→{allocation[ap]} | 剩余VIP需求："
                          f"{sum(t.remaining for t in self.tasks[ap] if t.priority==0)}")
                
                if self._check_completion():
                    print("\n【成功】所有VIP任务已完成！")
                    break
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n用户终止运行")
        finally:
            plt.ioff()
            plt.show()

    def _check_completion(self):
        """完成检测"""
        return all(
            t.remaining == 0 
            for ap in self.tasks.values() 
            for t in ap if t.priority == 0
        )

def get_runtime_params(config_count):
    """参数获取"""
    print(" TDMA协调系统初始化 ".center(40, '='))
    while True:
        try:
            num_aps = int(input(f"AP数量 (1-{config_count}): "))
            if 1 <= num_aps <= config_count:
                break
            print(f"请输入1-{config_count}之间的数字")
        except:
            print("输入无效，请重试")
    
    while True:
        try:
            num_channels = int(input("总时隙数（≥5）: "))
            if num_channels >=5:
                break
            print("时隙数不能小于5")
        except:
            print("输入无效，请重试")
    
    return num_aps, num_channels

if __name__ == "__main__":
    with open("OAI_CONFIG_LIST.json") as f:
        configs = json.load(f)
    
    num_aps, num_channels = get_runtime_params(len(configs))
    coordinator = FeedbackCoordinator(num_aps, num_channels, configs)
    
    try:
        coordinator.run()
    except Exception as e:
        print(f"系统异常: {str(e)}")
    finally:
        plt.close()