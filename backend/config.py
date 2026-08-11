"""
配置模块 - LLM API配置与系统设置
支持OpenAI兼容API（OpenAI/Azure/Qwen/DeepSeek等）
"""
import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "llm": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 2000,
        "enabled": False
    },
    "system": {
        "company": "上海绘兰材料科技有限公司",
        "product_focus": "光学膜UV固化胶",
        "data_dir": os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    }
}


class Config:
    """系统配置管理"""

    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # 深度合并
                for key in saved:
                    if key in self.config and isinstance(self.config[key], dict) and isinstance(saved[key], dict):
                        self.config[key].update(saved[key])
                    else:
                        self.config[key] = saved[key]
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get_llm_config(self):
        return self.config.get("llm", {})

    def set_llm_config(self, api_key="", base_url="", model="", enabled=None):
        if api_key:
            self.config["llm"]["api_key"] = api_key
        if base_url:
            self.config["llm"]["base_url"] = base_url
        if model:
            self.config["llm"]["model"] = model
        if enabled is not None:
            self.config["llm"]["enabled"] = enabled
        self.save()

    def is_llm_enabled(self):
        llm = self.config.get("llm", {})
        return llm.get("enabled", False) and bool(llm.get("api_key", ""))

    def get(self, key, default=None):
        return self.config.get(key, default)


config = Config()
