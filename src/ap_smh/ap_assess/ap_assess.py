import matplotlib.pyplot as plt
import json

ASSESS_FILE = './records/assess-2025-03-30-17-45-26.json' 

class assess_module:
    def __init__(self):
        self.assess_contents_list = []
        self.rounds = []
    
    #* read records
    def load_assess_contents(self):
        with open(ASSESS_FILE, 'r') as f:
            self.assess_contents_list = json.load(f)
    
    #* plot utilization rate
    def plot_utilization_rate(self):
        plt.plot([item['utilization rate'] for item in self.assess_contents_list])
        plt.title('Utilization Rate')
        plt.xlabel('rounds')
        plt.ylabel('Utilization Rate')
        plt.grid(linestyle='--')
        #plt.ylim(0,1)
        plt.show()
    
    #* plot ap1 and ap2 slots
    def plot_ap1_and_ap2_slots(self):
        self.rounds = [i for i in range(len(self.assess_contents_list))]
        ap1_slots = [item['AP1 time slots'] for item in self.assess_contents_list]
        ap2_slots = [item['AP2 time slots'] for item in self.assess_contents_list]
        
        for i in self.rounds:
            for j in ap1_slots[i]:
                plt.plot(i, j, 'ro', markersize=3)
            for j in ap2_slots[i]:
                plt.plot(i, j, 'bo', markersize=3)
        
        plt.title('AP1 and AP2Slots')
        plt.xlabel('rounds')
        plt.ylabel('Time Slots')
        plt.show()
    
    #* plot idle slots
    def plot_idle_slots(self):
        idle_slots = [item['idle slots'] for item in self.assess_contents_list]
        for i in self.rounds:
            for j in idle_slots[i]:
                plt.plot(i, j, 'go', markersize=3)
        
        plt.title('Idle Slots')
        plt.xlabel('rounds')
        plt.ylabel('Time Slots')
        plt.show()
        
    #* run
    def run(self):
        self.load_assess_contents()
        self.plot_utilization_rate()
        self.plot_ap1_and_ap2_slots()
        self.plot_idle_slots()

if __name__ == '__main__':
    assess_module().run()