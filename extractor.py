"""
Módulo de Extração de Imagens e Camadas de PSD (Photoshop)
Utiliza psd-tools e Pillow para manipulação e exportação.
"""

import io
import os
import re
import base64
import zipfile
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import Layer, Group

def sanitize_filename(name: str, fallback: str = "camada") -> str:
    """Sanitiza o nome de uma camada para um nome de arquivo válido no Windows/Linux."""
    if not name or not name.strip():
        return fallback
    # Remove caracteres inválidos do Windows
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', name.strip())
    # Remove espaços repetidos e caracteres de controle
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Limita tamanho do nome
    cleaned = cleaned[:100]
    return cleaned if cleaned else fallback

class PSDExtractor:
    def __init__(self, filepath_or_bytes, filename: Optional[str] = None):
        """Carrega o arquivo PSD a partir de um caminho de arquivo ou objeto bytes/io."""
        self.psd = PSDImage.open(filepath_or_bytes)
        if filename:
            self.filename = filename
        elif isinstance(filepath_or_bytes, (str, os.PathLike)):
            self.filename = os.path.basename(str(filepath_or_bytes))
        else:
            self.filename = "arquivo.psd"

        self.width = self.psd.width
        self.height = self.psd.height
        self.color_mode = getattr(self.psd, 'color_mode', 'RGB')
        self.depth = getattr(self.psd, 'depth', 8)
        self._layers_cache: Optional[List[Dict[str, Any]]] = None

    def get_info(self) -> Dict[str, Any]:
        """Retorna informações gerais sobre o PSD."""
        layers = self.get_layers_info()
        color_mode_str = getattr(self.color_mode, 'name', str(self.color_mode))
        has_preview = False
        try:
            if callable(getattr(self.psd, 'has_preview', None)):
                has_preview = self.psd.has_preview()
            else:
                has_preview = bool(getattr(self.psd, 'has_preview', False))
        except Exception:
            has_preview = False

        return {
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "color_mode": color_mode_str,
            "depth": self.depth,
            "total_layers": len(layers),
            "has_preview": has_preview
        }

    def get_composite_image(self) -> Image.Image:
        """Renderiza e retorna a imagem completa composta (flattened) do PSD."""
        composite = self.psd.composite()
        if composite is None:
            # Fallback para topil se disponível
            composite = self.psd.topil()
        return composite

    def get_layers_info(self) -> List[Dict[str, Any]]:
        """
        Retorna a lista estruturada de todas as camadas extraíveis com metadados.
        """
        if self._layers_cache is not None:
            return self._layers_cache

        layers_info = []
        name_counts: Dict[str, int] = {}

        # Percorre todas as camadas recursivamente (descendants)
        for idx, layer in enumerate(self.psd.descendants()):
            is_group = layer.is_group()
            is_visible = getattr(layer, 'visible', True)
            kind = getattr(layer, 'kind', 'pixel')

            width = getattr(layer, 'width', 0)
            height = getattr(layer, 'height', 0)
            left = getattr(layer, 'left', 0)
            top = getattr(layer, 'top', 0)

            # Define se a camada possui dados de imagem válidos
            has_pixels = (width > 0 and height > 0)
            if is_group:
                # Grupos podem ser compostos se tiverem filhos visíveis
                has_pixels = True

            raw_name = layer.name or f"Camada_{idx+1}"
            safe_name = sanitize_filename(raw_name, f"camada_{idx+1}")

            # Gerenciamento de nomes duplicados
            if safe_name in name_counts:
                name_counts[safe_name] += 1
                unique_name = f"{safe_name}_{name_counts[safe_name]}"
            else:
                name_counts[safe_name] = 1
                unique_name = safe_name

            opacity = getattr(layer, 'opacity', 255)
            if isinstance(opacity, int):
                opacity_pct = round((opacity / 255.0) * 100)
            else:
                opacity_pct = 100

            blend_mode = getattr(layer, 'blend_mode', None)
            blend_mode_str = getattr(blend_mode, 'name', str(blend_mode)) if blend_mode else "normal"

            layers_info.append({
                "index": idx,
                "name": raw_name,
                "safe_name": unique_name,
                "is_group": is_group,
                "visible": is_visible,
                "kind": kind,
                "width": width,
                "height": height,
                "left": left,
                "top": top,
                "opacity": opacity_pct,
                "blend_mode": blend_mode_str,
                "has_pixels": has_pixels
            })

        self._layers_cache = layers_info
        return layers_info

    def get_layer_by_index(self, index: int) -> Optional[Layer]:
        """Recupera o objeto de camada original pelo índice."""
        for idx, layer in enumerate(self.psd.descendants()):
            if idx == index:
                return layer
        return None

    def render_layer_image(
        self,
        layer_index: int,
        mode: str = "cropped",
        format_type: str = "PNG"
    ) -> Optional[Image.Image]:
        """
        Renderiza uma camada específica.
        - mode='cropped': extrai apenas os pixels da camada (tamanho da camada).
        - mode='canvas': posiciona a camada no canvas original com transparência.
        """
        layer = self.get_layer_by_index(layer_index)
        if layer is None:
            return None

        img = None
        try:
            img = layer.composite()
        except Exception:
            try:
                img = layer.topil()
            except Exception:
                img = None

        if img is None:
            return None

        # Garante modo RGBA para preservar transparência
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        if mode == "canvas":
            # Cria um canvas transparente do tamanho do PSD completo
            canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            left = getattr(layer, 'left', 0)
            top = getattr(layer, 'top', 0)
            canvas.paste(img, (left, top), img)
            img = canvas

        # Ajuste de cores se o formato de saída for JPEG (sem canal alfa)
        if format_type.upper() in ["JPG", "JPEG"]:
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])  # Aplica máscara alfa sobre fundo branco
            img = bg

        return img

    def generate_thumbnail(self, img: Image.Image, max_size: Tuple[int, int] = (200, 200)) -> Image.Image:
        """Gera thumbnail proporcional de uma imagem."""
        thumb = img.copy()
        thumb.thumbnail(max_size, Image.Resampling.LANCZOS)
        return thumb

    def export_selection_to_zip(
        self,
        selected_indices: List[int],
        include_composite: bool = False,
        mode: str = "cropped",
        format_type: str = "PNG",
        quality: int = 90
    ) -> io.BytesIO:
        """
        Exporta as camadas selecionadas e/ou o composite para um arquivo ZIP em memória.
        """
        zip_buffer = io.BytesIO()
        layers_info = {info["index"]: info for info in self.get_layers_info()}

        format_ext = "jpg" if format_type.upper() in ["JPG", "JPEG"] else format_type.lower()
        save_format = "JPEG" if format_ext == "jpg" else format_type.upper()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Exporta composite se solicitado
            if include_composite:
                comp_img = self.get_composite_image()
                if comp_img:
                    if save_format == "JPEG" and comp_img.mode != "RGB":
                        bg = Image.new("RGB", comp_img.size, (255, 255, 255))
                        if comp_img.mode == "RGBA":
                            bg.paste(comp_img, mask=comp_img.split()[3])
                        else:
                            bg.paste(comp_img)
                        comp_img = bg

                    img_io = io.BytesIO()
                    save_args = {"format": save_format}
                    if save_format in ["JPEG", "WEBP"]:
                        save_args["quality"] = quality
                    comp_img.save(img_io, **save_args)
                    img_io.seek(0)

                    psd_base = os.path.splitext(self.filename)[0]
                    zip_file.writestr(f"{psd_base}_completo.{format_ext}", img_io.getvalue())

            # 2. Exporta cada camada selecionada
            for idx in selected_indices:
                info = layers_info.get(idx)
                if not info:
                    continue

                layer_img = self.render_layer_image(idx, mode=mode, format_type=save_format)
                if layer_img is None:
                    continue

                img_io = io.BytesIO()
                save_args = {"format": save_format}
                if save_format in ["JPEG", "WEBP"]:
                    save_args["quality"] = quality
                layer_img.save(img_io, **save_args)
                img_io.seek(0)

                clean_name = info["safe_name"]
                filename = f"{idx+1:03d}_{clean_name}.{format_ext}"
                zip_file.writestr(f"camadas/{filename}", img_io.getvalue())

        zip_buffer.seek(0)
        return zip_buffer

    def export_to_directory(
        self,
        output_dir: str,
        selected_indices: List[int],
        include_composite: bool = True,
        mode: str = "cropped",
        format_type: str = "PNG",
        quality: int = 90
    ) -> List[str]:
        """
        Salva as imagens diretamente em uma pasta local.
        Retorna lista de caminhos dos arquivos gerados.
        """
        os.makedirs(output_dir, exist_ok=True)
        saved_files = []
        layers_info = {info["index"]: info for info in self.get_layers_info()}

        format_ext = "jpg" if format_type.upper() in ["JPG", "JPEG"] else format_type.lower()
        save_format = "JPEG" if format_ext == "jpg" else format_type.upper()

        if include_composite:
            comp_img = self.get_composite_image()
            if comp_img:
                if save_format == "JPEG" and comp_img.mode != "RGB":
                    bg = Image.new("RGB", comp_img.size, (255, 255, 255))
                    if comp_img.mode == "RGBA":
                        bg.paste(comp_img, mask=comp_img.split()[3])
                    else:
                        bg.paste(comp_img)
                    comp_img = bg

                psd_base = os.path.splitext(self.filename)[0]
                out_path = os.path.join(output_dir, f"{psd_base}_completo.{format_ext}")
                save_args = {"format": save_format}
                if save_format in ["JPEG", "WEBP"]:
                    save_args["quality"] = quality
                comp_img.save(out_path, **save_args)
                saved_files.append(out_path)

        for idx in selected_indices:
            info = layers_info.get(idx)
            if not info:
                continue

            layer_img = self.render_layer_image(idx, mode=mode, format_type=save_format)
            if layer_img is None:
                continue

            clean_name = info["safe_name"]
            filename = f"{idx+1:03d}_{clean_name}.{format_ext}"
            out_path = os.path.join(output_dir, filename)

            save_args = {"format": save_format}
            if save_format in ["JPEG", "WEBP"]:
                save_args["quality"] = quality
            layer_img.save(out_path, **save_args)
            saved_files.append(out_path)

        return saved_files

    def generate_renderable_html(
        self,
        selected_indices: List[int],
        embed_base64: bool = False,
        images_dir_rel: str = "images",
        fit_to_selection: bool = True,
        responsive: bool = True,
        mobile_mode: str = "stack",
        layer_configs: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, Dict[str, bytes]]:
        """
        Gera HTML e CSS renderizáveis reconstruindo a composição do PSD com suas peças,
        permitindo que cada peça seja renderizada de forma diferente na Web (Desktop) e no Mobile.
        - fit_to_selection=True: ajusta o tamanho do artboard ao retângulo delimitador exato das
          camadas selecionadas (sem espaços vazios gigantes).
        - mobile_mode: 'stack' (empilhamento vertical adaptativo) ou 'proportional' (canvas escalonado).
        - layer_configs: dicionário com regras específicas de cada camada para Web/Mobile:
          {
             index: {
               "target": "all" | "desktop" | "mobile",
               "mobile_behavior": "stack" | "absolute" | "bg" | "hide",
               "mobile_align": "center" | "full" | "left" | "right",
               "mobile_order": int
             }
          }
        Retorna (html_completo, css_completo, dict_imagens_bytes).
        """
        layers_info = {info["index"]: info for info in self.get_layers_info()}
        configs = layer_configs or {}

        # Filtra apenas camadas válidas selecionadas com pixels
        valid_indices = [
            idx for idx in selected_indices
            if idx in layers_info and layers_info[idx]["has_pixels"] and layers_info[idx]["width"] > 0 and layers_info[idx]["height"] > 0
        ]

        # Se nenhuma camada válida for selecionada
        if not valid_indices:
            doc_title = os.path.splitext(self.filename)[0]
            empty_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>{doc_title} - Nenhuma Imagem Selecionada</title>
  <style>
    body {{ background: #0f172a; color: #94a3b8; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
    .box {{ background: #1e293b; border: 1px dashed #475569; border-radius: 12px; padding: 40px; text-align: center; max-width: 500px; }}
    h3 {{ color: #f8fafc; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <div class="box">
    <h3>Nenhuma imagem selecionada</h3>
    <p>Marque uma ou mais camadas na aba <strong>Camadas</strong> para gerar a composição HTML no tamanho certo.</p>
  </div>
</body>
</html>"""
            return empty_html, "", {}

        # Determina a área de corte do artboard para o modo Desktop
        if fit_to_selection:
            min_x = min(layers_info[idx]["left"] for idx in valid_indices)
            min_y = min(layers_info[idx]["top"] for idx in valid_indices)
            max_x = max(layers_info[idx]["left"] + layers_info[idx]["width"] for idx in valid_indices)
            max_y = max(layers_info[idx]["top"] + layers_info[idx]["height"] for idx in valid_indices)
            artboard_w = max(1, max_x - min_x)
            artboard_h = max(1, max_y - min_y)
            origin_x = min_x
            origin_y = min_y
            is_cropped = (origin_x > 0 or origin_y > 0 or artboard_w < self.width or artboard_h < self.height)
        else:
            artboard_w = max(1, self.width)
            artboard_h = max(1, self.height)
            origin_x = 0
            origin_y = 0
            is_cropped = False

        images_bytes: Dict[str, bytes] = {}
        layer_elements: List[str] = []
        desktop_rules: List[str] = []
        mobile_rules: List[str] = []

        blend_mode_map = {
            "normal": "normal",
            "multiply": "multiply",
            "screen": "screen",
            "overlay": "overlay",
            "darken": "darken",
            "lighten": "lighten",
            "color_dodge": "color-dodge",
            "color_burn": "color-burn",
            "hard_light": "hard-light",
            "soft_light": "soft-light",
            "difference": "difference",
            "exclusion": "exclusion",
            "hue": "hue",
            "saturation": "saturation",
            "color": "color",
            "luminosity": "luminosity"
        }

        # Ordena as camadas pelo índice para garantir hierarquia correta de z-index
        sorted_indices = sorted(valid_indices)

        for z_idx, idx in enumerate(sorted_indices, start=1):
            info = layers_info[idx]
            cfg = configs.get(idx) or configs.get(str(idx)) or {}

            target = cfg.get("target", "all")  # all, desktop, mobile
            mobile_align = cfg.get("mobile_align", "center")  # center, full, left, right
            mobile_order = cfg.get("mobile_order", z_idx)

            # Heurística inteligente de comportamento mobile
            mobile_behavior = cfg.get("mobile_behavior", "auto")
            w = info["width"]
            h = info["height"]

            if mobile_behavior == "auto":
                # Camadas que cobrem mais de 70% do canvas se comportam como plano de fundo
                if w >= artboard_w * 0.70 and h >= artboard_h * 0.70:
                    mobile_behavior = "bg"
                else:
                    mobile_behavior = "stack"

            layer_img = self.render_layer_image(idx, mode="cropped", format_type="PNG")
            if layer_img is None:
                continue

            img_buffer = io.BytesIO()
            layer_img.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()

            clean_name = info["safe_name"]
            img_filename = f"{idx+1:03d}_{clean_name}.png"
            images_bytes[img_filename] = img_bytes

            if embed_base64:
                b64_data = base64.b64encode(img_bytes).decode("utf-8")
                img_src = f"data:image/png;base64,{b64_data}"
            else:
                img_src = f"{images_dir_rel}/{img_filename}"

            # Posição relativa ao artboard definido
            rel_left = info["left"] - origin_x
            rel_top = info["top"] - origin_y
            opacity = info.get("opacity", 100) / 100.0
            blend = blend_mode_map.get(info.get("blend_mode", "normal").lower(), "normal")

            # Cálculo proporcional para responsividade fluida mantendo proporção 1:1 exata
            left_pct = (rel_left / artboard_w) * 100.0
            top_pct = (rel_top / artboard_h) * 100.0
            w_pct = (w / artboard_w) * 100.0
            h_pct = (h / artboard_h) * 100.0

            layer_class = f"psd-layer-{idx}"

            # === 1. Regra para DESKTOP / WEB ===
            if target == "mobile":
                d_rule = f".{layer_class} {{ display: none !important; }}"
            else:
                d_rule = f"""
.{layer_class} {{
  position: absolute;
  left: {left_pct:.4f}%;
  top: {top_pct:.4f}%;
  width: {w_pct:.4f}%;
  height: {h_pct:.4f}%;
  z-index: {z_idx};
  opacity: {opacity:.2f};
  mix-blend-mode: {blend};
  display: block;
}}
.{layer_class} img {{
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}}
"""
            desktop_rules.append(d_rule.strip())

            # === 2. Regra para MOBILE ===
            if target == "desktop" or mobile_behavior == "hide":
                m_rule = f".{layer_class} {{ display: none !important; }}"
            elif mobile_mode == "proportional" or mobile_behavior == "absolute":
                m_rule = f"""
.{layer_class} {{
  position: absolute !important;
  left: {left_pct:.4f}% !important;
  top: {top_pct:.4f}% !important;
  width: {w_pct:.4f}% !important;
  height: {h_pct:.4f}% !important;
  z-index: {z_idx} !important;
  opacity: {opacity:.2f} !important;
  mix-blend-mode: {blend} !important;
  display: block !important;
}}
"""
            elif mobile_behavior == "bg":
                m_rule = f"""
.{layer_class} {{
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  width: 100% !important;
  height: 100% !important;
  z-index: 0 !important;
  opacity: {opacity:.2f} !important;
  display: block !important;
  pointer-events: none !important;
}}
.{layer_class} img {{
  width: 100% !important;
  height: 100% !important;
  object-fit: cover !important;
}}
"""
            else:  # mobile_behavior == "stack"
                align_style = "margin: 0 auto !important;"
                img_style = "width: auto !important; max-width: 100% !important;"

                if mobile_align == "full":
                    align_style = "width: 100% !important; margin: 0 !important;"
                    img_style = "width: 100% !important; height: auto !important;"
                elif mobile_align == "left":
                    align_style = "margin-right: auto !important; margin-left: 0 !important;"
                elif mobile_align == "right":
                    align_style = "margin-left: auto !important; margin-right: 0 !important;"

                m_rule = f"""
.{layer_class} {{
  position: relative !important;
  max-width: 100% !important;
  height: auto !important;
  order: {mobile_order} !important;
  z-index: {z_idx} !important;
  opacity: {opacity:.2f} !important;
  mix-blend-mode: {blend} !important;
  display: block !important;
  {align_style}
}}
.{layer_class} img {{
  {img_style}
  height: auto !important;
  display: block !important;
}}
"""
            mobile_rules.append(m_rule.strip())

            # Identificadores de dispositivo no elemento
            device_badge = "Web & Mobile"
            if target == "desktop": device_badge = "Apenas Web"
            elif target == "mobile": device_badge = "Apenas Mobile"

            element = f"""
        <div class="psd-layer {layer_class}"
             id="layer_{idx}"
             data-name="{info['name']}"
             data-device="{target}"
             data-mobile-behavior="{mobile_behavior}"
             data-x="{rel_left}"
             data-y="{rel_top}"
             data-w="{w}"
             data-h="{h}"
             data-opacity="{int(opacity * 100)}%"
             title="{info['name']} [{device_badge}] ({w}×{h}px)">
          <img src="{img_src}" alt="{info['name']}" loading="lazy" />
        </div>"""
            layer_elements.append(element)

        layers_html = "\n".join(layer_elements)
        desktop_css_content = "\n\n".join(desktop_rules)
        mobile_css_content = "\n\n".join(mobile_rules)

        full_css = f"""/* CSS da Composição PSD - Otimizada para Web & Mobile */
* {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  background-color: #0f172a;
  color: #f8fafc;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  transition: all 0.3s ease;
}}

.psd-stage-container {{
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  transition: max-width 0.3s ease;
}}

.psd-toolbar {{
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(30, 41, 59, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  font-size: 13px;
  backdrop-filter: blur(8px);
  gap: 10px;
  flex-wrap: wrap;
}}

.psd-toolbar .title {{
  font-weight: 600;
  color: #38bdf8;
}}

.psd-toolbar .badge {{
  font-family: monospace;
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  padding: 2px 8px;
  border-radius: 4px;
}}

.device-switcher {{
  display: flex;
  gap: 4px;
  background: rgba(15, 23, 42, 0.6);
  padding: 3px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}}

.device-btn {{
  background: transparent;
  border: none;
  color: #94a3b8;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}}

.device-btn:hover {{
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}}

.device-btn.active {{
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.2);
}}

.psd-layer {{
  transition: transform 0.15s ease, filter 0.15s ease, outline 0.15s ease;
  cursor: pointer;
}}

.psd-layer:hover {{
  outline: 2px dashed #38bdf8;
  outline-offset: -2px;
}}

#layerTooltip {{
  position: fixed;
  display: none;
  background: rgba(15, 23, 42, 0.95);
  color: #fff;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-family: monospace;
  border: 1px solid #38bdf8;
  pointer-events: none;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}}

/* ======================================================== */
/* 🖥️ REGRAS DESKTOP (Web / Telas > 768px ou Modo Forçado) */
/* ======================================================== */
@media (min-width: 769px) {{
  body:not(.view-mobile) .psd-stage-container {{
    max-width: {artboard_w}px;
  }}

  body:not(.view-mobile) .psd-artboard {{
    position: relative;
    width: 100%;
    max-width: {artboard_w}px;
    aspect-ratio: {artboard_w} / {artboard_h};
    background-color: transparent;
    overflow: hidden;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }}

  body:not(.view-mobile) {desktop_css_content.replace(chr(10), chr(10) + '  body:not(.view-mobile) ')}
}}

/* Forçar visualização Desktop mesmo em telas menores */
body.view-desktop .psd-stage-container {{
  max-width: {artboard_w}px !important;
}}
body.view-desktop .psd-artboard {{
  position: relative !important;
  width: 100% !important;
  max-width: {artboard_w}px !important;
  aspect-ratio: {artboard_w} / {artboard_h} !important;
  background-color: transparent !important;
  overflow: hidden !important;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6) !important;
  border-radius: 12px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
}}
body.view-desktop {desktop_css_content.replace(chr(10), chr(10) + 'body.view-desktop ')}

/* ======================================================== */
/* 📱 REGRAS MOBILE (Telas <= 768px ou Modo Mobile Forçado) */
/* ======================================================== */
@media (max-width: 768px) {{
  body:not(.view-desktop) .psd-stage-container {{
    width: 100% !important;
    max-width: 480px !important;
    padding: 8px !important;
  }}

  body:not(.view-desktop) .psd-artboard {{
    position: relative !important;
    width: 100% !important;
    max-width: 100% !important;
    background-color: transparent !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 15px 30px rgba(0, 0, 0, 0.5) !important;
    {"aspect-ratio: auto !important; height: auto !important; min-height: 240px !important; display: flex !important; flex-direction: column !important; align-items: center !important; gap: 16px !important; padding: 24px 16px !important; overflow: visible !important;" if mobile_mode == "stack" else f"aspect-ratio: {artboard_w} / {artboard_h} !important; overflow: hidden !important;"}
  }}

  body:not(.view-desktop) {mobile_css_content.replace(chr(10), chr(10) + '  body:not(.view-desktop) ')}
}}

/* Forçar visualização Mobile no computador */
body.view-mobile .psd-stage-container {{
  width: 100% !important;
  max-width: 420px !important;
  padding: 8px !important;
}}
body.view-mobile .psd-artboard {{
  position: relative !important;
  width: 100% !important;
  max-width: 100% !important;
  background-color: transparent !important;
  border-radius: 12px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.5) !important;
  {"aspect-ratio: auto !important; height: auto !important; min-height: 240px !important; display: flex !important; flex-direction: column !important; align-items: center !important; gap: 16px !important; padding: 24px 16px !important; overflow: visible !important;" if mobile_mode == "stack" else f"aspect-ratio: {artboard_w} / {artboard_h} !important; overflow: hidden !important;"}
}}
body.view-mobile {mobile_css_content.replace(chr(10), chr(10) + 'body.view-mobile ')}
"""

        doc_title = os.path.splitext(self.filename)[0]
        html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{doc_title} - Reconstrução Web & Mobile</title>
  {"" if embed_base64 else '<link rel="stylesheet" href="style.css">'}
  {f"<style>{full_css}</style>" if embed_base64 else ""}
</head>
<body>

  <div class="psd-stage-container">
    <div class="psd-toolbar">
      <span class="title">🖼️ {doc_title}</span>
      <div style="display: flex; gap: 8px; align-items: center;">
        <span class="badge">{artboard_w} × {artboard_h} px</span>
        <span class="badge">{len(layer_elements)} Peças</span>
        {'<span class="badge" style="background:rgba(245,158,11,0.15);color:#fbbf24;border:1px solid rgba(245,158,11,0.3);">Tamanho Ajustado</span>' if is_cropped else '<span class="badge">Canvas Completo</span>'}
      </div>
      <div class="device-switcher">
        <button class="device-btn active" id="btnViewAuto" onclick="setDeviceView('auto')" title="Adapta automaticamente conforme o tamanho da tela">⚡ Auto</button>
        <button class="device-btn" id="btnViewDesktop" onclick="setDeviceView('desktop')" title="Força visualização Web / Desktop">🖥️ Web</button>
        <button class="device-btn" id="btnViewMobile" onclick="setDeviceView('mobile')" title="Força visualização Mobile">📱 Mobile</button>
      </div>
    </div>

    <!-- Artboard Renderizável do PSD -->
    <div class="psd-artboard" id="artboard" style="aspect-ratio: {artboard_w} / {artboard_h}; max-width: {artboard_w}px;">
{layers_html}
    </div>
  </div>

  <div id="layerTooltip"></div>

  <script>
    // Alternância de visualização Web vs Mobile
    function setDeviceView(mode) {{
      document.body.classList.remove('view-desktop', 'view-mobile');
      document.querySelectorAll('.device-btn').forEach(b => b.classList.remove('active'));

      if (mode === 'desktop') {{
        document.body.classList.add('view-desktop');
        document.getElementById('btnViewDesktop').classList.add('active');
      }} else if (mode === 'mobile') {{
        document.body.classList.add('view-mobile');
        document.getElementById('btnViewMobile').classList.add('active');
      }} else {{
        document.getElementById('btnViewAuto').classList.add('active');
      }}
    }}

    // Inspetor visual ao passar o mouse sobre cada camada
    const tooltip = document.getElementById('layerTooltip');
    const layers = document.querySelectorAll('.psd-layer');

    layers.forEach(l => {{
      l.addEventListener('mousemove', (e) => {{
        tooltip.style.display = 'block';
        tooltip.style.left = (e.clientX + 14) + 'px';
        tooltip.style.top = (e.clientY + 14) + 'px';
        const deviceText = l.dataset.device === 'desktop' ? 'Apenas Web' : (l.dataset.device === 'mobile' ? 'Apenas Mobile' : 'Web & Mobile');
        tooltip.innerHTML = `<strong>${{l.dataset.name}}</strong><br>Exibição: ${{deviceText}}<br>Comportamento: ${{l.dataset.mobileBehavior || 'Padrão'}}<br>Dim: ${{l.dataset.w}}×${{l.dataset.h}}px | Pos: X:${{l.dataset.x}}, Y:${{l.dataset.y}}`;
      }});

      l.addEventListener('mouseleave', () => {{
        tooltip.style.display = 'none';
      }});
    }});
  </script>
</body>
</html>
"""
        return html_content, full_css, images_bytes

    def export_html_to_zip(
        self,
        selected_indices: List[int],
        fit_to_selection: bool = True,
        responsive: bool = True,
        mobile_mode: str = "stack",
        layer_configs: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        """
        Gera um arquivo ZIP completo contendo:
        - index.html (otimizado para Web & Mobile)
        - style.css
        - images/... (peças da composição)
        """
        html_code, css_code, images_bytes = self.generate_renderable_html(
            selected_indices=selected_indices,
            embed_base64=False,
            images_dir_rel="images",
            fit_to_selection=fit_to_selection,
            responsive=responsive,
            mobile_mode=mobile_mode,
            layer_configs=layer_configs
        )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html_code)
            zf.writestr("style.css", css_code)
            for img_name, img_data in images_bytes.items():
                zf.writestr(f"images/{img_name}", img_data)

        zip_buffer.seek(0)
        return zip_buffer

    def export_html_single_file(
        self,
        selected_indices: List[int],
        fit_to_selection: bool = True,
        responsive: bool = True,
        mobile_mode: str = "stack",
        layer_configs: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Gera um arquivo HTML autônomo (single-file) com todas as peças incorporadas em Base64.
        Renderiza com suporte completo a Web e Mobile.
        """
        html_code, _, _ = self.generate_renderable_html(
            selected_indices=selected_indices,
            embed_base64=True,
            fit_to_selection=fit_to_selection,
            responsive=responsive,
            mobile_mode=mobile_mode,
            layer_configs=layer_configs
        )
        return html_code

    def export_html_to_directory(
        self,
        output_dir: str,
        selected_indices: List[int],
        embed_base64: bool = False,
        fit_to_selection: bool = True,
        responsive: bool = True,
        mobile_mode: str = "stack",
        layer_configs: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Salva o pacote HTML renderizável em uma pasta local do computador.
        """
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []

        html_code, css_code, images_bytes = self.generate_renderable_html(
            selected_indices=selected_indices,
            embed_base64=embed_base64,
            images_dir_rel="images",
            fit_to_selection=fit_to_selection,
            responsive=responsive,
            mobile_mode=mobile_mode,
            layer_configs=layer_configs
        )

        html_path = os.path.join(output_dir, "index.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_code)
        saved_paths.append(html_path)

        if not embed_base64:
            css_path = os.path.join(output_dir, "style.css")
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(css_code)
            saved_paths.append(css_path)

            images_dir = os.path.join(output_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
            for img_name, img_data in images_bytes.items():
                img_path = os.path.join(images_dir, img_name)
                with open(img_path, "wb") as f:
                    f.write(img_data)
                saved_paths.append(img_path)

        return saved_paths
