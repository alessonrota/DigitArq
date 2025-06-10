# """
# Plugin: Conversão – imagens/PDF → PDF   (sem parâmetro CSV)
# -----------------------------------------------------------
# • Copiar/mover não tem mais CSV.
# • Escolhas: PDF único × múltiplos  |  Compactar (pikepdf).
# """

# from __future__ import annotations
# import csv, hashlib, threading
# from pathlib import Path
# from queue import Queue, Empty
# from datetime import datetime
# from typing import Dict, List, Tuple, Optional

# import tkinter as tk
# from tkinter import filedialog, messagebox

# from digitarq.premis_logger import registrar_evento
# from digitarq.erro import logging

# # dependências opcionais
# try:
#     from PIL import Image
# except ImportError:
#     Image = None
# try:
#     from PyPDF2 import PdfMerger
# except ImportError:
#     PdfMerger = None
# try:
#     import pikepdf
# except ImportError:
#     pikepdf = None
# try:
#     from tqdm import tqdm
# except ImportError:
#     tqdm = None

# # ------------------------------------------------------------------
# # Barra & utilidades
# # ------------------------------------------------------------------
# def sha256(path: Path, buf: int = 2**20) -> str:
#     h = hashlib.sha256()
#     with path.open("rb") as f:
#         while chunk := f.read(buf):
#             h.update(chunk)
#     return h.hexdigest()

# def premis_ok(src: Path, dst: Path, detail: Dict):
#     registrar_evento("convert", str(src), {"destino": str(dst), **detail}, "OK")

# # ------------------------------------------------------------------
# # Diálogo de opções
# # ------------------------------------------------------------------
# def pedir_opcoes(master: tk.Tk) -> Optional[Dict]:
#     win = tk.Toplevel(master); win.title("Opções de conversão"); win.grab_set(); win.resizable(False, False)

#     var_unico = tk.BooleanVar(value=True)
#     var_comp  = tk.BooleanVar(value=bool(pikepdf))

#     tk.Checkbutton(win, text="Gerar PDF único", variable=var_unico)\
#         .grid(row=0, column=0, sticky="w", padx=10, pady=5)
#     tk.Checkbutton(
#         win, text="Compactar PDF (requer pikepdf)",
#         variable=var_comp, state="normal" if pikepdf else "disabled"
#     ).grid(row=1, column=0, sticky="w", padx=10, pady=5)

#     resultado: Dict|None = None
#     def ok():
#         nonlocal resultado
#         resultado = {"pdf_unico": var_unico.get(), "compactar": var_comp.get()}
#         win.destroy()
#     def cancelar(): win.destroy()

#     tk.Button(win, text="OK", width=12, command=ok).grid(row=2, column=0, pady=8, padx=5, sticky="e")
#     tk.Button(win, text="Cancelar", width=12, command=cancelar).grid(row=2, column=0, pady=8, padx=5, sticky="w")

#     win.wait_window()
#     return resultado

# # ------------------------------------------------------------------
# # Worker thread
# # ------------------------------------------------------------------
# def worker(tarefas: List[Tuple[Path, Path]], pdf_unico: bool, compactar: bool, q: Queue):
#     try:
#         total = len(tarefas)
#         q.put(("total", total))

#         merger = PdfMerger() if (pdf_unico and PdfMerger) else None
#         for idx, (src, dst) in enumerate(tarefas, 1):
#             dst.parent.mkdir(parents=True, exist_ok=True)

#             # --- Imagem → PDF --------------------------------------------------
#             if Image and src.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}:
#                 tmp_pdf = dst if not pdf_unico else dst.with_suffix(".tmp.pdf")
#                 with Image.open(src) as im:
#                     im.convert("RGB").save(tmp_pdf, "PDF", resolution=100)
#             # --- PDF já pronto --------------------------------------------------
#             elif src.suffix.lower() == ".pdf":
#                 if not pdf_unico:
#                     shutil.copy2(src, dst)
#                 tmp_pdf = src
#             else:
#                 logging.warning("Não suportado: %s", src)
#                 q.put(("done", idx)); continue

#             premis_ok(src, dst, {"sha256_src": sha256(src), "tipo": src.suffix})
#             if pdf_unico and merger:
#                 merger.append(str(tmp_pdf))
#             q.put(("done", idx))

