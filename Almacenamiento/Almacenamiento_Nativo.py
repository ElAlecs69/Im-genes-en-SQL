# Aplicación GUI para almacenar imágenes y audio en SQLite (BLOB)
# Versión SIN pygame

import os
import sqlite3
import io
import datetime
import tempfile
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

DB_FILENAME = os.path.join(os.path.dirname(__file__), "media.db")

# =========================
# BASE DE DATOS
# =========================

def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        data BLOB NOT NULL,
        created TIMESTAMP NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS audio (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        data BLOB NOT NULL,
        created TIMESTAMP NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# =========================
# IMÁGENES
# =========================

def save_image_bytes(name, jpeg_bytes):
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO images (name,data,created) VALUES (?,?,?)",
        (name, sqlite3.Binary(jpeg_bytes), datetime.datetime.utcnow())
    )

    conn.commit()
    conn.close()


def list_images():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute("SELECT id,name,created FROM images ORDER BY created DESC")
    rows = c.fetchall()

    conn.close()
    return rows


def get_image_blob(image_id):
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute("SELECT data FROM images WHERE id=?", (image_id,))
    row = c.fetchone()

    conn.close()
    return row[0] if row else None


def pil_image_to_jpeg_bytes(img, quality=90):

    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255,255,255))
        background.paste(img, mask=img.split()[-1])
        img = background

    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


# =========================
# AUDIO
# =========================

def save_audio_bytes(name, audio_bytes):

    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO audio (name,data,created) VALUES (?,?,?)",
        (name, sqlite3.Binary(audio_bytes), datetime.datetime.utcnow())
    )

    conn.commit()
    conn.close()


def list_audio():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute("SELECT id,name,created FROM audio ORDER BY created DESC")
    rows = c.fetchall()

    conn.close()
    return rows


def get_audio_blob(audio_id):

    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()

    c.execute("SELECT data FROM audio WHERE id=?", (audio_id,))
    row = c.fetchone()

    conn.close()
    return row[0] if row else None


# =========================
# REPRODUCIR AUDIO
# =========================

def play_audio_system(file_path):

    if sys.platform.startswith("win"):
        os.startfile(file_path)

    elif sys.platform.startswith("darwin"):
        subprocess.call(("open", file_path))

    else:
        subprocess.call(("xdg-open", file_path))


# =========================
# GUI
# =========================

