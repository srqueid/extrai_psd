"""
Módulo de Extração de Imagens e Camadas de PSD (Photoshop)
Utiliza psd-tools e Pillow para manipulação e exportação.
"""

import io
import os
import re
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
