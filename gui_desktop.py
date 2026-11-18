"""
Interface Gráfica Desktop (Tkinter) para Extração de Imagens de PSD
Permite selecionar arquivos PSD, visualizar camadas e exportar em PNG/JPG/WEBP.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from extractor import PSDExtractor

class PSDDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Extrator de Imagens PSD - Desktop")
        self.geometry("1100;700".replace(";", "x"))
        self.minsize(900, 600)

        # Configuração de estilo ttk
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        self.extractor: PSDExtractor = None
        self.current_preview_image = None
        self.layers_info = []
        self.layer_check_vars = {}

        self._setup_ui()

    def _setup_ui(self):
        # Barra superior com ações do arquivo
        top_bar = ttk.Frame(self, padding="10")
        top_bar.pack(fill=tk.X)

        self.btn_open = ttk.Button(top_bar, text="📂 Abrir Arquivo PSD...", command=self.open_psd_file)
        self.btn_open.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_file_info = ttk.Label(top_bar, text="Nenhum arquivo PSD carregado.", font=("Segoe UI", 10, "bold"))
        self.lbl_file_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Painel central dividido em dois lados (Esquerda: Camadas | Direita: Pré-visualização)
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # === Painel Esquerdo: Lista de Camadas ===
        left_frame = ttk.LabelFrame(paned, text="Camadas do PSD", padding="8")
        paned.add(left_frame, weight=3)

        # Barra de ferramentas da lista de camadas
        layer_tools = ttk.Frame(left_frame)
        layer_tools.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(layer_tools, text="Marcar Todas", command=lambda: self.set_all_checks(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(layer_tools, text="Desmarcar", command=lambda: self.set_all_checks(False)).pack(side=tk.LEFT, padx=2)
        ttk.Button(layer_tools, text="Apenas Visíveis", command=self.check_only_visible).pack(side=tk.LEFT, padx=2)

        # Treeview de camadas com scrollbar
        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        columns = ("sel", "name", "type", "dimensions", "visible")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("sel", text="✓")
        self.tree.heading("name", text="Nome da Camada")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("dimensions", text="Dimensões (L×A)")
        self.tree.heading("visible", text="Visível")

        self.tree.column("sel", width=35, anchor="center")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("dimensions", width=110, anchor="center")
        self.tree.column("visible", width=60, anchor="center")

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # === Painel Direito: Preview ===
        right_frame = ttk.LabelFrame(paned, text="Pré-visualização", padding="8")
        paned.add(right_frame, weight=4)

        self.lbl_preview_title = ttk.Label(right_frame, text="Selecione uma camada para visualizar", font=("Segoe UI", 9))
        self.lbl_preview_title.pack(anchor="w", pady=(0, 6))

        self.canvas_preview = tk.Canvas(right_frame, bg="#20252e", highlightthickness=0)
        self.canvas_preview.pack(fill=tk.BOTH, expand=True)
        self.canvas_preview.bind("<Configure>", self.on_canvas_resize)

        # === Barra Inferior: Configurações de Exportação ===
        bottom_frame = ttk.LabelFrame(self, text="Opções de Exportação", padding="10")
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)

        # Opções
        opts_row = ttk.Frame(bottom_frame)
        opts_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(opts_row, text="Formato:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_format = tk.StringVar(value="PNG")
        self.combo_format = ttk.Combobox(opts_row, textvariable=self.var_format, values=["PNG", "JPG", "WEBP"], width=8, state="readonly")
        self.combo_format.pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(opts_row, text="Modo de Corte:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_mode = tk.StringVar(value="cropped")
        self.combo_mode = ttk.Combobox(
            opts_row,
            textvariable=self.var_mode,
            values=["cropped", "canvas"],
            width=18,
            state="readonly"
        )
        self.combo_mode.pack(side=tk.LEFT, padx=(0, 16))

        self.var_include_composite = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_row, text="Incluir imagem composta completa", variable=self.var_include_composite).pack(side=tk.LEFT, padx=(0, 16))

        # Botões de Ação
        actions_row = ttk.Frame(bottom_frame)
        actions_row.pack(fill=tk.X)

        self.btn_export_html_zip = ttk.Button(actions_row, text="🌐 Exportar HTML (.ZIP)...", command=self.export_html_zip)
        self.btn_export_html_zip.pack(side=tk.RIGHT, padx=4)

        self.btn_export_zip = ttk.Button(actions_row, text="📦 Exportar Imagens (.ZIP)...", command=self.export_zip)
        self.btn_export_zip.pack(side=tk.RIGHT, padx=4)

        self.btn_export_folder = ttk.Button(actions_row, text="📁 Salvar em Pasta Local...", command=self.export_folder)
        self.btn_export_folder.pack(side=tk.RIGHT, padx=4)

        self.status_var = tk.StringVar(value="Pronto.")
        self.lbl_status = ttk.Label(actions_row, textvariable=self.status_var, font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def open_psd_file(self):
        file_path = filedialog.askopenfilename(
            title="Selecione um arquivo Photoshop",
            filetypes=[("Arquivos PSD / PSB", "*.psd;*.psb"), ("Todos os Arquivos", "*.*")]
        )
        if not file_path:
            return

        self.status_var.set(f"Carregando {os.path.basename(file_path)}...")
        self.update_idletasks()

        threading.Thread(target=self._load_psd_thread, args=(file_path,), daemon=True).start()

    def _load_psd_thread(self, file_path):
        try:
            extractor = PSDExtractor(file_path)
            info = extractor.get_info()
            layers = extractor.get_layers_info()

            self.after(0, self._on_psd_loaded, extractor, info, layers)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro ao carregar PSD", str(e)))
            self.after(0, lambda: self.status_var.set("Erro ao abrir arquivo."))

    def _on_psd_loaded(self, extractor, info, layers):
        self.extractor = extractor
        self.layers_info = layers
        self.layer_check_vars.clear()

        # Atualiza labels
        filename = info["filename"]
        dim = f"{info['width']} × {info['height']} px"
        color = f"{info['color_mode']} {info['depth']}-bit"
        self.lbl_file_info.config(text=f"{filename}  |  {dim}  |  {color}  |  {len(layers)} camadas")

        # Limpa treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Preenche treeview
        for layer in layers:
            idx = layer["index"]
            # Marca por padrão camadas válidas
            default_checked = layer["has_pixels"] and not layer["is_group"]
            self.layer_check_vars[idx] = default_checked

            check_mark = "☑" if default_checked else "☐"
            dim_str = f"{layer['width']}×{layer['height']}" if layer['width'] > 0 else "-"
            vis_str = "Sim" if layer["visible"] else "Não"

            self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(check_mark, layer["name"], layer["kind"], dim_str, vis_str)
            )

        # Mostra o composite como preview inicial
        self.show_composite_preview()
        self.status_var.set(f"PSD carregado com {len(layers)} camadas.")

    def on_tree_click(self, event):
        """Alterna a caixa de seleção ao clicar na coluna ✓."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        # Coluna #1 é a coluna de seleção
        if column == "#1":
            idx = int(item_id)
            current = self.layer_check_vars.get(idx, False)
            self.layer_check_vars[idx] = not current

            mark = "☑" if not current else "☐"
            values = list(self.tree.item(item_id, "values"))
            values[0] = mark
            self.tree.item(item_id, values=values)

    def on_tree_select(self, event):
        """Ao clicar na linha, carrega o preview da camada."""
        selected = self.tree.selection()
        if not selected or not self.extractor:
            return

        idx = int(selected[0])
        self.lbl_preview_title.config(text=f"Renderizando camada #{idx+1}...")
        threading.Thread(target=self._load_layer_preview_thread, args=(idx,), daemon=True).start()

    def _load_layer_preview_thread(self, idx):
        try:
            layer_info = next((l for l in self.layers_info if l["index"] == idx), None)
            name = layer_info["name"] if layer_info else f"Camada {idx+1}"
            img = self.extractor.render_layer_image(idx, mode="cropped")

            if img:
                self.after(0, self._update_canvas_image, img, f"Camada: {name} ({img.width}×{img.height} px)")
            else:
                self.after(0, lambda: self.lbl_preview_title.config(text=f"Camada sem pixels visíveis: {name}"))
        except Exception as e:
            self.after(0, lambda: self.lbl_preview_title.config(text=f"Erro ao renderizar camada: {e}"))

    def show_composite_preview(self):
        if not self.extractor:
            return
        self.lbl_preview_title.config(text="Renderizando imagem composta completa...")
        threading.Thread(target=self._load_composite_thread, daemon=True).start()

    def _load_composite_thread(self):
        try:
            img = self.extractor.get_composite_image()
            if img:
                self.after(0, self._update_canvas_image, img, f"Imagem Composta ({img.width}×{img.height} px)")
        except Exception as e:
            self.after(0, lambda: self.lbl_preview_title.config(text=f"Erro ao renderizar composto: {e}"))

    def _update_canvas_image(self, pil_image, title):
        self.current_preview_image = pil_image
        self.lbl_preview_title.config(text=title)
        self.render_preview_canvas()

    def on_canvas_resize(self, event):
        if self.current_preview_image:
            self.render_preview_canvas()

    def render_preview_canvas(self):
        if not self.current_preview_image:
            return

        canvas_w = self.canvas_preview.winfo_width()
        canvas_h = self.canvas_preview.winfo_height()
        if canvas_w <= 10 or canvas_h <= 10:
            return

        # Redimensiona mantendo proporção
        img_w, img_h = self.current_preview_image.size
        ratio = min(canvas_w / img_w, canvas_h / img_h, 1.0)
        new_w = max(1, int(img_w * ratio))
        new_h = max(1, int(img_h * ratio))

        resized = self.current_preview_image.copy()
        resized.thumbnail((new_w, new_h), Image.Resampling.LANCZOS)

        self._tk_thumb = ImageTk.PhotoImage(resized)

        self.canvas_preview.delete("all")
        # Desenha centralizado
        x = (canvas_w - resized.width) // 2
        y = (canvas_h - resized.height) // 2
        self.canvas_preview.create_image(x, y, anchor=tk.NW, image=self._tk_thumb)

    def set_all_checks(self, check):
        for idx in self.layer_check_vars:
            self.layer_check_vars[idx] = check
            item_id = str(idx)
            if self.tree.exists(item_id):
                values = list(self.tree.item(item_id, "values"))
                values[0] = "☑" if check else "☐"
                self.tree.item(item_id, values=values)

    def check_only_visible(self):
        for layer in self.layers_info:
            idx = layer["index"]
            is_vis = layer["visible"] and layer["has_pixels"]
            self.layer_check_vars[idx] = is_vis
            item_id = str(idx)
            if self.tree.exists(item_id):
                values = list(self.tree.item(item_id, "values"))
                values[0] = "☑" if is_vis else "☐"
                self.tree.item(item_id, values=values)

    def get_selected_indices(self):
        return [idx for idx, val in self.layer_check_vars.items() if val]

    def export_zip(self):
        if not self.extractor:
            messagebox.showwarning("Aviso", "Abra um arquivo PSD primeiro.")
            return

        selected = self.get_selected_indices()
        include_comp = self.var_include_composite.get()
        if not selected and not include_comp:
            messagebox.showwarning("Aviso", "Selecione ao menos uma camada ou marque a opção de incluir o composto.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Salvar Arquivo ZIP",
            defaultextension=".zip",
            filetypes=[("Arquivo ZIP", "*.zip")],
            initialfile=f"{os.path.splitext(self.extractor.filename)[0]}_camadas.zip"
        )
        if not save_path:
            return

        self.status_var.set("Gerando arquivo ZIP...")
        self.update_idletasks()

        format_type = self.var_format.get()
        mode = self.var_mode.get()

        threading.Thread(
            target=self._export_zip_thread,
            args=(save_path, selected, include_comp, mode, format_type),
            daemon=True
        ).start()

    def _export_zip_thread(self, save_path, selected, include_comp, mode, format_type):
        try:
            zip_buf = self.extractor.export_selection_to_zip(
                selected_indices=selected,
                include_composite=include_comp,
                mode=mode,
                format_type=format_type
            )
            with open(save_path, "wb") as f:
                f.write(zip_buf.getvalue())

            self.after(0, lambda: messagebox.showinfo("Sucesso", f"Arquivo ZIP gerado com sucesso em:\n{save_path}"))
            self.after(0, lambda: self.status_var.set("Exportação ZIP concluída."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro ao exportar ZIP", str(e)))
            self.after(0, lambda: self.status_var.set("Falha na exportação."))

    def export_folder(self):
        if not self.extractor:
            messagebox.showwarning("Aviso", "Abra um arquivo PSD primeiro.")
            return

        selected = self.get_selected_indices()
        include_comp = self.var_include_composite.get()
        if not selected and not include_comp:
            messagebox.showwarning("Aviso", "Selecione ao menos uma camada ou marque a opção de incluir o composto.")
            return

        folder_path = filedialog.askdirectory(title="Selecione a pasta de destino")
        if not folder_path:
            return

        self.status_var.set(f"Exportando para pasta...")
        self.update_idletasks()

        format_type = self.var_format.get()
        mode = self.var_mode.get()

        threading.Thread(
            target=self._export_folder_thread,
            args=(folder_path, selected, include_comp, mode, format_type),
            daemon=True
        ).start()

    def _export_folder_thread(self, folder_path, selected, include_comp, mode, format_type):
        try:
            saved = self.extractor.export_to_directory(
                output_dir=folder_path,
                selected_indices=selected,
                include_composite=include_comp,
                mode=mode,
                format_type=format_type
            )
            self.after(0, lambda: messagebox.showinfo(
                "Exportação Concluída",
                f"{len(saved)} arquivos foram exportados com sucesso para:\n{folder_path}"
            ))
            self.after(0, lambda: self.status_var.set(f"{len(saved)} arquivos salvos."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro ao exportar pasta", str(e)))
            self.after(0, lambda: self.status_var.set("Falha na exportação."))

    def export_html_zip(self):
        if not self.extractor:
            messagebox.showwarning("Aviso", "Abra um arquivo PSD primeiro.")
            return

        selected = self.get_selected_indices()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione ao menos uma camada para gerar o HTML renderizável.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Salvar Pacote HTML (.ZIP)",
            defaultextension=".zip",
            filetypes=[("Arquivo ZIP", "*.zip")],
            initialfile=f"{os.path.splitext(self.extractor.filename)[0]}_html_renderizavel.zip"
        )
        if not save_path:
            return

        self.status_var.set("Gerando pacote HTML renderizável...")
        self.update_idletasks()

        threading.Thread(
            target=self._export_html_zip_thread,
            args=(save_path, selected),
            daemon=True
        ).start()

    def _export_html_zip_thread(self, save_path, selected):
        try:
            zip_buf = self.extractor.export_html_to_zip(selected_indices=selected, responsive=True)
            with open(save_path, "wb") as f:
                f.write(zip_buf.getvalue())

            self.after(0, lambda: messagebox.showinfo(
                "Sucesso",
                f"Pacote HTML renderizável gerado com sucesso em:\n{save_path}\n\nAbra o 'index.html' no navegador para visualizar a composição montada com as peças recortadas!"
            ))
            self.after(0, lambda: self.status_var.set("Exportação HTML concluída."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro ao exportar HTML", str(e)))
            self.after(0, lambda: self.status_var.set("Falha na exportação HTML."))


if __name__ == "__main__":
    app = PSDDesktopApp()
    app.mainloop()
