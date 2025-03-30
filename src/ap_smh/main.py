import ap_tdma.tdma_v4_1 as tdma
import ap_assess.ap_assess as assess
if __name__ == '__main__':
    tdma.MAX_ATTEMPTS = 10
    coordinator = tdma.FeedbackCoordinator()
    coordinator.run()
    print(f"run {tdma.MAX_ATTEMPTS} times over")
