"""
Plugin: Relatório de Arquivos
-----------------------------
* Percorre pasta escolhida e coleta metadados:
    caminho, nome, extensão, tamanho, criação, modificação,
    SHA-256, MIME (opcional), duplicado?, corrompido?
* Exibe resultados em Tabela (Treeview) + botão Exportar CSV.
* Evento PREMIS eventType="report" por arquivo.
"""

from __future__ import annotations
import csv, hashlib, threading, mimetypes
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, List, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from digitarq.premis_logger import registrar_evento
from digitarq.erro import logging

# opcionais
try:
    import magic             # python-magic
except ImportError:
    magic = None
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def sha256(path: Path, buf: int = 2**20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def try_open(path: Path) -> bool:
    """Retorna True se conseguir abrir imagem/PDF; False ⇒ possivelmente corrompido."""
    try:
        if Image and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
            with Image.open(path) as im:
                im.verify()
            return True
        if PdfReader and path.suffix.lower() == ".pdf":
            PdfReader(str(path))
            return True
    except Exception:
        return False
    return True  # outros tipos assumidos OK


def premis_report(path: Path, info: Dict):
    registrar_evento(
        event_type="report",
        object_id=str(path),
        detail=info,
        outcome="OK",
    )


# ------------------------------------------------------------------
# Worker Thread
# ------------------------------------------------------------------
def worker(base: Path, q: Queue):
    try:
        files = [p for p in base.rglob("*") if p.is_file()]
        total = len(files)
        q.put(("total", total))

        hashes: Dict[str, Path] = {}
        for idx, f in enumerate(files, 1):
            st = f.stat()
            sha = sha256(f)
            duplicado = sha in hashes
            hashes.setdefault(sha, f)

            mime = (magic.from_file(str(f), mime=True) if magic else
                    mimetypes.guess_type(f.name)[0] or "?" )

            corrompido = not try_open(f)

            info = {
                "caminho": str(f),
                "nome": f.name,
                "ext": f.suffix.lower(),
                "tamanho": st.st_size,
                "criado": datetime.fromtimestamp(st.st_ctime).isoformat(sep=" ", timespec="seconds"),
                "modificado": datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds"),
                "sha256": sha,
                "mime": mime,
                "duplicado": duplicado,
                "corrompido": corrompido,
            }
            premis_report(f, info)
            q.put(("row", info))
            q.put(("done", idx))
        q.put(("fim", None))
    except Exception as exc:
        logging.exception("Erro no relatório"); q.put(("erro", str(exc)))


# ------------------------------------------------------------------
# UI – Tabela + export
# ------------------------------------------------------------------
class Tabela(tk.Toplevel):
    def __init__(self, master: tk.Tk, rows: List[Dict]):
        super().__init__(master)
        self.title("Relatório de Arquivos")
        self.geometry("1200x600")

        cols = ["caminho","tamanho","sha256","duplicado","corrompido"]
        tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=250 if c=="caminho" else 120, anchor="w")
        vsb = ttk.Scrollbar(self, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1); self.columnconfigure(0, weight=1)

        for row in rows:
            tree.insert("", "end", values=[row[c] for c in cols])

        def export_csv():
            p = filedialog.asksaveasfilename(
                title="Salvar CSV", defaultextension=".csv",
                filetypes=[("CSV","*.csv")])
            if not p: return
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow([r[c] for c in cols])
            messagebox.showinfo("Exportado", f"CSV salvo em:\n{p}")

        tk.Button(self, text="Exportar CSV", command=export_csv)\
            .grid(row=1, column=0, pady=6, sticky="e")


# ------------------------------------------------------------------
# run()
# ------------------------------------------------------------------
def run(context):
    root = tk._default_root or tk.Tk()
    pasta = filedialog.askdirectory(title="Pasta base para relatório")
    if not pasta:
        return
    base = Path(pasta)

    q: Queue = Queue()
    th = threading.Thread(target=worker, args=(base, q))
    th.start()

    rows: List[Dict] = []
    bar = tqdm(desc="Analisando", total=0) if tqdm else None

    while th.is_alive() or not q.empty():
        try:
            typ, val = q.get(timeout=0.1)
        except Empty:
            continue
        if typ == "total" and bar:
            bar.reset(total=val)
        elif typ == "done" and bar:
            bar.update(1)
        elif typ == "row":
            rows.append(val)
        elif typ == "erro":
            messagebox.showerror("Erro", val)
            if bar: bar.close(); return
    if bar: bar.close()

    # mostra tabela
    Tabela(root, rows)
