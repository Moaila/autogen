import matplotlib.pyplot as plt
import json

ASSESS_FILE = './records/assess-2025-03-29-22-40-45.json' 

if __name__ == '__main__':
    with open(ASSESS_FILE, 'r') as f:
        assess_contents_list = json.load(f)
        plt.plot([item['utilization rate'] for item in assess_contents_list])
        plt.show()        
        # json.dump(assess, f, indent=2)
        # print(f"\n成功保存{len(assess)}条反馈记录到{ASSESS_FILE}")