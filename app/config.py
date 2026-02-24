"""
Application configuration loaded from config.json.
"""

import os
from dataclasses import dataclass

from .constants import (CONFIG_DIR_NAME, CONFIG_FILENAME,
                        DEFAULT_AUTO_REFRESH_INTERVAL,
                        DEFAULT_CALLBACK_HOST, DEFAULT_CALLBACK_PATH,
                        DEFAULT_CALLBACK_PORT, DEFAULT_REQUEST_TOKEN_TIMEOUT,
                        DEFAULT_UI_HOST, DEFAULT_UI_PORT,
                        SESSION_CACHE_FILENAME)
from .utils import load_config


@dataclass
class AppConfig:
    """Application configuration loaded from config.json."""
    accounts: list
    callback_host: str
    callback_port: int
    callback_path: str
    redirect_url: str
    ui_host: str
    ui_port: int
    request_token_timeout: int
    auto_refresh_interval: int
    auto_refresh_outside_market_hours: bool
    session_cache_file: str
    features: dict

    @classmethod
    def from_file(cls, config_path: str) -> 'AppConfig':
        """Load and parse application configuration from config.json."""
        config = load_config(config_path)

        server = config.get("server", {})
        timeouts = config.get("timeouts", {})
        features = config.get("features", {})

        callback_host = server.get("callback_host", DEFAULT_CALLBACK_HOST)
        callback_port = server.get("callback_port", DEFAULT_CALLBACK_PORT)
        callback_path = server.get("callback_path", DEFAULT_CALLBACK_PATH)

        base_dir = os.path.dirname(config_path)

        return cls(
            accounts=config.get("accounts", []),
            callback_host=callback_host,
            callback_port=callback_port,
            callback_path=callback_path,
            redirect_url=f"http://{callback_host}:{callback_port}{callback_path}",
            ui_host=server.get("ui_host", DEFAULT_UI_HOST),
            ui_port=server.get("ui_port", DEFAULT_UI_PORT),
            request_token_timeout=timeouts.get("request_token_timeout_seconds", DEFAULT_REQUEST_TOKEN_TIMEOUT),
            auto_refresh_interval=timeouts.get("auto_refresh_interval_seconds", DEFAULT_AUTO_REFRESH_INTERVAL),
            auto_refresh_outside_market_hours=features.get("auto_refresh_outside_market_hours", False),
            session_cache_file=os.path.join(base_dir, SESSION_CACHE_FILENAME),
            features=features,
        )


# Module-level singleton
_project_root = os.path.dirname(os.path.dirname(__file__))
app_config = AppConfig.from_file(os.path.join(_project_root, CONFIG_DIR_NAME, CONFIG_FILENAME))
