"""
Plugin: Cópia / Mover Arquivos – v3 (UI com botões)
---------------------------------------------------
• Copiar ou Mover
• F – Somente arquivos
• K – Conservar hierarquia
• R – Recriar hierarquia por lotes (intervalo em minutos)
"""

from __future__ import annotations

import hashlib
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty, Queue
from typing import List, Tuple, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from digitarq.premis_logger import registrar_evento
from digitarq.erro import logging

try:
    from tqdm import tqdm  # opcional barra console
except ImportError:
    tqdm = None


# ------------------------------------------------------------------
# UI — diálogo modal com botões
# ------------------------------------------------------------------
def perguntar_opcoes(parent: tk.Tk) -> Optional[Tuple[str, str, int | None]]:
    """
    Retorna (ev_type, hier, intervalo)  ou  None se cancelar.

        ev_type  = "copy" | "move"
        hier     = "F" | "K" | "R"
        intervalo = int  (min)  ou None
    """
    result: Optional[Tuple[str, str, int | None]] = None

    win = tk.Toplevel(parent)
    win.title("Opções de Cópia/Mover")
    win.grab_set()
    win.resizable(False, False)

    # ---- operação ----
    tk.Label(win, text="Escolha a operação:").grid(row=0, column=0, sticky="w", pady=(8, 2), padx=10)
    op_var = tk.StringVar(value="copy")
    for idx, (txt, val) in enumerate((("Copiar", "copy"), ("Mover", "move"))):
        tk.Radiobutton(win, text=txt, variable=op_var, value=val)\
            .grid(row=1, column=idx, padx=10, sticky="w")

    # ---- hierarquia ----
    tk.Label(win, text="Estrutura de destino:").grid(row=2, column=0, sticky="w", pady=(8, 2), padx=10)
    hier_var = tk.StringVar(value="K")
    descr = {"F": "Somente arquivos", "K": "Conservar hierarquia", "R": "Recriar por lotes"}
    for idx, key in enumerate(("F", "K", "R")):
        tk.Radiobutton(
            win,
            text=f"{key} – {descr[key]}",
            variable=hier_var,
            value=key
        ).grid(row=3 + idx, column=0, columnspan=2, sticky="w", padx=10)

    # ---- intervalo ----
    tk.Label(win, text="Intervalo (min) p/ lotes:").grid(row=6, column=0, sticky="w", pady=(8, 2), padx=10)
    spin = tk.Spinbox(win, from_=1, to=1440, width=5)
    spin.grid(row=6, column=1, sticky="w")
    spin.configure(state="disabled")

    def _toggle_spin(*_):
        spin.configure(state="normal" if hier_var.get() == "R" else "disabled")
    hier_var.trace_add("write", _toggle_spin)

    # ---- botões ----
    def confirmar():
        nonlocal result
        intervalo = int(spin.get()) if hier_var.get() == "R" else None
        result = (op_var.get(), hier_var.get(), intervalo)
        win.destroy()

    def cancelar():
        win.destroy()

    btn_frame = tk.Frame(win)
    btn_frame.grid(row=7, column=0, columnspan=2, pady=10)
    tk.Button(btn_frame, text="OK", width=10, command=confirmar).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Cancelar", width=10, command=cancelar).pack(side="left", padx=5)

    win.wait_window()        # modal
    return result


# ------------------------------------------------------------------
# Utilidades de lote
# ------------------------------------------------------------------
def sha256(path: Path, buf: int = 2 ** 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def group_by_batches(files: List[Path], intervalo: int) -> List[Tuple[str, List[Path]]]:
    """
    Divide em lotes baseados na diferença de mtime.
    Retorna [(subdir, [files…]), …]
    """
    if not files:
        return []
    files_sorted = sorted(files, key=lambda p: p.stat().st_mtime)
    res: List[Tuple[str, List[Path]]] = []
    lote_files: List[Path] = []
    lote_idx = 1
    prev_time = datetime.fromtimestamp(files_sorted[0].stat().st_mtime)

    for f in files_sorted:
        cur = datetime.fromtimestamp(f.stat().st_mtime)
        if (cur - prev_time) > timedelta(minutes=intervalo) and lote_files:
            res.append((f"{prev_time.date()}_Lote{lote_idx:02d}", lote_files))
            lote_idx += 1
            lote_files = []
        lote_files.append(f)
        prev_time = cur

    if lote_files:
        res.append((f"{prev_time.date()}_Lote{lote_idx:02d}", lote_files))
    return res


# ------------------------------------------------------------------
# Worker thread
# ------------------------------------------------------------------
def copy_move_worker(tarefas: List[Tuple[Path, Path, str]], q: Queue):
    try:
        total = len(tarefas)
        q.put(("total", total))
        for idx, (src, dst, ev_type) in enumerate(tarefas, 1):
            dst.parent.mkdir(parents=True, exist_ok=True)
            if ev_type == "copy":
                shutil.copy2(src, dst)
            else:
                shutil.move(src, dst)

            sha_src = sha256(dst if ev_type == "move" else src)
            sha_dst = sha256(dst)
            registrar_evento(
                event_type=ev_type,
                object_id=str(src),
                detail={"destino": str(dst), "sha256_src": sha_src, "sha256_dst": sha_dst},
                outcome="OK" if sha_src == sha_dst else "FAIL",
            )
            q.put(("done", idx))
    except Exception as exc:
        logging.exception("Erro no worker copiar/mover")
        q.put(("error", str(exc)))


# ------------------------------------------------------------------
# Função principal
# ------------------------------------------------------------------
def run(context):
    try:
        origem = filedialog.askdirectory(title="Selecione a pasta ORIGEM")
        if not origem:
            return
        destino = filedialog.askdirectory(title="Selecione a pasta DESTINO")
        if not destino:
            return

        # diálogo de opções
        opts = perguntar_opcoes(tk._default_root)
        if not opts:
            return
        ev_type, hier, intervalo = opts

        origem_p = Path(origem)
        destino_p = Path(destino)
        files = [p for p in origem_p.rglob("*") if p.is_file()]

        tarefas: List[Tuple[Path, Path, str]] = []

        if hier == "F":
            for f in files:
                tarefas.append((f, destino_p / f.name, ev_type))
        elif hier == "K":
            for f in files:
                tarefas.append((f, destino_p / f.relative_to(origem_p), ev_type))
        else:  # R
            for subdir, lote_files in group_by_batches(files, intervalo):
                for f in lote_files:
                    tarefas.append((f, destino_p / subdir / f.name, ev_type))

        # Thread para não travar GUI
        q: Queue = Queue()
        th = threading.Thread(target=copy_move_worker, args=(tarefas, q))
        th.start()

        barra = tqdm(total=0, desc="Arquivos") if tqdm else None
        total = None
        while th.is_alive() or not q.empty():
            try:
                tipo, val = q.get(timeout=0.1)
            except Empty:
                continue
            if tipo == "total":
                total = val
                if barra:
                    barra.reset(total=total)
            elif tipo == "done" and barra:
                barra.update(1)
            elif tipo == "error":
                raise RuntimeError(val)
        th.join()
        if barra:
            barra.close()

        messagebox.showinfo("Concluído", f"Processo finalizado.\nArquivos: {total}")

    except Exception:
        logging.exception("Falha em copiar/mover")
        messagebox.showerror("Erro", "Falha na operação. Veja logs/erro.log")
