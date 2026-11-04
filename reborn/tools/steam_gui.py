"""Creative Destruction Reborn — graphical Windows launcher.

Standard-library Tkinter UI. The login and registration requests run on worker
threads; credentials never go to logs, config files or subprocess argv. The
game bridge stays bound to localhost, with certificate-verified remote TLS.
"""
import json
import queue
import socket
import ssl
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request
import getpass

TOOLS = Path(__file__).resolve().parent
GAME_ROOT = (Path(sys.executable).resolve().parent
             if getattr(sys, "frozen", False)
             else TOOLS.parents[1])
sys.path.insert(0, str(TOOLS))
from steam_bridge import AccountLogin, ACCOUNT_OPENER, format_account_http_error, run  # noqa: E402
from steam_launcher import load_config  # noqa: E402
from patch_server import patch  # noqa: E402

CONFIG = GAME_ROOT / "reborn" / "client-config.json"
BG = "#0b1019"
PANEL = "#151e2b"
TEXT = "#e9eef8"
MUTED = "#a7b4c8"
ACCENT = "#39d5aa"


def friendly_error(detail, action="login"):
    """Turn account failures into safe, player-facing guidance."""
    value = str(detail).lower()
    if "invalid_credentials" in value or "http 401" in value:
        return "Username or password not recognised. Check your details or create an account."
    if "registration_requires_invitation" in value:
        return "You need an invitation from the Reborn server administrator."
    if "invitation invalid" in value:
        return "Your invitation is invalid or expired. Ask for a new one."
    if "username unavailable" in value:
        return "That username is already taken. Choose another."
    if "http 429" in value or "rate_limited" in value:
        return "Too many attempts. Please try again later."
    if "http 403" in value or "forbidden" in value:
        return "The account service refused access. Check the connection in Settings."
    if "timed out" in value or "urlerror" in value:
        return "Could not connect to the account service. Check your connection."
    if "put the gui launcher" in value:
        return "Game files missing. Install the launcher beside client.exe and script.npk."
    if "account api" in value or "ssl" in value:
        return "The account service is unavailable or its secure connection failed."
    return ("Could not create your account. Check your details and try again."
            if action == "register" else "Could not sign in. Check Settings and try again.")


def diagnose_auth(url):
    """No account secrets: GET /v1/me should return API JSON/401."""
    request = Request(url.rstrip("/") + "/v1/me",
                      headers={"Accept": "application/json"}, method="GET")
    try:
        with ACCOUNT_OPENER.open(request, timeout=8) as response:
            if "application/json" not in response.headers.get("Content-Type", ""):
                return "Unexpected API response", False
            return "Account API connected (HTTP %d)" % response.status, True
    except HTTPError as exc:
        if exc.code == 401 and "application/json" in exc.headers.get("Content-Type", ""):
            return "Account API online — sign in required", True
        return format_account_http_error(exc), False
    except (ValueError, URLError, OSError) as exc:
        return "%s: %s" % (type(exc).__name__, str(exc)[:180]), False


def diagnose_game(host, tls_host):
    """Verify TLS and hostname on the login port, without sending credentials."""
    try:
        with socket.create_connection((host, 4000), timeout=5) as raw:
            with ssl.create_default_context().wrap_socket(
                raw, server_hostname=tls_host
            ) as secure:
                return "Game TLS online (%s)" % secure.version(), True
    except (ssl.SSLError, OSError) as exc:
        return "Game TLS unavailable: %s" % type(exc).__name__, False


def signup(auth_url, username, password, invite):
    """Create an account via the existing single-use invite API, no secrets on disk."""
    data = json.dumps({
        "username": username, "password": password, "invite_code": invite
    }).encode("utf-8")
    request = Request(auth_url.rstrip("/") + "/v1/register", data=data,
                      headers={"Content-Type": "application/json"},
                      method="POST")
    try:
        with ACCOUNT_OPENER.open(request, timeout=15) as response:
            value = json.loads(response.read(8192))
            if response.status != 201 or not isinstance(value.get("account"), dict):
                raise ValueError("Unexpected registration response")
            return value["account"]["username"]
    except HTTPError as exc:
        raise ValueError(format_account_http_error(exc)) from exc


