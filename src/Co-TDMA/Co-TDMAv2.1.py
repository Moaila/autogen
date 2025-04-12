"""
TDMA动态多时隙协调系统V2.1
@author: 李文皓
@功能：支持动态时隙重分配和任务循环
"""
import json
import random
import time
import re
import logging
from collections import defaultdict, deque
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

MAX_ROUNDS = 50
VIP_COLOR = '#FF4500'
NORMAL_COLOR = '#1E90FF'
CONFLICT_COLOR = '#DC143C'

class TransmissionTask:
    """增强型传输任务类"""
    TASK_ID = 0
    def __init__(self, priority, size, gen_round):
        self.task_id = TransmissionTask.TASK_ID
        TransmissionTask.TASK_ID += 1
        self.priority = priority  # 0:VIP 1:普通
        self.size = size
        self.remaining = size
        self.allocated = []
        self.gen_round = gen_round
    
    def __repr__(self):
        return f"[T{self.task_id}:{'VIP' if self.priority==0 else '普通'}|{self.remaining}/{self.size}]"

class DynamicSlotAllocator:
    """动态时隙分配器"""
    def __init__(self, num_channels, ap_list):
        self.base_channels = num_channels
        self.active_alloc = {ap: 0 for ap in ap_list}
        self.free_pool = set(range(num_channels))
        self.locked_slots = defaultdict(set)
    
    def initial_allocation(self, task_reports):
        """基于任务负载的初始分配"""
        total_weight = sum(r['weight'] for r in task_reports.values())
        allocated = {}
        
        # 基础分配
        for ap, report in task_reports.items():
            ratio = report['weight'] / total_weight
            alloc = round(self.base_channels * ratio)
            allocated[ap] = min(alloc, self.base_channels)
        
        # 冲突解决分配
        while sum(allocated.values()) > self.base_channels:
            max_ap = max(allocated, key=lambda x: allocated[x])
            allocated[max_ap] -= 1
        
        # 应用分配
        self.active_alloc = allocated
        self._update_free_pool()
    
    def redistribute(self, completed_aps):
        """时隙再分配"""
        released = []
        for ap in completed_aps:
            released.extend(self.locked_slots[ap])
            del self.locked_slots[ap]
        
        # 将释放的时隙加入空闲池
        self.free_pool.update(released)
        self._update_free_pool()
    
    def _update_free_pool(self):
        """更新空闲时隙池"""
        used = set().union(*self.locked_slots.values())
        self.free_pool = set(range(self.base_channels)) - used
    
    def allocate_slots(self, ap, request_slots):
        """执行实际分配"""
        available = list(self.free_pool & set(request_slots))
        allocate_num = min(len(available), self.active_alloc[ap])
        
        allocated = random.sample(available, allocate_num) if available else []
        self.locked_slots[ap].update(allocated)
        self._update_free_pool()
        return allocated

class EnhancedVisualizer:
    """增强可视化模块"""
    def __init__(self, num_aps, num_channels):
        plt.ion()
        self.fig, (self.ax1, self.ax2, self.ax3) = plt.subplots(1, 3, figsize=(20, 6))
        self.num_aps = num_aps
        self.num_channels = num_channels
        self._init_views()
    
    def _init_views(self):
        """初始化视图"""
        # 时隙分配视图
        self.ax1.clear()
        self.ax1.set_title(f'时隙分配（总时隙：{self.num_channels}）')
        self.ax1.set_xlim(-0.5, self.num_channels-0.5)
        self.ax1.set_ylim(-0.5, self.num_aps-0.5)
        self.ax1.set_xticks(range(self.num_channels))
        self.ax1.set_yticks(range(self.num_aps))
        self.ax1.set_yticklabels([f"AP{i+1}" for i in range(self.num_aps)])
        self.ax1.grid(True)
        
        # 任务队列视图
        self.ax2.clear()
        self.ax2.set_title('任务队列状态')
        self.ax2.set_xticks([0, 1])
        self.ax2.set_xticklabels(['VIP队列', '普通队列'])
        self.ax2.set_ylabel('任务数')
        
        # 资源分配视图
        self.ax3.clear()
        self.ax3.set_title('动态资源分配')
        self.ax3.set_xlabel('分配时隙数')
        self.ax3.set_ylabel('AP节点')

    def update(self, coordinator):
        """实时更新视图"""
        self._init_views()
        
        # 绘制时隙分配
        for ap_idx, ap in enumerate(coordinator.allocator.locked_slots):
            for ch in coordinator.allocator.locked_slots[ap]:
                color = VIP_COLOR if 'VIP' in str(coordinator.tasks[ap]) else NORMAL_COLOR
                self.ax1.add_patch(
                    plt.Rectangle(
                        (ch-0.4, ap_idx-0.4), 0.8, 0.8,
                        facecolor=color, edgecolor='black', alpha=0.7
                    )
                )
        
        # 队列状态
        vip_counts = [len([t for t in tasks if t.priority==0]) 
                     for tasks in coordinator.tasks.values()]
        normal_counts = [len([t for t in tasks if t.priority==1]) 
                        for tasks in coordinator.tasks.values()]
        self.ax2.bar(range(len(vip_counts)), vip_counts, color=VIP_COLOR, alpha=0.6, label='VIP')
        self.ax2.bar(range(len(normal_counts)), normal_counts, bottom=vip_counts, 
                    color=NORMAL_COLOR, alpha=0.6, label='普通')
        
        # 资源分配
        alloc_data = [(ap, coordinator.allocator.active_alloc[ap]) 
                     for ap in coordinator.agents]
        self.ax3.barh([d[0] for d in alloc_data], [d[1] for d in alloc_data], 
                     color='#2E8B57', alpha=0.7)
        
        plt.draw()
        plt.pause(0.3)

