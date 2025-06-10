"""
Plugin: Renomeação NOBRADI
--------------------------
Gera nomes no padrão:

    <BR>_<Repositório>_<Gênero>_<Espécie/Tipo>_<NNNN>

Ex.: BR_APESP_MI_LP_0009

Modos (GUI):
  1. In-place (mantém hierarquia)
  2. Nova pasta (copia/move p/ destino)
  3. Por metadados (lotes por mtime)

Cada arquivo renomeado gera evento PREMIS ("name").
"""

from __future__ import annotations
import hashlib, shutil, threading
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox

from digitarq.premis_logger import registrar_evento
from digitarq.erro import logging

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def gerar_nome(dados: Dict, seq: int) -> str:
    """Constrói BR_<Repo>_<Genero>_<Tipo>_<####>."""
    return (
        f"{dados.get('BR','BR')}_"
        f"{dados.get('Repositório','RP')}_"
        f"{dados.get('Gênero','GN')}_"
        f"{dados.get('Espécie/Tipo','TP')}_"
        f"{seq:04d}"
    )


def lotear(arquivos: List[Path], minutos: int
           ) -> List[Tuple[str, List[Path]]]:
    if not arquivos:
        return []
    files = sorted(arquivos, key=lambda p: p.stat().st_mtime)
    lotes, atual, idx = [], [], 1
    prev_t = datetime.fromtimestamp(files[0].stat().st_mtime)
    for f in files:
        cur = datetime.fromtimestamp(f.stat().st_mtime)
        if (cur - prev_t) > timedelta(minutes=minutos) and atual:
            lotes.append((f"{prev_t.date()}_Lote{idx:02d}", atual))
            idx += 1; atual = []
        atual.append(f); prev_t = cur
    if atual:
        lotes.append((f"{prev_t.date()}_Lote{idx:02d}", atual))
    return lotes


def evento_nome(src: Path, dst: Path):
    sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    registrar_evento("name", str(src),
                     {"novo_nome": dst.name, "sha256": sha})


# ------------------------------------------------------------------
# Diálogo de opções
# ------------------------------------------------------------------
def dialog_opcoes(master: tk.Tk) -> Optional[Dict]:
    win = tk.Toplevel(master)
    win.title("Renomeação – escolher modo")
    win.grab_set(); win.resizable(False, False)

    modo_var = tk.StringVar(value="inplace")
    dest_var = tk.StringVar()
    intervalo_var = tk.IntVar(value=30)

    opções = (
        ("1 · In-place (mantém hierarquia)", "inplace"),
        ("2 · Nova pasta", "nova"),
        ("3 · Por metadados (lotes)", "meta"),
    )
    tk.Label(win, text="Modo de renomeação:",
             font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                              padx=10, pady=(8,4), sticky="w")
    for i, (txt, val) in enumerate(opções, 1):
        tk.Radiobutton(win, text=txt, variable=modo_var, value=val)\
          .grid(row=i, column=0, columnspan=2, sticky="w", padx=20)

    # Botão destino (modo nova)
    dest_btn = tk.Button(
        win, text="Escolher pasta destino (modo 2)",
        command=lambda: dest_var.set(
            filedialog.askdirectory(title="Destino"))
    )
    dest_btn.grid(row=4, column=0, columnspan=2, pady=6, padx=10, sticky="w")

    # Intervalo (modo meta)
    tk.Label(win, text="Intervalo min p/ lotes (modo 3):")\
        .grid(row=5, column=0, sticky="w", padx=10)
    spin = tk.Spinbox(win, from_=1, to=1440, width=5, textvariable=intervalo_var)
    spin.grid(row=5, column=1, sticky="w", padx=4)

    # Habilitar/desabilitar widgets
    def toggle(*_):
        dest_btn.configure(state="normal" if modo_var.get() == "nova" else "disabled")
        spin.configure(state="normal" if modo_var.get() == "meta" else "disabled")
    modo_var.trace_add("write", toggle); toggle()

    res: Optional[Dict] = None
    def ok():
        nonlocal res
        res = {
            "modo": modo_var.get(),
            "destino": dest_var.get(),
            "intervalo": intervalo_var.get(),
        }
        win.destroy()
    tk.Button(win, text="OK", width=10, command=ok)\
        .grid(row=6, column=1, pady=10, sticky="e")
    tk.Button(win, text="Cancelar", width=10, command=win.destroy)\
        .grid(row=6, column=0, pady=10, sticky="w")

    win.wait_window()
    return res


# ------------------------------------------------------------------
# Worker
# ------------------------------------------------------------------
def worker(tarefas: List[Tuple[Path, Path]], q: Queue):
    try:
        total = len(tarefas); q.put(("total", total))
        for idx, (src, dst) in enumerate(tarefas, 1):
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src != dst:
                shutil.copy2(src, dst)
            evento_nome(src, dst)
            q.put(("done", idx))
        q.put(("fim", 0))
    except Exception as exc:
        logging.exception("Erro no rename"); q.put(("erro", str(exc)))


# ------------------------------------------------------------------
# run()
# ------------------------------------------------------------------
def run(context):
    root = tk._default_root or tk.Tk()

    origem_path = filedialog.askdirectory(title="Pasta de origem")
    if not origem_path:
        return
    opts = dialog_opcoes(root)
    if not opts:
        return

    origem = Path(origem_path)
    arquivos = [p for p in origem.rglob("*") if p.is_file()]
    if not arquivos:
        messagebox.showwarning("Aviso", "Nenhum arquivo encontrado."); return

    modo = opts["modo"]
    destino_base = Path(opts["destino"]) if modo == "nova" else origem
    intervalo = opts["intervalo"]

    tarefas=[]; seq=1
    if modo == "meta":
        for sub, files in lotear(arquivos, intervalo):
            for f in files:
                novo = gerar_nome(context.campos, seq) + f.suffix.lower()
                dst = destino_base / sub / novo
                tarefas.append((f, dst)); seq += 1
    else:
        for f in arquivos:
            novo = gerar_nome(context.campos, seq) + f.suffix.lower()
            dst_dir = destino_base / f.relative_to(origem).parent if modo=="inplace" else destino_base
            tarefas.append((f, dst_dir / novo)); seq += 1

    q: Queue = Queue()
    th = threading.Thread(target=worker, args=(tarefas, q))
    th.start()

    bar = tqdm(total=len(tarefas), desc="Renomeando") if tqdm else None
    while th.is_alive() or not q.empty():
        try:
            typ, val = q.get(timeout=0.1)
        except Empty:
            continue
        if typ == "done" and bar: bar.update(1)
        elif typ == "erro":
            messagebox.showerror("Erro", val); break
    if bar: bar.close()
    messagebox.showinfo("Concluído", "Renomeação finalizada.")
