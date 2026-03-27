import os
import yaml
from pathlib import Path

def load_config(config_path="config.yaml"):
    """加载配置文件"""
    if Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def get_env_or_default(key, default=None):
    """获取环境变量或默认值"""
    return os.getenv(key, default)

def ensure_dir(path):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)