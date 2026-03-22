# FinanceApp_Portable.py — Vrai logiciel avec fenêtre intégrée (PyWebView)
import sys
import threading
import tkinter as tk
from tkinter import ttk
import urllib.request

RAILWAY_URL = "https://projet-finance-production.up.railway.app"
APP_NAME    = "FinanceApp"
APP_VERSION = "1.0.0"

def check_connection():
    try:
        urllib.request.urlopen(RAILWAY_URL, timeout=8)
        return True
    except Exception:
        return False

def launch_webview():
    try:
        import webview
        window = webview.create_window(
            title      = APP_NAME,
            url        = RAILWAY_URL,
            width      = 1200,
            height     = 800,
            min_size   = (800, 600),
            resizable  = True,
            text_select= True,
        )
        webview.start(
            debug          = False,
            private_mode   = False,
            storage_path   = None,
        )
        return True
    except ImportError:
        return False
    except Exception as e:
        print("WebView error:", e)
        return False

def show_splash():
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("460x300")
    root.configure(bg="#0f172a")
    root.resizable(False, False)
    root.eval('tk::PlaceWindow . center')

    # Icône
    tk.Label(root, text="💳", font=("Segoe UI Emoji", 52),
             bg="#0f172a", fg="#f1f5f9").pack(pady=(28, 4))

    tk.Label(root, text="FinanceApp", font=("Arial", 22, "bold"),
             bg="#0f172a", fg="#6366f1").pack()

    tk.Label(root, text="Gestion de comptes personnels",
             font=("Arial", 10), bg="#0f172a", fg="#94a3b8").pack(pady=(2, 18))

    # Barre de progression
    progress = ttk.Progressbar(root, mode='indeterminate', length=300)
    progress.pack(pady=4)
    progress.start(12)

    status = tk.Label(root, text="⏳ Connexion au serveur...",
                      font=("Arial", 10), bg="#0f172a", fg="#94a3b8")
    status.pack(pady=8)

    version_label = tk.Label(root, text=f"v{APP_VERSION}",
                             font=("Arial", 8), bg="#0f172a", fg="#334155")
    version_label.pack(side="bottom", pady=6)

    def start_app():
        # Test connexion
        if not check_connection():
            progress.stop()
            status.config(text="❌ Pas de connexion internet", fg="#ef4444")
            tk.Button(root, text="🔄 Réessayer", font=("Arial", 11, "bold"),
                      bg="#6366f1", fg="white", relief="flat", padx=16, pady=8,
                      cursor="hand2",
                      command=lambda: [status.config(text="⏳ Reconnexion...", fg="#94a3b8"),
                                       progress.start(12),
                                       threading.Thread(target=start_app, daemon=True).start()]
                      ).pack(pady=6)
            return

        status.config(text="✅ Connecté ! Ouverture...", fg="#22c55e")
        root.after(800, lambda: [root.destroy(), launch_webview()])

    threading.Thread(target=start_app, daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    # Essayer PyWebView d'abord
    try:
        import webview
        # PyWebView dispo — lancer directement
        show_splash()
    except ImportError:
        # PyWebView pas installé — afficher splash avec message d'installation
        root = tk.Tk()
        root.title("FinanceApp — Installation")
        root.geometry("500x340")
        root.configure(bg="#0f172a")
        root.eval('tk::PlaceWindow . center')

        tk.Label(root, text="💳", font=("Segoe UI Emoji", 48),
                 bg="#0f172a", fg="#f1f5f9").pack(pady=(24,4))
        tk.Label(root, text="FinanceApp", font=("Arial", 20, "bold"),
                 bg="#0f172a", fg="#6366f1").pack()
        tk.Label(root, text="Première installation — préparation...",
                 font=("Arial", 10), bg="#0f172a", fg="#94a3b8").pack(pady=(4,12))

        status = tk.Label(root, text="📦 Installation du moteur d'affichage...",
                          font=("Arial", 10), bg="#0f172a", fg="#eab308")
        status.pack(pady=4)

        progress = ttk.Progressbar(root, mode='indeterminate', length=340)
        progress.pack(pady=8)
        progress.start(10)

        def install_webview():
            import subprocess
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install",
                                       "pywebview", "--quiet"],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
                root.after(0, lambda: [
                    progress.stop(),
                    status.config(text="✅ Installation réussie ! Redémarrage...", fg="#22c55e"),
                    root.after(1500, lambda: [root.destroy(), show_splash()])
                ])
            except Exception as e:
                root.after(0, lambda: [
                    progress.stop(),
                    status.config(text=f"❌ Erreur : {e}", fg="#ef4444")
                ])

        threading.Thread(target=install_webview, daemon=True).start()
        root.mainloop()