class RebornLauncher:
    def __init__(self, root):
        self.root = root
        root.title("Creative Destruction Reborn — Launcher")
        root.geometry("980x700")
        root.minsize(780, 610)
        root.configure(bg=BG)
        self.events = queue.Queue()
        self.busy = False
        self.game_active = False
        self.config_error = ""
        try:
            host, tls_host, auth_url = load_config(CONFIG)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            host, tls_host, auth_url = (
                "game-cdr.nekosunevr.co.uk",
                "game-cdr.nekosunevr.co.uk",
                "https://auth-cdr.nekosunevr.co.uk")
            self.config_error = str(exc)

        self.game_host = tk.StringVar(value=host)
        self.tls_host = tk.StringVar(value=tls_host)
        self.auth_url = tk.StringVar(value=auth_url)
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.reg_username = tk.StringVar()
        self.reg_password = tk.StringVar()
        self.reg_confirm = tk.StringVar()
        self.invite = tk.StringVar()
        self.status = tk.StringVar(value="Ready — sign in or create your Reborn account")
        self.api_status = tk.StringVar(value="Not checked")
        self.game_status = tk.StringVar(value="Not checked")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(20, 13))
        style.map("TNotebook.Tab", background=[("selected", "#233347")], foreground=[("selected", TEXT)])
        style.configure("TNotebook.Tab", padding=(18, 10), font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 9))
        style.configure("Accent.TButton", background=ACCENT, foreground="#071a16", font=("Segoe UI", 11, "bold"), padding=(24, 13), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#70edca")])
        style.configure("TEntry", padding=7, font=("Segoe UI", 10))

        header = tk.Frame(root, bg=BG, padx=32, pady=22)
        header.pack(fill="x")
        tk.Label(header, text="CD  /  REBORN", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(header, text="Creative Destruction", bg=BG, fg=TEXT,
                 font=("Segoe UI", 27, "bold")).pack(anchor="w", pady=(3, 2))
        tk.Label(header, text="Private multiplayer  •  Your adventure starts here",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Frame(root, bg="#293447", height=1).pack(fill="x", padx=30, pady=(0, 18))

        footer = tk.Frame(root, bg="#101b25", padx=25, pady=12)
        footer.pack(side="bottom", fill="x", padx=24, pady=(0, 12))
        self.status_label = tk.Label(footer, textvariable=self.status,
                                     bg="#101b25", fg=TEXT, anchor="w",
                                     justify="left", wraplength=820,
                                     font=("Segoe UI", 10))
        self.status_label.pack(fill="x")
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self.play_tab = ttk.Frame(self.tabs)
        self.register_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.play_tab, text="Play")
        self.tabs.add(self.register_tab, text="Create Account")
        self.tabs.add(self.settings_tab, text="Settings & Diagnostics")
        self.build_play()
        self.build_registration()
        self.build_settings()


        self.root.after(100, self.flush_events)
        if self.config_error:
            self.status.set("Server settings need attention. Open Settings to review them.")

    def field(self, parent, label, var, secret=False):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(13, 4))
        entry = ttk.Entry(parent, textvariable=var, show="•" if secret else "")
        entry.pack(fill="x")
        return entry

    def build_play(self):
        shell = tk.Frame(self.play_tab, bg=BG, padx=28, pady=28)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=3)
        shell.grid_columnconfigure(1, weight=2)
        shell.grid_rowconfigure(0, weight=1)

        left = tk.Frame(shell, bg=PANEL, padx=28, pady=25,
                        highlightthickness=1, highlightbackground="#293447")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(left, text="PLAYER ACCOUNT", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(left, text="Ready to drop in?", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(8, 5))
        tk.Label(left, text="Sign in to your independent Reborn account.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 19))
        tk.Label(left, text="Username", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 5))
        user_entry = ttk.Entry(left, textvariable=self.username, font=("Segoe UI", 11))
        user_entry.pack(fill="x", pady=(0, 13))
        tk.Label(left, text="Password", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 5))
        password_entry = ttk.Entry(left, textvariable=self.password,
                                   show="•", font=("Segoe UI", 11))
        password_entry.pack(fill="x")
        password_entry.bind("<Return>", lambda _: self.on_play())
        self.play_button = ttk.Button(left, text="SIGN IN & PLAY",
                                      style="Accent.TButton", command=self.on_play)
        self.play_button.pack(fill="x", pady=(23, 13))
        tk.Label(left, text="Don't have an account? Select Create Account above.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                 wraplength=360, justify="left").pack(anchor="w")
        user_entry.focus_set()

        right = tk.Frame(shell, bg="#11252b", padx=23, pady=26,
                         highlightthickness=1, highlightbackground="#285448")
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="REBORN MULTIPLAYER", bg="#11252b",
                 fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(right, text="WELCOME TO\nTHE BATTLEFIELD",
                 bg="#11252b", fg=TEXT, justify="left",
                 font=("Segoe UI", 19, "bold")).pack(anchor="w", pady=(22, 12))
        tk.Label(right, text="A community-hosted revival experience.",
                 bg="#11252b", fg="#b1c9c7",
                 font=("Segoe UI", 10), wraplength=260,
                 justify="left").pack(anchor="w", pady=(0, 30))
        tk.Label(right, text="GAME SERVER", bg="#11252b",
                 fg="#87aea9", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(right, textvariable=self.game_host, bg="#11252b",
                 fg=TEXT, wraplength=270, justify="left",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 18))
        tk.Label(right, text="Secure sign-in  •  Automatic game bridge",
                 bg="#11252b", fg="#87aea9",
                 font=("Segoe UI", 9), wraplength=265,
                 justify="left").pack(anchor="w")

    def build_registration(self):
        p = ttk.Frame(self.register_tab, padding=(34, 16))
        p.pack(fill="both", expand=True)
        ttk.Label(p, text="Your next adventure starts here", font=("Segoe UI", 19, "bold")
                  ).pack(anchor="w")
        ttk.Label(p, text="Join the Reborn community with a one-time invitation.",
                  style="Sub.TLabel").pack(anchor="w", pady=(5, 0))
        self.field(p, "Username", self.reg_username)
        self.field(p, "Password (12–128 characters)", self.reg_password, secret=True)
        self.field(p, "Confirm password", self.reg_confirm, secret=True)
        self.field(p, "One-time invitation", self.invite, secret=True)
        self.register_button = ttk.Button(p, text="CREATE ACCOUNT",
                                          command=self.on_register)
        self.register_button.pack(anchor="w", pady=(20, 0))

    def build_settings(self):
        p = ttk.Frame(self.settings_tab, padding=(34, 18))
        p.pack(fill="both", expand=True)
        self.field(p, "Game DNS-only hostname", self.game_host)
        self.field(p, "Game TLS certificate hostname", self.tls_host)
        self.field(p, "HTTPS account API", self.auth_url)
        buttons = ttk.Frame(p)
        buttons.pack(fill="x", pady=18)
        ttk.Button(buttons, text="Save Settings", command=self.on_save).pack(side="left")
        self.check_button = ttk.Button(buttons, text="Test Connections",
                                       command=self.on_diagnose)
        self.check_button.pack(side="left", padx=12)
        ttk.Label(p, text="Account API:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(p, textvariable=self.api_status, wraplength=640).pack(anchor="w", pady=(3, 12))
        ttk.Label(p, text="Game TLS:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(p, textvariable=self.game_status, wraplength=640).pack(anchor="w", pady=(3, 10))

    def current(self):
        # Use the exact same validation as the existing CLI launcher.
        from steam_bridge import validate_game_host
        from urllib.parse import urlsplit
        host = validate_game_host(self.game_host.get())
        tls = validate_game_host(self.tls_host.get())
        address = self.auth_url.get().strip().rstrip("/")
        uri = urlsplit(address)
        if (uri.scheme != "https" or not uri.hostname or uri.username or
                uri.password or uri.path or uri.query or uri.fragment):
            raise ValueError("Account URL must be plain HTTPS without paths or credentials")
        return host, tls, address

    def worker(self, task, callback):
        if self.busy:
            return
        self.busy = True
        self.set_busy(True)
        def go():
            try:
                output = task()
                self.events.put((callback, True, output))
            except Exception as exc:
                # Error strings from AccountLogin are intentionally sanitized.
                detail = str(exc) if isinstance(exc, (ValueError, FileNotFoundError, OSError)) else type(exc).__name__
                self.events.put((callback, False, detail))
        threading.Thread(target=go, daemon=True).start()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.play_button.configure(state=state)
        self.register_button.configure(state=state)
        self.check_button.configure(state=state)

    def flush_events(self):
        try:
            while True:
                callback, ok, value = self.events.get_nowait()
                self.busy = False
                self.set_busy(False)
                callback(ok, value)
        except queue.Empty:
            pass
        self.root.after(100, self.flush_events)

    def show_failure(self, message):
        self.status_label.configure(fg="#ff9eae")
        self.status.set(message)
        messagebox.showerror("Launch failed", message, parent=self.root)

    def show_progress(self, message):
        self.status_label.configure(fg=ACCENT)
        self.status.set(message)

    def on_play(self):
        if self.game_active:
            self.status.set("A game session is already running")
            return
        user, secret = self.username.get().strip(), self.password.get()
        self.password.set("")
        if not user or not secret:
            messagebox.showwarning("Missing login", "Enter your Reborn username and password.")
            return
        try:
            host, tls, auth_url = self.current()
        except ValueError:
            self.show_failure("Server settings are invalid. Review them in Settings.")
            return
        game = GAME_ROOT / "client.exe"
        if not game.is_file() or not (GAME_ROOT / "script.npk").is_file():
            self.show_failure("Game files not found. Place RebornLauncher.exe and its _internal folder next to client.exe and script.npk.")
            return
        self.show_progress("Signing in securely to your Reborn account...")
        def task():
            account = AccountLogin(auth_url, user, secret)
            return (account, host, tls, game)
        def finished(ok, result):
            if not ok:
                self.show_failure(friendly_error(result, "login"))
                return
            account, host_name, tls_name, game = result
            self.game_active = True
            self.show_progress("Signed in. Starting the game connection...")
            self.play_button.configure(state="disabled")
            def start():
                try:
                    patch(str(GAME_ROOT), "http://127.0.0.1:8000/")
                    run(host_name, account, tls_name, game_executable=game)
                    self.events.put((self.game_finished, True, "Game closed; bridge stopped."))
                except Exception as exc:
                    self.events.put((self.game_finished, False, "Game connection failed to start. Check game files, server connectivity and whether another launcher is running."))
            threading.Thread(target=start, daemon=True).start()
        self.worker(task, finished)

    def game_finished(self, ok, message):
        self.game_active = False
        self.play_button.configure(state="normal")
        if ok:
            self.status_label.configure(fg=ACCENT)
            self.status.set(message)
        else:
            self.show_failure(message)

    def on_register(self):
        username = self.reg_username.get().strip()
        password, confirm, invite = (
            self.reg_password.get(), self.reg_confirm.get(), self.invite.get().strip())
        self.reg_password.set("")
        self.reg_confirm.set("")
        self.invite.set("")
        if password != confirm:
            messagebox.showwarning("Passwords differ", "Both passwords must match.")
            return
        if len(password) < 12 or len(password) > 128 or not username or not invite:
            messagebox.showwarning("Missing details", "Enter username, 12–128 character password and invite.")
            return
        try:
            _, _, auth_url = self.current()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.status.set("Creating account through HTTPS...")
        def finished(ok, result):
            if ok:
                self.username.set(result)
                self.tabs.select(self.play_tab)
                self.status.set("Account created. Enter your password to Play.")
                messagebox.showinfo("Registration successful", "Account created: " + result)
            else:
                self.show_failure(friendly_error(result, "register"))
        self.worker(lambda: signup(auth_url, username, password, invite), finished)

    def on_save(self):
        if self.game_active:
            self.status.set("Close the game before changing its connection settings")
            return
        try:
            host, tls, auth_url = self.current()
            if host != tls:
                raise ValueError("TLS certificate hostname should match your game DNS name")
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            payload = {"game_host": host, "game_tls_hostname": tls, "auth_url": auth_url}
            # Only public endpoints are persisted, NEVER passwords or invite codes.
            tmp = CONFIG.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(CONFIG)
            self.status.set("Public server settings saved.")
        except (ValueError, OSError) as exc:
            self.status.set("Settings not saved: " + str(exc))

    def on_diagnose(self):
        try:
            host, tls, auth_url = self.current()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.status.set("Checking account HTTPS and game TLS certificates...")
        def task():
            return (diagnose_auth(auth_url), diagnose_game(host, tls))
        def finished(ok, result):
            if not ok:
                self.status.set("Connection check failed. Review your network and server settings.")
                return
            (api_msg, api_ok), (game_msg, game_ok) = result
            self.api_status.set(api_msg)
            self.game_status.set(game_msg)
            self.status.set("Checks completed: API %s; game TLS %s" %
                            ("OK" if api_ok else "FAILED", "OK" if game_ok else "FAILED"))
        self.worker(task, finished)


def main():
    root = tk.Tk()
    RebornLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
