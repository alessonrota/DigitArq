# digitarq_main.py – visual neutro (tons de cinza)
"""
Módulo principal da aplicação DigitArq
-------------------------------------
* GUI Tkinter com paleta cinza (diferente do ArquivAPESP)
* Formulário Nobrad → contexto global (FORM_CONTEXT)
* Descobre plugins em `src/plugins/*/meta.json` ou via entry‑points pip
* Eventos PREMIS + log de erros separados
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Dict, List

from .context import FORM_CONTEXT
from .premis_logger import registrar_evento
from .erro import logging
from .plugin_loader import discover_plugins

# ------------------------------------------------------------------
# 1. Paleta & helpers (tons de cinza)
# ------------------------------------------------------------------
PALETTE = {
    "bg_main": "#f4f4f4",
    "bg_panel": "#ffffff",
    "fg_text": "#333333",
    "btn": "#6c757d",
    "btn_hover": "#5a6268",
    "btn_danger": "#8b0000",
}

def grey_button(parent: tk.Widget, text: str, command, danger: bool = False):
    color = PALETTE["btn_danger"] if danger else PALETTE["btn"]
    return tk.Button(
        parent, text=text, command=command, width=42,
        bg=color, fg="white", activebackground=PALETTE["btn_hover"],
        relief="flat", font=("Segoe UI", 10, "bold" if danger else "normal")
    )

# ------------------------------------------------------------------
# 2. Descobrir plugins
# ------------------------------------------------------------------
PLUGIN_DIR = (Path(__file__).resolve().parent.parent / "plugins").resolve()
PLUGINS = discover_plugins(PLUGIN_DIR)

# ------------------------------------------------------------------
# 3. Especificação do formulário Nobrad
# ------------------------------------------------------------------
FORM_FIELDS: List[Dict] = [
    {"section": "Área de identificação do repositório",
     "fields": [
        {"code": "BR", "label": "País", "default": "BR"},
        {"code": "SP", "label": "UF", "default": "SP"},
        {"code": "Repositório", "label": "Repositório", "default": "DIG"},
     ]},
    {"section": "Área de identificação do conjunto documental",
     "fields": [
        {"code": "Fundo", "label": "Fundo", "default": "Imigrantes"},
        {"code": "Subconjunto", "label": "Subconjunto", "default": "Subconjunto"},
     ]},
    {"section": "Área de caracterização da unid. de descrição",
     "fields": [
        {"code": "Gênero", "label": "Gênero", "default": "ICO"},
        {"code": "Espécie/Tipo", "label": "Espécie/Tipo", "default": "FOT"},
        {"code": "Dispositivo", "label": "Dispositivo", "default": "FOT"},
        {"code": "Ação", "label": "Ação", "default": "Copia"},
     ]},
    {"section": "Dados do usuário",
     "fields": [
        {"code": "USR", "label": "Usuário", "default": "Fulano"},
     ]},
]

# ------------------------------------------------------------------
# 4. GUI principal
# ------------------------------------------------------------------
class AppGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DigitArq – Sistema de Funções Arquivísticas")
        self.root.geometry("820x720")
        self.root.configure(bg=PALETTE["bg_main"])
        self._config_style()

        self.entries: Dict[str, tk.Entry] = {}
        self._build_form()

    # -------- style
    def _config_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TLabel", background=PALETTE["bg_panel"], foreground=PALETTE["fg_text"])
        style.configure("TFrame", background=PALETTE["bg_panel"])
        style.configure("TEntry", relief="flat")

    # -------- form
    def _build_form(self):
        self.frm_form = ttk.Frame(self.root, padding=10)
        self.frm_form.pack(fill="both", expand=True, padx=20, pady=20)
        ttk.Label(self.frm_form, text="Preencha os dados do formulário:",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,6))

        for sec in FORM_FIELDS:
            self._add_section(sec)

        grey_button(self.frm_form, "Prosseguir", self._show_menu).pack(pady=12, anchor="e")

    def _add_section(self, sec_data: Dict):
        box = ttk.Frame(self.frm_form, padding=8, style="TFrame")
        box.pack(fill="x", pady=8)
        ttk.Label(box, text=sec_data["section"], font=("Segoe UI", 10, "bold"))\
            .pack(anchor="w", pady=(0,4))
        for field in sec_data["fields"]:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=field["code"], width=8).pack(side="left")
            ttk.Label(row, text=field["label"], width=32).pack(side="left")
            ent = ttk.Entry(row, width=35)
            ent.insert(0, field["default"])
            ent.pack(side="left", padx=4)
            self.entries[field["code"]] = ent

    # -------- menu
    def _show_menu(self):
        if not self._capture():
            return
        self.frm_form.pack_forget()
        self.frm_menu = ttk.Frame(self.root, padding=10)
        self.frm_menu.pack(fill="both", expand=True, padx=20, pady=20)
        ttk.Label(self.frm_menu, text="Escolha uma opção:", font=("Segoe UI", 12, "bold"))\
            .pack(anchor="w", pady=(0,8))

        if not PLUGINS:
            ttk.Label(self.frm_menu, text="Nenhum plugin encontrado.", foreground="red").pack()
        for plug in PLUGINS:
            grey_button(
                self.frm_menu, plug["name"],
                lambda p=plug: self._run_plugin(p)
            ).pack(pady=3)

        grey_button(self.frm_menu, "Voltar ao Formulário", self._back).pack(pady=(12,4))
        grey_button(self.frm_menu, "Sair", self.root.quit, danger=True).pack(pady=4)

    # -------- helpers
    def _back(self):
        self.frm_menu.pack_forget()
        self._build_form()

    def _capture(self) -> bool:
        data = {}
        for code, ent in self.entries.items():
            val = ent.get().strip()
            if not val:
                messagebox.showwarning("Aviso", f"O campo {code} não pode ficar vazio.")
                return False
            data[code] = val
        FORM_CONTEXT.campos = data
        return True

    def _run_plugin(self, plug: Dict):
        try:
            registrar_evento(plug["name"], object_id="batch-session",
                             detail={"usuario": FORM_CONTEXT.campos.get("USR", "")})
            plug["run"](FORM_CONTEXT)
        except Exception:
            logging.exception(f"Erro no plugin {plug['name']}")
            messagebox.showerror("Erro", f"Falha no plugin {plug['name']}. Veja logs/erro.log")


# ------------------------------------------------------------------
# Inicializador
# ------------------------------------------------------------------

def main():
    root = tk.Tk()
    AppGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