#         # PDF único final
#         if pdf_unico and merger:
#             final_pdf = tarefas[0][1].parent / "documento_unico.pdf"
#             merger.write(final_pdf); merger.close()
#             if compactar and pikepdf:
#                 _compactar_pdf(final_pdf)
#         q.put(("fim", 0))
#     except Exception as e:
#         logging.exception("Erro na conversão")
#         q.put(("erro", str(e)))

# def _compactar_pdf(pdf: Path):
#     try:
#         with pikepdf.open(pdf) as pdf_in:
#             pdf_in.save(pdf.with_suffix(".compact.pdf"), optimize_streams=True)
#             pdf.rename(pdf.with_suffix(".backup.pdf"))
#             pdf.with_suffix(".compact.pdf").rename(pdf)
#     except Exception:
#         logging.exception("Falha compactando PDF")

# # ------------------------------------------------------------------
# # Função principal
# # ------------------------------------------------------------------
# def run(context):
#     root = tk._default_root or tk.Tk()

#     # 1) selecionar pastas
#     origem = filedialog.askdirectory(title="Pasta de origem (imagens / PDFs)")
#     if not origem:
#         return
#     destino = filedialog.askdirectory(title="Pasta destino dos PDFs")
#     if not destino:
#         return

#     # 2) opções
#     opts = pedir_opcoes(root)
#     if not opts:
#         return
#     pdf_unico, compactar = opts["pdf_unico"], opts["compactar"]

#     # 3) montar lista de tarefas
#     origem_p, destino_p = Path(origem), Path(destino)
#     arquivos = [p for p in origem_p.rglob("*") if p.suffix.lower() in
#                 {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".pdf"}]
#     if not arquivos:
#         messagebox.showwarning("Aviso", "Nenhum arquivo suportado encontrado."); return

#     tarefas = []
#     for f in arquivos:
#         dst = destino_p / (f.stem + ".pdf") if not pdf_unico else destino_p / f.name
#         tarefas.append((f, dst))

#     # 4) thread + barra
#     q: Queue = Queue()
#     th = threading.Thread(target=worker, args=(tarefas, pdf_unico, compactar, q))
#     th.start()

#     bar = tqdm(total=len(tarefas), desc="Convertendo") if tqdm else None
#     while th.is_alive() or not q.empty():
#         try:
#             typ, _ = q.get(timeout=0.1)
#         except Empty:
#             continue
#         if typ == "done" and bar:
#             bar.update(1)
#         elif typ == "erro":
#             messagebox.showerror("Erro na conversão", _)
#     if bar:
#         bar.close()
#     messagebox.showinfo("Concluído", "Conversão finalizada.")


# SEGUNDA VERSÃO

# """
# Plugin: Conversão – imagens/PDF → PDF   (sem CSV, com compressão configurável)
# ------------------------------------------------------------------------------
# Fluxo:
#   1. Usuário escolhe pasta origem e destino.
#   2. Caixa de opções:
#        • PDF único ou múltiplos PDFs
#        • Compactar (se pikepdf) + Qualidade JPEG (30-95)
#   3. Conversão em thread, PREMIS por arquivo, barra de progresso console.
# """

# from __future__ import annotations
# import threading, hashlib, shutil
# from datetime import datetime
# from pathlib import Path
# from queue import Queue, Empty
# from typing import List, Tuple, Optional, Dict

# import tkinter as tk
# from tkinter import filedialog, messagebox

# from digitarq.premis_logger import registrar_evento
# from digitarq.erro import logging

# # bibliotecas opcionais
# try:
#     from PIL import Image
# except ImportError:
#     Image = None
# try:
#     from PyPDF2 import PdfMerger
# except ImportError:
#     PdfMerger = None
# try:
#     import pikepdf
#     from pikepdf import ImageSettings, ImageCompression
# except ImportError:
#     pikepdf = None
# try:
#     from tqdm import tqdm
# except ImportError:
#     tqdm = None


# # -----------------------------------------------------------------
# # Utilidades
# # -----------------------------------------------------------------
# SUP_IMGS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
# SUP_PDFS = {".pdf"}


# def sha256(path: Path, buf: int = 2**20) -> str:
#     h = hashlib.sha256()
#     with path.open("rb") as f:
#         while chunk := f.read(buf):
#             h.update(chunk)
#     return h.hexdigest()


# def premis_convert(src: Path, dst: Path, extra: Dict):
#     registrar_evento(
#         event_type="convert",
#         object_id=str(src),
#         detail={"destino": str(dst), **extra},
#     )


