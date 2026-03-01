# empty
"""
Aplicación GUI para almacenar imágenes de forma nativa (BLOB) en SQLite.
"""

import os
import sqlite3
import io
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
	from PIL import Image, ImageTk
except Exception as e:
	raise RuntimeError("Pillow no está instalado. Instálalo con: pip install pillow") from e


DB_FILENAME = os.path.join(os.path.dirname(__file__), "images.db")


def init_db():
	conn = sqlite3.connect(DB_FILENAME)
	c = conn.cursor()
	c.execute(
		"""
		CREATE TABLE IF NOT EXISTS images (
			id INTEGER PRIMARY KEY,
			name TEXT NOT NULL,
			data BLOB NOT NULL,
			created TIMESTAMP NOT NULL
		)
		"""
	)
	conn.commit()
	conn.close()


def save_image_bytes(name: str, jpeg_bytes: bytes):
	conn = sqlite3.connect(DB_FILENAME)
	c = conn.cursor()
	c.execute(
		"INSERT INTO images (name, data, created) VALUES (?, ?, ?)",
		(name, sqlite3.Binary(jpeg_bytes), datetime.datetime.utcnow()),
	)
	conn.commit()
	conn.close()


def list_images():
	conn = sqlite3.connect(DB_FILENAME)
	c = conn.cursor()
	c.execute("SELECT id, name, created FROM images ORDER BY created DESC")
	rows = c.fetchall()
	conn.close()
	return rows


def get_image_blob(image_id: int) -> bytes:
	conn = sqlite3.connect(DB_FILENAME)
	c = conn.cursor()
	c.execute("SELECT data FROM images WHERE id = ?", (image_id,))
	row = c.fetchone()
	conn.close()
	return row[0] if row else None


def pil_image_to_jpeg_bytes(img: Image.Image, quality=85) -> bytes:
	# Convert to RGB if needed
	if img.mode in ("RGBA", "LA"):
		background = Image.new("RGB", img.size, (255, 255, 255))
		background.paste(img, mask=img.split()[-1])
		img = background
	elif img.mode != "RGB":
		img = img.convert("RGB")

	buf = io.BytesIO()
	img.save(buf, format="JPEG", quality=quality)
	return buf.getvalue()


