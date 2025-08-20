import json


def load_config(config_path):
    with open(config_path, "r") as f:
        return json.load(f)


def save_config(config_path, session_state, selected_keys=["crs"]):
    run_config = {
        "Run parameters": {
            key: session_state[key] for key in selected_keys if key in session_state
        }
    }

    with open(config_path, "w") as f:
        json.dump(run_config, f, indent=2)
