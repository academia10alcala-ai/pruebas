"""Arranca la aplicación en local (sin Docker). Lo usa iniciar.bat, pero también vale: python launcher.py"""
import json
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datos"
CONFIG = DATA / "config.json"
PORT = int(os.environ.get("PORT", "8000"))


def lan_ip() -> str:
    """IP del ordenador en la red local (para abrirlo desde el móvil)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "IP-DEL-ORDENADOR"


def load_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    print("\nPrimera vez: elige el acceso al programa.\n")
    user = input("Usuario [admin]: ").strip() or "admin"
    password = ""
    while len(password) < 6:
        password = input("Contraseña (mínimo 6 caracteres, se verá al escribirla): ").strip()
    DATA.mkdir(exist_ok=True)
    config = {"user": user, "password": password}
    CONFIG.write_text(json.dumps(config), encoding="utf-8")
    print("\nGuardado. Para cambiarlo, borra el archivo datos\\config.json y vuelve a abrir el programa.")
    return config


def main():
    config = load_config()
    DATA.mkdir(exist_ok=True)
    os.environ["APP_USER"], os.environ["APP_PASSWORD"] = config["user"], config["password"]
    os.environ["DATABASE_URL"] = f"sqlite:///{(DATA / 'gestion.db').as_posix()}"

    print("\n" + "=" * 60)
    print("  Programa en marcha. NO cierres esta ventana mientras lo uses.")
    print(f"  En este ordenador:        http://localhost:{PORT}")
    print(f"  Desde el móvil (misma wifi): http://{lan_ip()}:{PORT}")
    print(f"  Usuario: {config['user']}")
    print("  Para apagarlo: cierra esta ventana.")
    print("=" * 60 + "\n")

    threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(f"http://localhost:{PORT}")), daemon=True).start()

    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
