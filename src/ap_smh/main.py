import ap_tdma.tdma_v4_1 as tdma

if __name__ == '__main__':
    coordinator = tdma.FeedbackCoordinator()
    coordinator.run()