# # -----------------------------------------------------------------
# # Diálogo de opções
# # -----------------------------------------------------------------
# def dialog_opcoes(master: tk.Tk) -> Optional[Dict]:
#     win = tk.Toplevel(master)
#     win.title("Opções de conversão")
#     win.grab_set(); win.resizable(False, False)

#     var_unico = tk.BooleanVar(value=True)
#     var_comp = tk.BooleanVar(value=bool(pikepdf))
#     qual_val = tk.IntVar(value=75)

#     tk.Checkbutton(win, text="Gerar PDF único", variable=var_unico)\
#         .grid(row=0, column=0, sticky="w", padx=10, pady=4)

#     tk.Checkbutton(win, text="Compactar PDF (requer pikepdf)",
#                    variable=var_comp,
#                    state="normal" if pikepdf else "disabled")\
#         .grid(row=1, column=0, sticky="w", padx=10, pady=4)

#     tk.Label(win, text="Qualidade JPEG (30-95)").grid(row=2, column=0, sticky="w", padx=10)
#     qual = tk.Scale(win, from_=30, to=95, orient="horizontal", variable=qual_val,
#                     state="normal" if pikepdf else "disabled")
#     qual.grid(row=3, column=0, padx=10, pady=4, sticky="we")

#     def on_comp_change(*_):
#         qual.configure(state="normal" if var_comp.get() and pikepdf else "disabled")
#     var_comp.trace_add("write", on_comp_change)

#     res: Dict | None = None

#     def ok():
#         nonlocal res
#         res = {
#             "pdf_unico": var_unico.get(),
#             "compactar": var_comp.get(),
#             "qualidade": qual_val.get(),
#         }
#         win.destroy()

#     def cancelar(): win.destroy()

#     btnf = tk.Frame(win); btnf.grid(row=4, column=0, pady=8)
#     tk.Button(btnf, text="OK", width=10, command=ok).pack(side="left", padx=5)
#     tk.Button(btnf, text="Cancelar", width=10, command=cancelar).pack(side="left", padx=5)

#     win.wait_window()
#     return res


# # -----------------------------------------------------------------
# # Worker
# # -----------------------------------------------------------------
# def worker(tarefas: List[Tuple[Path, Path]], pdf_unico: bool,
#            compactar: bool, jpeg_q: int, q: Queue):
#     try:
#         total = len(tarefas)
#         q.put(("total", total))

#         merger = PdfMerger() if (pdf_unico and PdfMerger) else None

#         for idx, (src, dst) in enumerate(tarefas, 1):
#             dst.parent.mkdir(parents=True, exist_ok=True)

#             # ------- imagem -------
#             if src.suffix.lower() in SUP_IMGS and Image:
#                 tmp = dst if not pdf_unico else dst.with_suffix(".tmp.pdf")
#                 with Image.open(src) as im:
#                     im.convert("RGB").save(tmp, "PDF", resolution=100)

#             # ------- pdf ----------
#             elif src.suffix.lower() in SUP_PDFS:
#                 tmp = src
#                 if not pdf_unico:
#                     shutil.copy2(src, dst)
#             else:
#                 logging.warning("Formato não suportado: %s", src)
#                 q.put(("done", idx)); continue

#             premis_convert(src, dst, {"sha256_src": sha256(src), "tipo": src.suffix})
#             if pdf_unico and merger:
#                 merger.append(str(tmp))
#             q.put(("done", idx))

#         # **gera PDF único**
#         if pdf_unico and merger:
#             final_pdf = tarefas[0][1].parent / "documento_unico.pdf"
#             merger.write(final_pdf); merger.close()

#             if compactar and pikepdf:
#                 _compactar(final_pdf, jpeg_q)

#         q.put(("fim", 0))
#     except Exception as exc:
#         logging.exception("Erro na conversão")
#         q.put(("erro", str(exc)))


# def _compactar(pdf_path: Path, qualidade: int):
#     try:
#         iset = ImageSettings(
#             compression=ImageCompression.jpeg,
#             quality=qualidade,
#             transparency=False,
#         )
#         tmp = pdf_path.with_suffix(".tmp.pdf")
#         with pikepdf.open(pdf_path) as pdf:
#             pdf.save(tmp, optimize_streams=True, image_settings=iset)
#         pdf_path.unlink(missing_ok=True)
#         tmp.rename(pdf_path)
#     except Exception:
#         logging.exception("Falha ao compactar PDF")


