import customtkinter as ctk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

# --- Configuración Visual ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

BG_COLOR = "#0F0D0B"
CARD_COLOR = "#1C1814"
TEXT_COLOR = "#F0EDE6"
ACCENT_GREEN = "#5ECFA0"
ACCENT_ORANGE = "#F5A56C"
ACCENT_RED = "#E57373"

DB_FILE = "montana_club.db"

# --- Lógica de Base de Datos ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Migración: Productos (Costo y Precio Venta)
        cursor.execute("PRAGMA table_info(productos)")
        columnas_prod = [info[1] for info in cursor.fetchall()]
        if 'precio' in columnas_prod and 'precio_venta' not in columnas_prod:
            cursor.execute("ALTER TABLE productos RENAME COLUMN precio TO costo")
            cursor.execute("ALTER TABLE productos ADD COLUMN precio_venta REAL NOT NULL DEFAULT 0")
            cursor.execute("UPDATE productos SET precio_venta = costo") 
            
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id TEXT PRIMARY KEY, nombre TEXT UNIQUE NOT NULL,
                costo REAL NOT NULL, precio_venta REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        # Migración: Ventas (Agregar Costo Total para calcular Ganancia)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas (
                id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
                producto_nombre TEXT NOT NULL, cantidad INTEGER NOT NULL,
                precio_unitario REAL NOT NULL, total REAL NOT NULL,
                metodo_pago TEXT NOT NULL
            )
        ''')
        cursor.execute("PRAGMA table_info(ventas)")
        columnas_ventas = [info[1] for info in cursor.fetchall()]
        if 'costo_total' not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN costo_total REAL NOT NULL DEFAULT 0")
            cursor.execute('''
                UPDATE ventas
                SET costo_total = cantidad * IFNULL((SELECT costo FROM productos WHERE productos.nombre = ventas.producto_nombre), 0)
                WHERE costo_total = 0
            ''')
        
        cursor.execute("SELECT COUNT(*) FROM productos")
        if cursor.fetchone()[0] == 0:
            catalogo_inicial = [
                ("P001", "Red 750ml", 15000, 27500, 24), ("P002", "Black 750ml", 25000, 47000, 12),
                ("P003", "Gold 750ml", 40000, 72000, 8), ("P004", "Federico Alvear", 2000, 4300, 36),
                ("P006", "Chandon 750ml", 8000, 15000, 18), ("P008", "Sky Regular", 4000, 7500, 25),
                ("P013", "Coca Cola 1.75L", 1500, 3200, 48), ("P015", "Speed 269ml", 600, 1300, 60)
            ]
            cursor.executemany("INSERT INTO productos (id, nombre, costo, precio_venta, stock) VALUES (?, ?, ?, ?, ?)", catalogo_inicial)

# --- Aplicación Principal ---
class MontanaClubApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Montana Club - Sistema de Gestión")
        self.geometry("1100x750")
        self.configure(fg_color=BG_COLOR)
        
        init_db()
        self.productos_db = []
        
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", background=CARD_COLOR, foreground=TEXT_COLOR, fieldbackground=CARD_COLOR, borderwidth=0, rowheight=30)
        style.map("Treeview", background=[("selected", "#2A251F")])
        style.configure("Treeview.Heading", background="#2A251F", foreground=TEXT_COLOR, relief="flat", font=("Helvetica", 10, "bold"))
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.crear_menu_lateral()
        
        self.frames = {}
        for F in (FrameNuevaVenta, FrameVentas, FrameInventario, FrameCaja):
            frame = F(self, self)
            self.frames[F] = frame
            frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            
        self.mostrar_frame(FrameNuevaVenta)
        
    def crear_menu_lateral(self):
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=CARD_COLOR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(5, weight=1)
        
        ctk.CTkLabel(sidebar, text="MONTANA CLUB", font=("Helvetica", 20, "bold"), text_color=TEXT_COLOR).grid(row=0, column=0, padx=20, pady=(30, 10))
        
        ctk.CTkButton(sidebar, text="+ Nueva Venta", fg_color=ACCENT_GREEN, text_color="black", font=("Helvetica", 14, "bold"), command=lambda: self.mostrar_frame(FrameNuevaVenta)).grid(row=2, column=0, padx=20, pady=10)
        ctk.CTkButton(sidebar, text="💰 Ventas", fg_color="transparent", border_width=1, border_color="#A09890", text_color=TEXT_COLOR, command=lambda: self.mostrar_frame(FrameVentas)).grid(row=3, column=0, padx=20, pady=10)
        ctk.CTkButton(sidebar, text="📦 Inventario", fg_color="transparent", border_width=1, border_color="#A09890", text_color=TEXT_COLOR, command=lambda: self.mostrar_frame(FrameInventario)).grid(row=4, column=0, padx=20, pady=10)
        ctk.CTkButton(sidebar, text="🏧 Caja (Hoy)", fg_color="transparent", border_width=1, border_color="#A09890", text_color=TEXT_COLOR, command=lambda: self.mostrar_frame(FrameCaja)).grid(row=5, column=0, padx=20, pady=10, sticky="n")

    def mostrar_frame(self, frame_class):
        frame = self.frames[frame_class]
        frame.tkraise()
        frame.actualizar_datos()

    def obtener_productos(self):
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # FIX CRUCIAL: Se pide explícitamente el orden para evitar cruces
            cursor.execute("SELECT id, nombre, costo, precio_venta, stock FROM productos")
            filas = cursor.fetchall()
        # Se fuerza int() en stock para eliminar el ".0" residual
        self.productos_db = [{"id": f[0], "nombre": f[1], "costo": f[2], "precio_venta": f[3], "stock": int(f[4])} for f in filas]
        return self.productos_db

# --- Frame: Nueva Venta ---
class FrameNuevaVenta(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="Registrar Nueva Venta", font=("Helvetica", 24, "bold"), text_color=TEXT_COLOR).pack(pady=(0, 20), anchor="w")
        
        form_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=15)
        form_frame.pack(fill="x", padx=20, pady=10)
        
        self.var_producto = ctk.StringVar(value="Seleccioná un producto")
        self.var_cantidad = ctk.StringVar(value="1")
        self.var_precio = ctk.StringVar(value="0")
        self.var_metodo = ctk.StringVar(value="efectivo")
        
        ctk.CTkLabel(form_frame, text="Producto:").grid(row=0, column=0, padx=20, pady=(20,5), sticky="w")
        self.cb_producto = ctk.CTkOptionMenu(form_frame, variable=self.var_producto, command=self.al_seleccionar_producto)
        self.cb_producto.grid(row=0, column=1, padx=20, pady=(20,5), sticky="ew")
        
        self.lbl_stock = ctk.CTkLabel(form_frame, text="Stock: -", text_color=ACCENT_ORANGE)
        self.lbl_stock.grid(row=0, column=2, padx=10, pady=(20,5), sticky="w")
        
        ctk.CTkLabel(form_frame, text="Cantidad:").grid(row=1, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.var_cantidad).grid(row=1, column=1, padx=20, pady=5, sticky="ew")
        
        ctk.CTkLabel(form_frame, text="Precio Venta ($):").grid(row=2, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.var_precio).grid(row=2, column=1, padx=20, pady=5, sticky="ew")
        
        ctk.CTkLabel(form_frame, text="Método de Pago:").grid(row=3, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkOptionMenu(form_frame, variable=self.var_metodo, values=["efectivo", "transferencia"]).grid(row=3, column=1, padx=20, pady=5, sticky="ew")
        
        ctk.CTkButton(form_frame, text="Registrar Venta", fg_color=ACCENT_GREEN, text_color="black", font=("Helvetica", 14, "bold"), command=self.registrar).grid(row=4, column=0, columnspan=3, pady=30)
        form_frame.grid_columnconfigure(1, weight=1)

    def actualizar_datos(self):
        prod_list = [p["nombre"] for p in self.controller.obtener_productos()]
        self.cb_producto.configure(values=prod_list)
        self.var_producto.set("Seleccioná un producto")
        self.lbl_stock.configure(text="Stock: -")

    def al_seleccionar_producto(self, choice):
        for p in self.controller.productos_db:
            if p["nombre"] == choice:
                self.var_precio.set(str(int(p["precio_venta"])))
                self.lbl_stock.configure(text=f"Stock: {p['stock']}")
                break

    def registrar(self):
        prod_nombre = self.var_producto.get()
        if prod_nombre == "Seleccioná un producto": return
        try:
            cant = int(self.var_cantidad.get())
            precio_venta = float(self.var_precio.get())
            
            stock_actual = 0
            costo_unitario = 0
            for p in self.controller.productos_db:
                if p["nombre"] == prod_nombre:
                    stock_actual = p["stock"]
                    costo_unitario = p["costo"]
                    break
            
            if cant > stock_actual:
                messagebox.showwarning("Sin Stock", f"Solo quedan {stock_actual} unidades de {prod_nombre}.")
                return

            vta_id = f"VTA-{datetime.now().strftime('%H%M%S')}"
            total_venta = cant * precio_venta
            total_costo = cant * costo_unitario
            metodo = self.var_metodo.get()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ventas (id, timestamp, producto_nombre, cantidad, precio_unitario, total, metodo_pago, costo_total) VALUES (?,?,?,?,?,?,?,?)", (vta_id, timestamp, prod_nombre, cant, precio_venta, total_venta, metodo, total_costo))
                cursor.execute("UPDATE productos SET stock = stock - ? WHERE nombre = ?", (cant, prod_nombre))
            
            messagebox.showinfo("Éxito", f"Venta registrada por ${total_venta:,.0f}")
            self.actualizar_datos()
            self.var_cantidad.set("1")
        except ValueError:
            messagebox.showerror("Error", "La cantidad y el precio deben ser números.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

# --- Frame: Historial de Ventas ---
class FrameVentas(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="Historial de Ventas", font=("Helvetica", 24, "bold"), text_color=TEXT_COLOR).pack(pady=(0, 20), anchor="w")
        
        self.tree = ttk.Treeview(self, columns=("ID", "Hora", "Producto", "Cant", "Total", "Pago"), show="headings")
        for col, width in {"ID": 100, "Hora": 150, "Producto": 200, "Cant": 60, "Total": 100, "Pago": 100}.items():
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True)

        ctk.CTkButton(self, text="Eliminar Venta Seleccionada", fg_color=ACCENT_RED, command=self.eliminar_venta).pack(pady=10)

    def actualizar_datos(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for fila in cursor.execute("SELECT id, timestamp, producto_nombre, cantidad, total, metodo_pago FROM ventas ORDER BY timestamp DESC"):
                self.tree.insert("", "end", values=(fila[0], fila[1], fila[2], fila[3], f"${fila[4]:,.0f}", fila[5]))

    def eliminar_venta(self):
        selected = self.tree.selection()
        if not selected: return
        
        item = self.tree.item(selected)
        vta_id = item['values'][0]
        prod_nombre = item['values'][2]
        cant = int(item['values'][3])

        if messagebox.askyesno("Confirmar", f"¿Desea anular la venta {vta_id}? El stock será devuelto."):
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ventas WHERE id = ?", (vta_id,))
                cursor.execute("UPDATE productos SET stock = stock + ? WHERE nombre = ?", (cant, prod_nombre))
            self.actualizar_datos()

# --- Frame: Inventario ---
class FrameInventario(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="Gestión de Inventario", font=("Helvetica", 24, "bold"), text_color=TEXT_COLOR).pack(pady=(0, 10), anchor="w")
        
        add_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR)
        add_frame.pack(fill="x", pady=10)
        
        self.ent_nombre = ctk.CTkEntry(add_frame, placeholder_text="Nombre Producto")
        self.ent_nombre.grid(row=0, column=0, padx=10, pady=10)
        
        self.ent_costo = ctk.CTkEntry(add_frame, placeholder_text="Costo ($)", width=100)
        self.ent_costo.grid(row=0, column=1, padx=10, pady=10)
        
        self.ent_precio = ctk.CTkEntry(add_frame, placeholder_text="Precio Venta ($)", width=120)
        self.ent_precio.grid(row=0, column=2, padx=10, pady=10)
        
        self.ent_stock = ctk.CTkEntry(add_frame, placeholder_text="Cant. Stock", width=100)
        self.ent_stock.grid(row=0, column=3, padx=10, pady=10)
        
        ctk.CTkButton(add_frame, text="Añadir Producto", fg_color=ACCENT_GREEN, text_color="black", command=self.agregar_producto).grid(row=0, column=4, padx=10)

        self.tree = ttk.Treeview(self, columns=("ID", "Producto", "Costo", "P. Venta", "Stock"), show="headings")
        for col, w in zip(("ID", "Producto", "Costo", "P. Venta", "Stock"), (80, 200, 100, 100, 80)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=10)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        ctk.CTkButton(btn_frame, text="Modificar Seleccionado", fg_color=ACCENT_ORANGE, text_color="black", command=self.abrir_modal_editar).grid(row=0, column=0, padx=10)
        ctk.CTkButton(btn_frame, text="Eliminar Producto", fg_color=ACCENT_RED, command=self.borrar_producto).grid(row=0, column=1, padx=10)

    def agregar_producto(self):
        nom = self.ent_nombre.get()
        costo = self.ent_costo.get()
        pre = self.ent_precio.get()
        stk = self.ent_stock.get()
        
        if not nom or not pre or not stk or not costo:
            messagebox.showwarning("Faltan datos", "Completa todos los campos")
            return
            
        try:
            costo_val = float(costo)
            precio_val = float(pre)
            stock_val = int(stk)
            
            nuevo_id = f"P{str(datetime.now().timestamp())[-4:]}"
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO productos (id, nombre, costo, precio_venta, stock) VALUES (?,?,?,?,?)", (nuevo_id, nom, costo_val, precio_val, stock_val))
            self.actualizar_datos()
            self.ent_nombre.delete(0, 'end'); self.ent_costo.delete(0, 'end'); self.ent_precio.delete(0, 'end'); self.ent_stock.delete(0, 'end')
        except ValueError:
            messagebox.showerror("Error", "Costo, Precio Venta y Stock deben ser números.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "El nombre de este producto ya existe.")
            
    def abrir_modal_editar(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Seleccioná un producto para editar")
            return
            
        item = self.tree.item(selected)
        prod_id = item['values'][0]
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nombre, costo, precio_venta, stock FROM productos WHERE id=?", (prod_id,))
            datos = cursor.fetchone()
            
        if not datos: return
        
        modal = ctk.CTkToplevel(self)
        modal.title(f"Editar Producto")
        modal.geometry("350x450")
        modal.transient(self.winfo_toplevel()) 
        modal.grab_set() 
        
        ctk.CTkLabel(modal, text=f"Editando: {datos[0]}", font=("Helvetica", 18, "bold")).pack(pady=(20, 10))
        
        ctk.CTkLabel(modal, text="Costo ($):").pack(pady=(10, 0))
        ent_modal_costo = ctk.CTkEntry(modal)
        ent_modal_costo.pack(pady=5)
        ent_modal_costo.insert(0, str(int(datos[1])))
        
        ctk.CTkLabel(modal, text="Precio de Venta ($):").pack(pady=(10, 0))
        ent_modal_precio = ctk.CTkEntry(modal)
        ent_modal_precio.pack(pady=5)
        ent_modal_precio.insert(0, str(int(datos[2])))
        
        ctk.CTkLabel(modal, text="Cantidad en Stock:").pack(pady=(10, 0))
        ent_modal_stock = ctk.CTkEntry(modal)
        ent_modal_stock.pack(pady=5)
        ent_modal_stock.insert(0, str(int(datos[3])))  # Aseguramos que cargue como entero sin .0
        
        def guardar_cambios():
            try:
                nuevo_costo = float(ent_modal_costo.get())
                nuevo_precio = float(ent_modal_precio.get())
                nuevo_stock = int(ent_modal_stock.get())
                
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE productos SET costo=?, precio_venta=?, stock=? WHERE id=?", 
                                   (nuevo_costo, nuevo_precio, nuevo_stock, prod_id))
                self.actualizar_datos()
                modal.destroy()
                messagebox.showinfo("Éxito", "Producto actualizado correctamente")
            except ValueError:
                messagebox.showerror("Error", "Asegúrate de ingresar solo números válidos.")
                
        ctk.CTkButton(modal, text="Guardar Cambios", fg_color=ACCENT_GREEN, text_color="black", command=guardar_cambios).pack(pady=30)

    def borrar_producto(self):
        selected = self.tree.selection()
        if not selected: return
        prod_id = self.tree.item(selected)['values'][0]
        
        if messagebox.askyesno("Eliminar", "¿Seguro que quieres borrar este producto del catálogo?"):
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("DELETE FROM productos WHERE id = ?", (prod_id,))
            self.actualizar_datos()

    def actualizar_datos(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        for p in self.controller.obtener_productos():
            self.tree.insert("", "end", values=(p["id"], p["nombre"], f"${p['costo']:,.0f}", f"${p['precio_venta']:,.0f}", p["stock"]))

# --- Frame: Caja ---
class FrameCaja(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="Resumen de Caja (Solo Hoy)", font=("Helvetica", 24, "bold"), text_color=TEXT_COLOR).pack(pady=(0, 20), anchor="w")
        
        self.info_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=15)
        self.info_frame.pack(fill="x", padx=20, pady=10)
        
        self.lbl_efectivo = ctk.CTkLabel(self.info_frame, text="Ingresos Efectivo: $0", font=("Helvetica", 16), text_color=TEXT_COLOR)
        self.lbl_efectivo.pack(pady=(20, 5))
        
        self.lbl_transf = ctk.CTkLabel(self.info_frame, text="Ingresos Transferencias: $0", font=("Helvetica", 16), text_color=TEXT_COLOR)
        self.lbl_transf.pack(pady=5)
        
        self.lbl_total_ventas = ctk.CTkLabel(self.info_frame, text="TOTAL VENTAS: $0", font=("Helvetica", 20, "bold"), text_color=TEXT_COLOR)
        self.lbl_total_ventas.pack(pady=(10, 20))
        
        ctk.CTkFrame(self.info_frame, height=2, fg_color="#3A342E").pack(fill="x", padx=40, pady=10)
        
        self.lbl_costo_total = ctk.CTkLabel(self.info_frame, text="Costo de Mercadería: $0", font=("Helvetica", 16), text_color=ACCENT_RED)
        self.lbl_costo_total.pack(pady=(20, 10))
        
        self.lbl_ganancia = ctk.CTkLabel(self.info_frame, text="GANANCIA REAL: $0", font=("Helvetica", 26, "bold"), text_color=ACCENT_GREEN)
        self.lbl_ganancia.pack(pady=(10, 30))

    def actualizar_datos(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metodo_pago, SUM(total), SUM(costo_total) FROM ventas WHERE timestamp LIKE ? GROUP BY metodo_pago", (f"{hoy}%",))
            filas = cursor.fetchall()
        
        efectivo = 0
        transf = 0
        costo_total_dia = 0
        
        for fila in filas:
            metodo, total_venta, costo_venta = fila
            if metodo == "efectivo":
                efectivo += total_venta
            elif metodo == "transferencia":
                transf += total_venta
                
            costo_total_dia += costo_venta
            
        total_ingresos = efectivo + transf
        ganancia_neta = total_ingresos - costo_total_dia
        
        self.lbl_efectivo.configure(text=f"Ingresos en Efectivo: ${efectivo:,.0f}")
        self.lbl_transf.configure(text=f"Ingresos por Transferencia: ${transf:,.0f}")
        self.lbl_total_ventas.configure(text=f"TOTAL VENTAS BRUTAS: ${total_ingresos:,.0f}")
        
        self.lbl_costo_total.configure(text=f"- Costo de Mercadería Vendida: ${costo_total_dia:,.0f}")
        self.lbl_ganancia.configure(text=f"GANANCIA REAL (NETA): ${ganancia_neta:,.0f}")

if __name__ == "__main__":
    app = MontanaClubApp()
    app.mainloop()