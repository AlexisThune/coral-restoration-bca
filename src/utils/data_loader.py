class DataLoader:
    def __init__(self, data_path):
        self.data_path = data_path

    def load_data(self):
        print(f"Chargement des données depuis {self.data_path}...")
