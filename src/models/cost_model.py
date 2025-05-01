class CostModel:
    def __init__(self):
        pass

    def calculate_costs(self, data, config):
        costs = {}
        costs["total_cost"] = sum(data["costs"]) * config["cost_factor"]
        return costs
