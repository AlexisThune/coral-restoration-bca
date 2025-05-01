class BenefitModel:
    def __init__(self):
        pass

    def calculate_benefits(self, data, config):
        benefits = {}
        benefits["total_benefit"] = (
            sum(data["benefit_values"]) * config["benefit_factor"]
        )
        return benefits
