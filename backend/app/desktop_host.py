from __future__ import annotations

import logging
import queue
import threading
import traceback
import webbrowser
from pathlib import Path
from typing import Final

import customtkinter as ctk
import httpx
import uvicorn

from app.app import create_app
from app.core.certificates import (
    CERT_PATH,
    KEY_PATH,
    ensure_https_env,
    trust_certificate_for_current_user,
)
from app.core.config import BASE_DIR, settings
from app.core.env_manager import ensure_env_file, read_env_file, write_env_values
from app.core.runtime import get_resource_root

WINDOW_TITLE: Final[str] = "Ollie Desktop Host"
LOG_POLL_INTERVAL_MS: Final[int] = 250
HEALTH_CHECK_INTERVAL_MS: Final[int] = 2000
LOCALHOST_ALIASES: Final[set[str]] = {"127.0.0.1", "0.0.0.0", "::1", "[::1]"}
ENV_FIELDS: Final[list[dict[str, str | bool]]] = [
    {
        "key": "RAG_SERVICE_URL",
        "label": "RAG Backend URL",
        "hint": "Endpoint of the local or remote LLM/RAG service.",
    },
    {
        "key": "MODEL_API_BASE_URL",
        "label": "Model API Base URL",
        "hint": "Optional direct API endpoint for model providers.",
    },
    {
        "key": "MODEL_API_KEY",
        "label": "Model API Key",
        "hint": "Optional API key for remote model providers.",
        "secret": True,
    },
    {
        "key": "LLM_MODEL",
        "label": "Model Name",
        "hint": "Model identifier passed to the backend.",
    },
    {
        "key": "SERVER_HOST",
        "label": "Host Bind Address",
        "hint": "Local host address for the HTTPS app server.",
    },
    {
        "key": "SERVER_PORT",
        "label": "HTTPS Port",
        "hint": "Single shared port for frontend and API.",
    },
]


class QueueLogHandler(logging.Handler):
    def __init__(self, sink: queue.Queue[str]) -> None:
        super().__init__()
        self.sink = sink
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.put(self.format(record))


