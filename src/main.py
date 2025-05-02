from config import load_config
from data_preprocessing import DataPreprocessor
from models.cost_model import CostModel
from models.benefit_model import BenefitModel
from models.bca_calculator import BCACalculator
from utils.plotter import Plotter
from utils.evaluator import Evaluator
from utils.data_loader import DataLoader


class CoralRestorationBCA:
    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.data_loader = DataLoader(self.config["data_path"])
        self.data_preprocessor = DataPreprocessor()
        self.cost_model = CostModel()
        self.benefit_model = BenefitModel()
        self.bca_calculator = BCACalculator()
        self.plotter = Plotter()
        self.evaluator = Evaluator()

    def run(self):
        # Load and process data
        data = self.data_loader.load_data()
        processed_data = self.data_preprocessor.preprocess_data(data)

        # Compute costs and benefits
        costs = self.cost_model.calculate_costs(processed_data, self.config)
        benefits = self.benefit_model.calculate_benefits(processed_data, self.config)

        # Compute BCA
        bca_results = self.bca_calculator.calculate_bca(
            costs, benefits, self.config["discount_rate"], self.config["years"]
        )

        # Evaluate the model
        evaluation_results = self.evaluator.evaluate_model(bca_results)

        # Visualize the results
        self.plotter.plot_results(bca_results)

        # Save the results
        self.save_results(bca_results)

    def save_results(self, results):
        with open(self.config["output_path"], "w") as f:
            f.write(results)
        print(f"Results saved in {self.config['output_path']}.")


if __name__ == "__main__":
    config_path = "config.json"
    bca = CoralRestorationBCA(config_path)
    bca.run()