class TDMA_Coordinator:
    """增强型协调器"""
    def __init__(self, num_aps, num_channels, configs):
        self.num_aps = num_aps
        self.num_channels = num_channels
        self.round_count = 0
        self.cycle_count = 0
        
        # 初始化组件
        # self.agents = self._init_agents(configs)
        self._reset_tasks()
        self.agents = self._init_agents(configs)
        self.allocator = DynamicSlotAllocator(num_channels, list(self.agents.keys()))
        self.visualizer = EnhancedVisualizer(num_aps, num_channels)
    
    def _init_agents(self, configs):
        """初始化智能体"""
        agents = {}
        for i in range(self.num_aps):
            ap_name = f"AP{i+1}"
            agents[ap_name] = ConversableAgent(
                name=f"{ap_name}_Controller",
                system_message=self._build_agent_prompt(ap_name),
                llm_config={"config_list": [configs[i % len(configs)]]}
            )
        return agents
    
    def _build_agent_prompt(self, ap_name):
        """构建智能体提示"""
        if ap_name not in self.tasks:
            return f"{ap_name} 暂无任务"
    
        vip_tasks = [t for t in self.tasks[ap_name] if t.priority == 0]
        normal_tasks = [t for t in self.tasks[ap_name] if t.priority == 1]
    
        return f"""作为{ap_name}的TDMA控制器，您需要：

1. 根据当前任务负载请求时隙资源
2. VIP任务优先保证
3. 合理评估所需时隙数量
4. 遵循协调器的分配方案

当前待处理任务：
{self._get_task_summary(ap_name)}

响应格式示例：
{{"vip_need": 3, "normal_need": 2, "preferred_slots": [1,3,5]}}
"""
    
    def _get_task_summary(self, ap_name):
        """生成任务摘要"""
        vip_tasks = [t for t in self.tasks[ap_name] if t.priority == 0]
        normal_tasks = [t for t in self.tasks[ap_name] if t.priority == 1]
        return (f"VIP任务: {len(vip_tasks)}个（剩余总量：{sum(t.remaining for t in vip_tasks)}）\n"
                f"普通任务: {len(normal_tasks)}个（剩余总量：{sum(t.remaining for t in normal_tasks)}）")
    
    def _reset_tasks(self):
        """重置任务系统"""
        self.tasks = defaultdict(list)
        ap_names = [f"AP{i+1}" for i in range(self.num_aps)]
    
        for ap in ap_names:
            # VIP任务
            for _ in range(random.randint(3,5)):
                self.tasks[ap].append(
                    TransmissionTask(0, random.randint(1,3), self.cycle_count)
                )
            # 普通任务
            for _ in range(random.randint(5,8)):
                self.tasks[ap].append(
                    TransmissionTask(1, random.randint(2,5), self.cycle_count)
                )
    
    def _collect_task_reports(self):
        """收集各AP任务报告"""
        reports = {}
        for ap in self.agents:
            vip_need = sum(t.remaining for t in self.tasks[ap] if t.priority == 0)
            normal_need = sum(t.remaining for t in self.tasks[ap] if t.priority == 1)
            reports[ap] = {
                'vip': vip_need,
                'normal': normal_need,
                'weight': vip_need * 2 + normal_need  # VIP权重系数
            }
        return reports
    
    def _get_agent_request(self, ap):
        """实现智能体请求生成"""
        try:
            response = self.agents[ap].generate_reply(messages=[{
                "role": "user",
                "content": "请根据当前任务提交时隙请求"
            }])
            return self._parse_request(response)
        except Exception as e:
            print(f"{ap} 请求生成失败: {str(e)}")
            return {"vip_need":0, "normal_need":0, "preferred_slots":[]}

    def _parse_request(self, response):
        """解析响应（新增容错机制）"""
        try:
            if isinstance(response, dict):
                content = response.get("content", "{}")
            else:
                content = str(response)
            
            # 使用正则提取JSON
            json_str = re.search(r'\{.*\}', content).group()
            return json.loads(json_str)
        except:
            return {"vip_need":0, "normal_need":0, "preferred_slots":[]}
    
    def _negotiation_phase(self):
        """协商阶段"""
        # 收集任务报告
        task_reports = self._collect_task_reports()
        
        # 初始分配
        self.allocator.initial_allocation(task_reports)
        print("\n【初始分配结果】")
        for ap in self.agents:
            print(f"{ap}: 分配时隙 {self.allocator.active_alloc[ap]}")
        
        # 多轮协商
        for _ in range(3):  # 最多三轮协商
            all_accepted = True
            for ap in self.agents:
                requested = self._get_agent_request(ap)
                allocated = self.allocator.allocate_slots(ap, requested['preferred_slots'])
                
                # 检查是否满足需求
                vip_coverage = len(allocated) >= requested['vip_need']
                if not vip_coverage:
                    print(f"{ap} 申请调整分配...")
                    all_accepted = False
            
            if all_accepted:
                print("全体AP接受分配方案")
                return True
            
            # 动态调整分配
            self._adjust_allocation()
        
        print("协商失败，使用强制分配方案")
        return False
    def _adjust_allocation(self):
        """动态调整分配方案"""
        # 增加10%的时隙给未满足需求的AP
        total_extra = int(self.num_channels * 0.1)
        for ap in self.allocator.active_alloc:
            if self._check_ap_need(ap) > self.allocator.active_alloc[ap]:
                self.allocator.active_alloc[ap] += 1
                total_extra -= 1
                if total_extra <=0:
                    break

    def _check_ap_need(self, ap):
        """计算AP实际需求"""
        vip_need = sum(t.remaining for t in self.tasks[ap] if t.priority==0)
        normal_need = sum(t.remaining for t in self.tasks[ap] if t.priority==1)
        return vip_need + normal_need
    
    def _execute_phase(self):
        """执行阶段"""
        print("\n【开始任务执行】")
        for _ in range(MAX_ROUNDS):
            self.round_count += 1
            completed_aps = []
            
            # 各AP执行传输
            for ap in self.agents:
                # 获取已分配的时隙
                allocated = self.allocator.locked_slots[ap]
                
                # 分配时隙给任务
                self._allocate_to_tasks(ap, allocated)
                
                # 检查是否完成
                if self._check_ap_completion(ap):
                    completed_aps.append(ap)
            
            # 重新分配已完成AP的时隙
            if completed_aps:
                print(f"完成AP: {completed_aps} 释放时隙")
                self.allocator.redistribute(completed_aps)
            
            # 更新可视化
            self.visualizer.update(self)
            
            # 检查全局完成
            if self._check_global_completion():
                print("\n所有任务完成！")
                return True
            
            time.sleep(1)
        
        print("\n达到最大轮次限制")
        return False
    
    def _allocate_to_tasks(self, ap, slots):
        """将时隙分配给具体任务"""
        vip_tasks = [t for t in self.tasks[ap] if t.priority == 0 and t.remaining > 0]
        normal_tasks = [t for t in self.tasks[ap] if t.priority == 1 and t.remaining > 0]
        
        # VIP任务优先分配
        for task in vip_tasks:
            if not slots: break
            allocate = min(task.remaining, len(slots))
            task.allocated.extend(slots[:allocate])
            task.remaining -= allocate
            slots = slots[allocate:]
        
        # 普通任务分配
        for task in normal_tasks:
            if not slots: break
            allocate = min(task.remaining, len(slots))
            task.allocated.extend(slots[:allocate])
            task.remaining -= allocate
            slots = slots[allocate:]
    
    def _check_ap_completion(self, ap):
        """检查单个AP是否完成"""
        return all(t.remaining == 0 for t in self.tasks[ap])
    
    def _check_global_completion(self):
        """检查全局完成状态"""
        return all(self._check_ap_completion(ap) for ap in self.agents)
    
    def run_cycle(self):
        """运行完整周期"""
        self.cycle_count += 1
        print(f"\n=== 任务周期 {self.cycle_count} ===")
        print("当前各AP任务负载:")
        for ap in self.agents:
            vip = sum(t.size for t in self.tasks[ap] if t.priority==0)
            normal = sum(t.size for t in self.tasks[ap] if t.priority==1)
            print(f"{ap}: VIP×{vip} 普通×{normal}")
        if self._negotiation_phase():
            success = self._execute_phase()
            if success:
                print("准备开始新任务周期...")
                self._reset_tasks()
                self.round_count = 0
                return True
        return False

def main():
    """主运行程序"""
    with open("OAI_CONFIG_LIST.json") as f:
        configs = json.load(f)
    
    num_aps = int(input("请输入AP数量: "))
    num_channels = int(input("请输入总时隙数: "))
    
    coordinator = TDMA_Coordinator(num_aps, num_channels, configs)
    
    try:
        while True:
            if not coordinator.run_cycle():
                break
            if input("是否继续下一个周期？(y/n)").lower() != 'y':
                break
    except KeyboardInterrupt:
        print("\n用户终止运行")
    finally:
        plt.ioff()
        plt.show()

if __name__ == "__main__":
    main()