class OllieDesktopHost(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title(WINDOW_TITLE)
        self.geometry("1100x860")
        self.minsize(980, 760)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.server: uvicorn.Server | None = None
        self.server_thread: threading.Thread | None = None
        self.log_handler: QueueLogHandler | None = None
        self.file_log_handler: logging.Handler | None = None

        self.frontend_dist = get_resource_root() / "frontend" / "dist"
        self.env_path = BASE_DIR / ".env"
        self.log_path = BASE_DIR / "ollie.log"
        self.entries: dict[str, ctk.CTkEntry] = {}

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        ensure_env_file(self.env_path)
        self._build_layout()
        self._load_env_values()
        self._refresh_readiness()
        self._append_log("Desktop host initialized.")
        self.after(LOG_POLL_INTERVAL_MS, self._drain_log_queue)
        self.after(HEALTH_CHECK_INTERVAL_MS, self._poll_runtime_status)

    def _normalize_host_value(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return "localhost"
        if cleaned.lower() in LOCALHOST_ALIASES:
            return "localhost"
        return cleaned

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="Ollie Local Host",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.status_label = ctk.CTkLabel(
            header,
            text="Stopped",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.status_label.grid(row=0, column=1, sticky="e", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            header,
            text="Starts the shared HTTPS server for the Outlook add-in and API.",
            anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        controls = ctk.CTkFrame(self)
        controls.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        controls.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        self.start_button = ctk.CTkButton(
            controls,
            text="Start Host",
            command=lambda: self._run_ui_action("start host", self.start_host),
        )
        self.start_button.grid(row=0, column=0, padx=8, pady=12, sticky="ew")

        self.stop_button = ctk.CTkButton(
            controls,
            text="Stop Host",
            command=lambda: self._run_ui_action("stop host", self.stop_host),
            state="disabled",
        )
        self.stop_button.grid(row=0, column=1, padx=8, pady=12, sticky="ew")

        self.save_button = ctk.CTkButton(
            controls,
            text="Save Settings",
            command=lambda: self._run_ui_action("save settings", self.save_settings),
        )
        self.save_button.grid(row=0, column=2, padx=8, pady=12, sticky="ew")

        self.open_button = ctk.CTkButton(
            controls,
            text="Open Host URL",
            command=lambda: self._run_ui_action("open host URL", self.open_host_url),
        )
        self.open_button.grid(row=0, column=3, padx=8, pady=12, sticky="ew")

        self.open_log_button = ctk.CTkButton(
            controls,
            text="Open Log File",
            command=lambda: self._run_ui_action("open log file", self.open_log_file),
        )
        self.open_log_button.grid(row=0, column=4, padx=8, pady=12, sticky="ew")

        self.trust_cert_button = ctk.CTkButton(
            controls,
            text="Trust Certificate",
            command=lambda: self._run_ui_action("trust certificate", self.trust_certificate),
        )
        self.trust_cert_button.grid(row=0, column=5, padx=8, pady=12, sticky="ew")

        content = ctk.CTkFrame(self)
        content.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 16))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        settings_frame = ctk.CTkFrame(content)
        settings_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        settings_frame.grid_columnconfigure(1, weight=1)

        for index, field in enumerate(ENV_FIELDS):
            key = str(field["key"])
            ctk.CTkLabel(settings_frame, text=str(field["label"])).grid(
                row=index,
                column=0,
                padx=(12, 8),
                pady=(8, 2),
                sticky="sw",
            )
            entry = ctk.CTkEntry(settings_frame, show="*" if field.get("secret") else None)
            entry.grid(row=index, column=1, padx=(0, 12), pady=(8, 2), sticky="ew")
            self.entries[key] = entry
            ctk.CTkLabel(
                settings_frame,
                text=str(field["hint"]),
                text_color=("gray35", "gray70"),
                anchor="w",
            ).grid(row=index, column=2, padx=(0, 12), pady=(8, 2), sticky="sw")

        settings_frame.grid_columnconfigure(2, weight=1)

        self.env_label = ctk.CTkLabel(
            settings_frame,
            text=f"Settings file: {self.env_path}",
            anchor="w",
        )
        self.env_label.grid(
            row=len(ENV_FIELDS),
            column=0,
            columnspan=3,
            padx=12,
            pady=(8, 2),
            sticky="ew",
        )

        self.frontend_label = ctk.CTkLabel(
            settings_frame,
            text=f"Frontend bundle: {self.frontend_dist}",
            anchor="w",
        )
        self.frontend_label.grid(
            row=len(ENV_FIELDS) + 1,
            column=0,
            columnspan=3,
            padx=12,
            pady=(2, 4),
            sticky="ew",
        )

        self.log_path_label = ctk.CTkLabel(
            settings_frame,
            text=f"Log file: {self.log_path}",
            anchor="w",
        )
        self.log_path_label.grid(
            row=len(ENV_FIELDS) + 2,
            column=0,
            columnspan=3,
            padx=12,
            pady=(2, 12),
            sticky="ew",
        )

        readiness_frame = ctk.CTkFrame(content)
        readiness_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        readiness_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            readiness_frame,
            text="Readiness",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 8))

        self.readiness_labels: dict[str, ctk.CTkLabel] = {}
        for column, key in enumerate(("frontend", "certificate", "api")):
            frame = ctk.CTkFrame(readiness_frame)
            frame.grid(row=1, column=column, sticky="ew", padx=8, pady=(0, 12))
            frame.grid_columnconfigure(0, weight=1)
            title = {
                "frontend": "Frontend Build",
                "certificate": "HTTPS Certificate",
                "api": "API Health",
            }[key]
            ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, sticky="w", padx=12, pady=(10, 4)
            )
            label = ctk.CTkLabel(frame, text="Checking...", anchor="w")
            label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
            self.readiness_labels[key] = label

        logs_frame = ctk.CTkFrame(content)
        logs_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(8, 12))
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            logs_frame,
            text="Logs",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        self.log_box = ctk.CTkTextbox(logs_frame)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")
        self.log_box.insert("end", "Logs will appear here after startup actions.\n")
        self.log_box.configure(state="disabled")

    def _load_env_values(self) -> None:
        values = read_env_file(self.env_path)
        defaults = {
            "RAG_SERVICE_URL": settings.rag_service_url,
            "MODEL_API_BASE_URL": "",
            "MODEL_API_KEY": "",
            "LLM_MODEL": settings.llm_model,
            "SERVER_HOST": self._normalize_host_value(settings.server_host),
            "SERVER_PORT": str(settings.server_port),
        }
        for key, entry in self.entries.items():
            entry.delete(0, "end")
            current_value = values.get(key, str(defaults[key]))
            if key == "SERVER_HOST":
                current_value = self._normalize_host_value(current_value)
            entry.insert(0, current_value)

    def save_settings(self) -> None:
        self._append_log("Saving settings...")
        updates = {key: entry.get().strip() for key, entry in self.entries.items()}
        normalized_host = self._normalize_host_value(updates.get("SERVER_HOST", ""))
        if updates.get("SERVER_HOST", "") != normalized_host:
            self._append_log(
                f"Normalized SERVER_HOST from '{updates.get('SERVER_HOST', '')}' to '{normalized_host}'."
            )
        updates["SERVER_HOST"] = normalized_host
        self.entries["SERVER_HOST"].delete(0, "end")
        self.entries["SERVER_HOST"].insert(0, normalized_host)
        cert_path, key_path = ensure_https_env()
        updates["SSL_CERTFILE"] = str(cert_path)
        updates["SSL_KEYFILE"] = str(key_path)
        write_env_values(updates, self.env_path)
        self._append_log(f"Saved settings to {self.env_path}")
        trusted, trust_message = trust_certificate_for_current_user(cert_path)
        self._append_log(trust_message)
        if trusted:
            self.status_label.configure(text="Certificate trusted")
        self._refresh_readiness()

    def trust_certificate(self) -> None:
        self._append_log("Trusting localhost certificate for current user...")
        cert_path, _ = ensure_https_env()
        trusted, message = trust_certificate_for_current_user(cert_path)
        self._append_log(message)
        if trusted:
            self.status_label.configure(text="Certificate trusted")
        self._refresh_readiness()

    def start_host(self) -> None:
        self._append_log("Start requested.")
        if self.server_thread and self.server_thread.is_alive():
            self._append_log("Host is already running.")
            return

        if not self.frontend_dist.exists():
            self._append_log(
                "Frontend build not found. Run 'npm.cmd run build' in the frontend directory first."
            )
            return

        self.save_settings()
        self._attach_log_handler()

        host = self._normalize_host_value(self.entries["SERVER_HOST"].get())
        if self.entries["SERVER_HOST"].get().strip() != host:
            self.entries["SERVER_HOST"].delete(0, "end")
            self.entries["SERVER_HOST"].insert(0, host)
        port = int(self.entries["SERVER_PORT"].get().strip() or "8000")
        env_values = read_env_file(self.env_path)
        server_app = create_app()
        self._append_log(f"Using env file: {self.env_path}")
        self._append_log(f"Using frontend build: {self.frontend_dist}")
        self._append_log(f"Using certificate: {env_values.get('SSL_CERTFILE', '')}")

        config = uvicorn.Config(
            server_app,
            host=host,
            port=port,
            reload=False,
            ssl_certfile=env_values.get("SSL_CERTFILE"),
            ssl_keyfile=env_values.get("SSL_KEYFILE"),
            log_level="info",
            log_config=None,
        )
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(target=self.server.run, daemon=True)
        self.server_thread.start()

        self.status_label.configure(text=f"Running on https://{host}:{port}")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._append_log(f"Starting Ollie host on https://{host}:{port}")
        self._refresh_readiness()

    def stop_host(self) -> None:
        if self.server is None:
            return
        self.server.should_exit = True
        self.status_label.configure(text="Stopping...")
        self._append_log("Stopping Ollie host...")
        self.after(300, self._finish_stop_if_ready)

    def _finish_stop_if_ready(self) -> None:
        if self.server_thread and self.server_thread.is_alive():
            self.after(300, self._finish_stop_if_ready)
            return

        self.server = None
        self.server_thread = None
        self.status_label.configure(text="Stopped")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self._append_log("Ollie host stopped.")
        self._refresh_readiness()

    def open_host_url(self) -> None:
        host = self._normalize_host_value(self.entries["SERVER_HOST"].get())
        port = self.entries["SERVER_PORT"].get().strip() or "8000"
        webbrowser.open(f"https://{host}:{port}")

    def _attach_log_handler(self) -> None:
        if self.log_handler is not None:
            return
        self.log_handler = QueueLogHandler(self.log_queue)
        self.file_log_handler = logging.FileHandler(self.log_path, encoding="utf-8")
        self.file_log_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(self.log_handler)
        root_logger.addHandler(self.file_log_handler)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(message)
        self.after(LOG_POLL_INTERVAL_MS, self._drain_log_queue)

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _run_ui_action(self, action_name: str, callback: callable) -> None:
        try:
            callback()
        except Exception as exc:
            self.status_label.configure(text="Error")
            self._append_log(f"Failed to {action_name}: {exc}")
            self._append_log(traceback.format_exc())

    def _set_readiness(self, key: str, ready: bool, message: str) -> None:
        label = self.readiness_labels[key]
        prefix = "Ready" if ready else "Missing"
        color = "#2f855a" if ready else "#c05621"
        if key == "api" and message.startswith("Waiting"):
            prefix = "Checking"
            color = "#b7791f"
        label.configure(text=f"{prefix}: {message}", text_color=color)

    def _refresh_readiness(self) -> None:
        frontend_ready = self.frontend_dist.exists()
        self._set_readiness(
            "frontend",
            frontend_ready,
            str(self.frontend_dist) if frontend_ready else "frontend/dist not found",
        )

        cert_ready = CERT_PATH.exists() and KEY_PATH.exists()
        cert_message = str(CERT_PATH) if cert_ready else "Certificate will be generated on save/start"
        self._set_readiness("certificate", cert_ready, cert_message)

        self._refresh_api_status()

    def _refresh_api_status(self) -> None:
        if self.server is None or not self.server_thread or not self.server_thread.is_alive():
            self._set_readiness("api", False, "Waiting for host start")
            return

        host = self._normalize_host_value(self.entries["SERVER_HOST"].get())
        port = self.entries["SERVER_PORT"].get().strip() or "8000"
        url = f"https://{host}:{port}/api/health"

        try:
            with httpx.Client(verify=False, timeout=1.5) as client:
                response = client.get(url)
            if response.is_success:
                self._set_readiness("api", True, url)
            else:
                self._set_readiness("api", False, f"{url} returned {response.status_code}")
        except Exception:
            self._set_readiness("api", False, f"Waiting for {url}")

    def _poll_runtime_status(self) -> None:
        self._refresh_readiness()
        self.after(HEALTH_CHECK_INTERVAL_MS, self._poll_runtime_status)

    def open_log_file(self) -> None:
        self.log_path.touch(exist_ok=True)
        webbrowser.open(self.log_path.as_uri())

    def on_close(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        self.destroy()


def main() -> None:
    app_instance = OllieDesktopHost()
    app_instance.mainloop()


if __name__ == "__main__":
    main()