class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Gestor Multimedia SQLite")
        self.geometry("1000x600")

        self.setup_ui()
        self.refresh_lists()


    def setup_ui(self):

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, width=350)
        paned.add(left, weight=1)

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill=tk.X,padx=5,pady=5)

        ttk.Button(btn_frame,text="Cargar Imagen",command=self.load_images).pack(side=tk.LEFT,padx=2)
        ttk.Button(btn_frame,text="Cargar Audio",command=self.load_audio).pack(side=tk.LEFT,padx=2)
        ttk.Button(btn_frame,text="Eliminar",command=self.delete_selected).pack(side=tk.LEFT,padx=2)
        ttk.Button(btn_frame,text="Exportar",command=self.export_selected).pack(side=tk.LEFT,padx=2)

        self.tabs = ttk.Notebook(left)
        self.tabs.pack(fill=tk.BOTH,expand=True)

        # TAB IMÁGENES
        img_frame = ttk.Frame(self.tabs)
        self.tabs.add(img_frame,text="Imágenes")

        self.tree_images = ttk.Treeview(img_frame,columns=("id","name","created"),show="headings")

        for col in ("id","name","created"):
            self.tree_images.heading(col,text=col)

        self.tree_images.pack(fill=tk.BOTH,expand=True)
        self.tree_images.bind("<<TreeviewSelect>>",self.on_image_select)

        # TAB AUDIO
        aud_frame = ttk.Frame(self.tabs)
        self.tabs.add(aud_frame,text="Audio")

        self.tree_audio = ttk.Treeview(aud_frame,columns=("id","name","created"),show="headings")

        for col in ("id","name","created"):
            self.tree_audio.heading(col,text=col)

        self.tree_audio.pack(fill=tk.BOTH,expand=True)
        self.tree_audio.bind("<<TreeviewSelect>>",self.on_audio_select)

        # PREVIEW
        right = ttk.Frame(paned)
        paned.add(right,weight=3)

        self.canvas = tk.Canvas(right,bg="#eeeeee")
        self.canvas.pack(fill=tk.BOTH,expand=True,padx=5,pady=5)

        self.status = tk.StringVar()
        ttk.Label(self,textvariable=self.status).pack(fill=tk.X)


    def set_status(self,text):
        self.status.set(text)


    def refresh_lists(self):

        for row in self.tree_images.get_children():
            self.tree_images.delete(row)

        for row in list_images():
            self.tree_images.insert("",tk.END,values=row)

        for row in self.tree_audio.get_children():
            self.tree_audio.delete(row)

        for row in list_audio():
            self.tree_audio.insert("",tk.END,values=row)


    # =========================
    # CARGAR IMÁGENES
    # =========================

    def load_images(self):

        paths = filedialog.askopenfilenames(
            filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.gif *.webp")]
        )

        for p in paths:

            img = Image.open(p)
            data = pil_image_to_jpeg_bytes(img)

            save_image_bytes(os.path.basename(p),data)

        self.refresh_lists()


    # =========================
    # CARGAR AUDIO
    # =========================

    def load_audio(self):

        paths = filedialog.askopenfilenames(
            filetypes=[("Audio","*.wav *.mp3 *.ogg *.flac *.aac *.m4a")]
        )

        for p in paths:

            with open(p,"rb") as f:
                data = f.read()

            save_audio_bytes(os.path.basename(p),data)

        self.refresh_lists()


    # =========================
    # PREVIEW IMAGEN
    # =========================

    def on_image_select(self,event):

        sel = self.tree_images.selection()

        if not sel:
            return

        item = self.tree_images.item(sel[0])
        image_id = item["values"][0]

        blob = get_image_blob(image_id)

        img = Image.open(io.BytesIO(blob))
        img.thumbnail((600,500))

        self.tk_img = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(300,250,image=self.tk_img)


    # =========================
    # REPRODUCIR AUDIO
    # =========================

    def on_audio_select(self,event):

        sel = self.tree_audio.selection()

        if not sel:
            return

        item = self.tree_audio.item(sel[0])
        audio_id = item["values"][0]

        data = get_audio_blob(audio_id)

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(data)
        tmp.close()

        play_audio_system(tmp.name)

        self.set_status("Reproduciendo audio")


    # =========================
    # ELIMINAR
    # =========================

    def delete_selected(self):

        tab = self.tabs.index(self.tabs.select())

        if tab == 0:

            sel = self.tree_images.selection()
            if not sel: return

            id_ = self.tree_images.item(sel[0])["values"][0]

            conn = sqlite3.connect(DB_FILENAME)
            c = conn.cursor()
            c.execute("DELETE FROM images WHERE id=?", (id_,))
            conn.commit()
            conn.close()

        else:

            sel = self.tree_audio.selection()
            if not sel: return

            id_ = self.tree_audio.item(sel[0])["values"][0]

            conn = sqlite3.connect(DB_FILENAME)
            c = conn.cursor()
            c.execute("DELETE FROM audio WHERE id=?", (id_,))
            conn.commit()
            conn.close()

        self.refresh_lists()


    # =========================
    # EXPORTAR
    # =========================

    def export_selected(self):

        tab = self.tabs.index(self.tabs.select())

        if tab == 0:

            sel = self.tree_images.selection()
            if not sel: return

            item = self.tree_images.item(sel[0])
            blob = get_image_blob(item["values"][0])

        else:

            sel = self.tree_audio.selection()
            if not sel: return

            item = self.tree_audio.item(sel[0])
            blob = get_audio_blob(item["values"][0])

        path = filedialog.asksaveasfilename(initialfile=item["values"][1])

        if not path:
            return

        with open(path,"wb") as f:
            f.write(blob)


if __name__ == "__main__":

    init_db()

    app = App()
    app.mainloop()