# # -----------------------------------------------------------------
# # run()
# # -----------------------------------------------------------------
# def run(context):
#     root = tk._default_root or tk.Tk()

#     # Selecionar pastas
#     origem_dir = filedialog.askdirectory(title="Pasta de origem (imagens / PDFs)")
#     if not origem_dir:
#         return
#     destino_dir = filedialog.askdirectory(title="Pasta destino dos PDFs")
#     if not destino_dir:
#         return

#     # Opções
#     opts = dialog_opcoes(root)
#     if not opts:
#         return
#     pdf_unico, compactar, qualidade = opts.values()

#     # Arquivos
#     origem = Path(origem_dir)
#     destino = Path(destino_dir)
#     arquivos = [p for p in origem.rglob("*") if p.suffix.lower() in SUP_IMGS | SUP_PDFS]
#     if not arquivos:
#         messagebox.showwarning("Aviso", "Nenhum arquivo suportado encontrado."); return

#     tarefas = [(f, destino / (f.stem + ".pdf") if not pdf_unico else destino / f.name)
#                for f in arquivos]

#     q: Queue = Queue()
#     th = threading.Thread(target=worker,
#                           args=(tarefas, pdf_unico, compactar, qualidade, q))
#     th.start()

#     bar = tqdm(total=len(tarefas), desc="Convertendo") if tqdm else None
#     while th.is_alive() or not q.empty():
#         try:
#             typ, val = q.get(timeout=0.1)
#         except Empty:
#             continue
#         if typ == "done" and bar:
#             bar.update(1)
#         elif typ == "erro":
#             messagebox.showerror("Erro", val)
#             break
#     if bar: bar.close()
#     messagebox.showinfo("Concluído", "Conversão finalizada.")


#TERCEIRA VERSÃO
"""
Plugin: Conversão – imagens/PDF → PDF (sem CSV, com compressão configurável)
-------------------------------------------------------------------------------
• Pasta origem e destino escolhidas pelo usuário
• Opções: PDF único × múltiplos  |  Compactar (pikepdf) + Qualidade JPEG
• Thread para não travar a GUI, barra tqdm no console
• Eventos PREMIS por arquivo convertido
"""

from __future__ import annotations
import hashlib, shutil, threading
from pathlib import Path
from queue import Queue, Empty
from typing import List, Tuple, Optional, Dict

import tkinter as tk
from tkinter import filedialog, messagebox

from digitarq.premis_logger import registrar_evento
from digitarq.erro import logging

# bibliotecas opcionais
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from PyPDF2 import PdfMerger
except ImportError:
    PdfMerger = None
try:
    import pikepdf
    from pikepdf import ImageSettings, ImageCompression
except ImportError:
    pikepdf = None
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# -----------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------
SUP_IMGS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
SUP_PDFS = {".pdf"}


