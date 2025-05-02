class BCACalculator:
    def __init__(self):
        pass

    def calculate_bca(self, costs, benefits, discount_rate, years):
        """
        Calculate the Benefit-Cost Ratio (BCR) and the Net Present Value (NPV) for the given costs and benefits.

        Parameters:
        - costs: Array of the annual costs associated with the project at year i + 1.
        - benefits: Array of the annual benefits associated with the project at year i + 1.

        Returns:
        - bcr: The Benefit-Cost Ratio.
        - npv: The Net Present Value.
        """
        selected_costs = costs[:years]
        selected_benefits = benefits[:years]

        discounted_costs = [
            cost * ((1 + discount_rate) ** -year)
            for year, cost in enumerate(selected_costs)
        ]
        discounted_benefits = [
            benefit * ((1 + discount_rate) ** -year)
            for year, benefit in enumerate(selected_benefits)
        ]

        total_costs = float(sum(discounted_costs))
        total_benefits = float(sum(discounted_benefits))

        bcr = total_benefits / total_costs
        npv = total_benefits - total_costs

        return bcr, npv
