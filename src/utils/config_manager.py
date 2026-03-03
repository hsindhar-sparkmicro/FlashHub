import json
import os

class ConfigManager:
    DEFAULT_CONFIG = {
        "projects": [
            {
                "name": "Default Project",
                "target_device": "stm32g0b0",
                "firmware_path": "",
                "probes": []
            }
        ],
        "current_project_index": 0
    }

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return self.DEFAULT_CONFIG

    def save_config(self, config=None):
        if config is not None:
            self.config = config
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_current_project(self):
        idx = self.config.get("current_project_index", 0)
        projects = self.config.get("projects", [])
        if 0 <= idx < len(projects):
            return projects[idx]
        return None

    def get_projects(self):
        return self.config.get("projects", [])

    def create_project(self, name, target="", firmware=""):
        new_project = {
            "name": name,
            "target_device": target,
            # "firmware_path": firmware, # Deprecated global firmware
            "probes_config": {} # Map unique_id -> {alias: "", firmware: ""}
        }
        self.config["projects"].append(new_project)
        self.config["current_project_index"] = len(self.config["projects"]) - 1
        self.save_config()
        return new_project

    def get_probe_config(self, probe_id):
        proj = self.get_current_project()
        if proj and "probes_config" in proj:
            return proj["probes_config"].get(probe_id, {})
        return {}

    def update_probe_config(self, probe_id, alias, firmware):
        proj = self.get_current_project()
        if proj:
            if "probes_config" not in proj:
                proj["probes_config"] = {}
            
            proj["probes_config"][probe_id] = {
                "alias": alias,
                "firmware": firmware
            }
            self.save_config()

    def update_current_project_probes_config(self, probes_config):
        proj = self.get_current_project()
        if proj is not None:
            proj["probes_config"] = probes_config or {}
            self.save_config()

    def delete_project(self, index):
        projects = self.config.get("projects", [])
        if 0 <= index < len(projects):
            projects.pop(index)
            # Adjust current index
            curr = self.config.get("current_project_index", 0)
            if index < curr:
                self.config["current_project_index"] = curr - 1
            elif index == curr:
                 self.config["current_project_index"] = 0 if projects else -1
                 
            # If we deleted everything, create default again
            if not projects:
                self.config["projects"] = [self.DEFAULT_CONFIG["projects"][0]]
                self.config["current_project_index"] = 0

            self.save_config()
            return True
        return False

    def select_project(self, index):
        if 0 <= index < len(self.config.get("projects", [])):
            self.config["current_project_index"] = index
            self.save_config()
            return self.get_current_project()
        return None

    def update_current_project(self, key, value):
        idx = self.config.get("current_project_index", 0)
        if 0 <= idx < len(self.config["projects"]):
            self.config["projects"][idx][key] = value
            self.save_config()

    def update_probe_firmware(self, probe_uid: str, firmware: str, project_name: str | None = None):
        """Update firmware path for a specific probe UID in the given (or active) project."""
        if project_name:
            proj = next((p for p in self.config.get("projects", []) if p["name"].lower() == project_name.lower()), None)
        else:
            proj = self.get_current_project()
        if proj is None:
            return False
        probes_config = proj.setdefault("probes_config", {})
        # Match UID case-insensitively
        matched_key = next((k for k in probes_config if k.upper() == probe_uid.upper()), None)
        if matched_key is None:
            return False
        probes_config[matched_key]["firmware"] = firmware
        self.save_config()
        return True