def sha256(path: Path, buf: int = 2**20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def premis_convert(src: Path, dst: Path, extra: Dict):
    registrar_evento(
        event_type="convert",
        object_id=str(src),
        detail={"destino": str(dst), **extra},
    )


# -----------------------------------------------------------------
# Diálogo de opções
# -----------------------------------------------------------------
def dialog_opcoes(master: tk.Tk) -> Optional[Dict]:
    win = tk.Toplevel(master)
    win.title("Opções de conversão")
    win.grab_set()
    win.resizable(False, False)

    var_unico = tk.BooleanVar(value=True)
    var_comp = tk.BooleanVar(value=bool(pikepdf))
    qual_val = tk.IntVar(value=75)

    tk.Checkbutton(win, text="Gerar PDF único", variable=var_unico)\
        .grid(row=0, column=0, sticky="w", padx=10, pady=4)
    tk.Checkbutton(
        win, text="Compactar PDF (requer pikepdf)",
        variable=var_comp,
        state="normal" if pikepdf else "disabled",
    ).grid(row=1, column=0, sticky="w", padx=10, pady=4)

    tk.Label(win, text="Qualidade JPEG (30-95)").grid(row=2, column=0, sticky="w", padx=10)
    qual = tk.Scale(
        win, from_=30, to=95, orient="horizontal", variable=qual_val,
        state="normal" if pikepdf else "disabled",
    )
    qual.grid(row=3, column=0, padx=10, pady=4, sticky="we")

    def _toggle(*_):
        qual.configure(state="normal" if var_comp.get() and pikepdf else "disabled")
    var_comp.trace_add("write", _toggle)

    res: Optional[Dict] = None

    def ok():
        nonlocal res
        res = {
            "pdf_unico": var_unico.get(),
            "compactar": var_comp.get(),
            "qualidade": qual_val.get(),
        }
        win.destroy()

    tk.Frame(win).grid(row=4, column=0, pady=8)  # espaçador
    tk.Button(win, text="Cancelar", width=10, command=win.destroy)\
        .grid(row=5, column=0, sticky="w", padx=10, pady=6)
    tk.Button(win, text="OK", width=10, command=ok)\
        .grid(row=5, column=0, sticky="e", padx=10, pady=6)

    win.wait_window()
    return res


# -----------------------------------------------------------------
# Worker thread
# -----------------------------------------------------------------
def worker(tarefas: List[Tuple[Path, Path]], pdf_unico: bool,
           compactar: bool, jpeg_q: int, q: Queue):
    try:
        total = len(tarefas)
        q.put(("total", total))

        merger = PdfMerger() if (pdf_unico and PdfMerger) else None

        for idx, (src, dst) in enumerate(tarefas, 1):
            dst.parent.mkdir(parents=True, exist_ok=True)

            # imagem
            if Image and src.suffix.lower() in SUP_IMGS:
                tmp = dst if not pdf_unico else dst.with_suffix(".tmp.pdf")
                with Image.open(src) as im:
                    im.convert("RGB").save(tmp, "PDF", resolution=100)

            # pdf
            elif src.suffix.lower() in SUP_PDFS:
                tmp = src
                if not pdf_unico:
                    shutil.copy2(src, dst)
            else:
                logging.warning("Formato não suportado: %s", src)
                q.put(("done", idx)); continue

            premis_convert(src, dst, {"sha256_src": sha256(src), "tipo": src.suffix})
            if pdf_unico and merger:
                merger.append(str(tmp))
            q.put(("done", idx))

        # único
        if pdf_unico and merger:
            final_pdf = tarefas[0][1].parent / "documento_unico.pdf"
            merger.write(final_pdf); merger.close()
            if compactar and pikepdf:
                _compactar(final_pdf, jpeg_q)

        q.put(("fim", 0))
    except Exception as exc:
        logging.exception("Erro na conversão")
        q.put(("erro", str(exc)))


def _compactar(pdf_path: Path, qualidade: int):
    try:
        iset = ImageSettings(
            compression=ImageCompression.jpeg,
            quality=qualidade,
            transparency=False,
        )
        tmp = pdf_path.with_suffix(".tmp.pdf")
        with pikepdf.open(pdf_path) as pdf:
            pdf.save(tmp, optimize_streams=True, image_settings=iset)
        pdf_path.unlink(missing_ok=True)
        tmp.rename(pdf_path)
    except Exception:
        logging.exception("Falha ao compactar PDF")


# -----------------------------------------------------------------
# run()
# -----------------------------------------------------------------
def run(context):
    root = tk._default_root or tk.Tk()

    origem_dir = filedialog.askdirectory(title="Pasta de origem (imagens / PDFs)")
    if not origem_dir:
        return
    destino_dir = filedialog.askdirectory(title="Pasta destino dos PDFs")
    if not destino_dir:
        return

    opts = dialog_opcoes(root)
    if not opts:
        return
    pdf_unico, compactar, qualidade = opts.values()

    origem = Path(origem_dir)
    destino = Path(destino_dir)
    arquivos = [p for p in origem.rglob("*")
                if p.suffix.lower() in SUP_IMGS | SUP_PDFS]
    if not arquivos:
        messagebox.showwarning("Aviso", "Nenhum arquivo suportado encontrado.")
        return

    tarefas = [
        (f, destino / (f.stem + ".pdf") if not pdf_unico else destino / f.name)
        for f in arquivos
    ]

    q: Queue = Queue()
    th = threading.Thread(target=worker,
                          args=(tarefas, pdf_unico, compactar, qualidade, q))
    th.start()

    bar = tqdm(total=len(tarefas), desc="Convertendo") if tqdm else None
    while th.is_alive() or not q.empty():
        try:
            typ, val = q.get(timeout=0.1)
        except Empty:
            continue
        if typ == "done" and bar:
            bar.update(1)
        elif typ == "erro":
            messagebox.showerror("Erro", val)
            break
    if bar:
        bar.close()
    messagebox.showinfo("Concluído", "Conversão finalizada.")
