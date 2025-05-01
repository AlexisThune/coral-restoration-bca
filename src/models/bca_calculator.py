class BCACalculator:
    def __init__(self):
        pass

    def calculate_bca(self, costs, benefits):
        """
        Calculate the Benefit-Cost Ratio (BCR) and Net Present Value (NPV) for the given costs and benefits.

        Parameters:
        - costs: A list of costs associated with the project.
        - benefits: A list of benefits associated with the project.

        Returns:
        - bcr: The Benefit-Cost Ratio.
        - npv: The Net Present Value.
        """
        total_costs = sum(costs)
        total_benefits = sum(benefits)

        if total_costs == 0:
            raise ValueError("Total costs cannot be zero.")

        bcr = total_benefits / total_costs
        npv = total_benefits - total_costs

        return bcr, npv
