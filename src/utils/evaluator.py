class Evaluator:
    def __init__(self, model, data):
        self.model = model
        self.data = data
        self.results = None

    def evaluate_model(self):
        self.results = self.model.predict(self.data)
        return self.results