class App(tk.Tk):
	def __init__(self):
		super().__init__()
		self.title("Almacenamiento Nativo de Imágenes")
		self.geometry("900x600")

		self.setup_ui()
		self.refresh_list()

	def setup_ui(self):
		paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
		paned.pack(fill=tk.BOTH, expand=True)

		# Left: explorer
		left = ttk.Frame(paned, width=300)
		paned.add(left, weight=1)

		btn_frame = ttk.Frame(left)
		btn_frame.pack(fill=tk.X, padx=6, pady=6)

		load_btn = ttk.Button(btn_frame, text="Cargar imagen(es)", command=self.load_images)
		load_btn.pack(side=tk.LEFT, padx=2)

		del_btn = ttk.Button(btn_frame, text="Eliminar seleccionado", command=self.delete_selected)
		del_btn.pack(side=tk.LEFT, padx=2)

		export_btn = ttk.Button(btn_frame, text="Exportar seleccionado", command=self.export_selected)
		export_btn.pack(side=tk.LEFT, padx=2)

		# Treeview
		columns = ("id", "name", "created")
		self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
		self.tree.heading("id", text="ID")
		self.tree.heading("name", text="Nombre")
		self.tree.heading("created", text="Creado")
		self.tree.column("id", width=50, anchor=tk.CENTER)
		self.tree.column("name", width=180, anchor=tk.W)
		self.tree.column("created", width=120, anchor=tk.CENTER)
		self.tree.bind("<<TreeviewSelect>>", self.on_select)
		self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

		# Right: preview
		right = ttk.Frame(paned)
		paned.add(right, weight=3)

		self.preview_label = ttk.Label(right, text="Selecciona una imagen para previsualizar")
		self.preview_label.pack(padx=6, pady=6)

		self.canvas = tk.Canvas(right, bg="#f0f0f0")
		self.canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

		# Status
		self.status_var = tk.StringVar()
		self.status_var.set("Listo")
		status = ttk.Label(self, textvariable=self.status_var, anchor=tk.W)
		status.pack(fill=tk.X)

	def set_status(self, text: str):
		self.status_var.set(text)

	def refresh_list(self):
		for row in self.tree.get_children():
			self.tree.delete(row)
		rows = list_images()
		for r in rows:
			id_, name, created = r
			created_str = created if isinstance(created, str) else str(created)
			self.tree.insert("", tk.END, values=(id_, name, created_str))

	def load_images(self):
		paths = filedialog.askopenfilenames(
			title="Seleccionar imagen(es)",
			filetypes=[("Imágenes", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.tiff;*.webp"), ("Todos", "*")],
		)
		if not paths:
			return
		count = 0
		for p in paths:
			try:
				img = Image.open(p)
				jpeg_bytes = pil_image_to_jpeg_bytes(img, quality=90)  # usar algoritmo JPG
				name = os.path.basename(p)
				save_image_bytes(name, jpeg_bytes)
				count += 1
			except Exception as e:
				messagebox.showerror("Error", f"No se pudo cargar {p}: {e}")
		self.set_status(f"Cargadas {count} imagen(es)")
		self.refresh_list()

	def on_select(self, event=None):
		sel = self.tree.selection()
		if not sel:
			return
		item = self.tree.item(sel[0])
		image_id = item["values"][0]
		blob = get_image_blob(image_id)
		if not blob:
			messagebox.showwarning("Advertencia", "No se encontraron datos para la imagen seleccionada")
			return
		try:
			buf = io.BytesIO(blob)
			img = Image.open(buf)
			self.show_image_on_canvas(img)
			self.set_status(f"Mostrando: {item['values'][1]}")
		except Exception as e:
			messagebox.showerror("Error", f"No se pudo reconstruir la imagen: {e}")

	def show_image_on_canvas(self, pil_img: Image.Image):
		# Fit image into canvas while keeping aspect ratio
		self.canvas.delete("all")
		cw = self.canvas.winfo_width() or 400
		ch = self.canvas.winfo_height() or 300
		img_w, img_h = pil_img.size
		ratio = min(cw / img_w, ch / img_h, 1)
		new_w = int(img_w * ratio)
		new_h = int(img_h * ratio)
		disp = pil_img.resize((new_w, new_h), Image.LANCZOS)
		self.tk_img = ImageTk.PhotoImage(disp)
		self.canvas.create_image(cw // 2, ch // 2, image=self.tk_img, anchor=tk.CENTER)

	def delete_selected(self):
		sel = self.tree.selection()
		if not sel:
			return
		item = self.tree.item(sel[0])
		image_id = item["values"][0]
		if not messagebox.askyesno("Confirmar", "¿Eliminar la imagen seleccionada?"):
			return
		conn = sqlite3.connect(DB_FILENAME)
		c = conn.cursor()
		c.execute("DELETE FROM images WHERE id = ?", (image_id,))
		conn.commit()
		conn.close()
		self.set_status("Imagen eliminada")
		self.refresh_list()
		self.canvas.delete("all")

	def export_selected(self):
		sel = self.tree.selection()
		if not sel:
			return
		item = self.tree.item(sel[0])
		image_id = item["values"][0]
		name = item["values"][1]
		blob = get_image_blob(image_id)
		if not blob:
			messagebox.showwarning("Advertencia", "No se encontraron datos para la imagen seleccionada")
			return
		path = filedialog.asksaveasfilename(defaultextension=".jpg", initialfile=name)
		if not path:
			return
		try:
			with open(path, "wb") as f:
				f.write(blob)
			self.set_status(f"Exportada: {os.path.basename(path)}")
		except Exception as e:
			messagebox.showerror("Error", f"No se pudo exportar: {e}")


if __name__ == "__main__":
	init_db()
	app = App()
	app.mainloop()

