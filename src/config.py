"""配置加载模块."""

from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


class AppConfig:
    """应用配置管理类."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self._config_path = config_path
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """从 YAML 文件加载配置."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self._config_path}")
        with self._config_path.open("r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

    def save(self) -> None:
        """保存配置到 YAML 文件."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, allow_unicode=True, sort_keys=False)

    def get(self, key: str, default: Any = None) -> Any:
        """使用点号分隔的键获取配置值，例如 'capture.interval_ms'."""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """使用点号分隔的键设置配置值."""
        keys = key.split(".")
        target = self._data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    @property
    def raw(self) -> Dict[str, Any]:
        """返回原始配置字典."""
        return self._data


# 全局配置实例
config = AppConfig()
