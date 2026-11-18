"""
Servidor Web Flask para o Extrator de PSD
Interface interativa, visualização de camadas e exportação em ZIP ou pasta local.
"""

import io
import os
import sys
import uuid
import socket
import logging
import tempfile
import webbrowser
import threading
from typing import Dict
from flask import Flask, render_template, request, jsonify, send_file, Response
from PIL import Image

from extractor import PSDExtractor

# Configuração da aplicação Flask
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB limite para PSDs pesados

# Armazenamento temporário de sessões em memória / diretório temporário
SESSIONS: Dict[str, Dict] = {}
TEMP_DIR = tempfile.mkdtemp(prefix="psd_extractor_")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PSDExtractorApp")


def get_available_port(default_port=5000):
    """Encontra uma porta disponível iniciando na porta padrão."""
    port = default_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
            port += 1
    return default_port


@app.route('/')
def index():
    """Página principal da interface web."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_psd():
    """Recebe o upload do arquivo PSD e processa sua estrutura."""
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"error": "Arquivo inválido ou vazio"}), 400

    filename = file.filename
    if not filename.lower().endswith(('.psd', '.psb')):
        return jsonify({"error": "Formato não suportado. Por favor, envie um arquivo .psd ou .psb"}), 400

    session_id = str(uuid.uuid4())
    session_file_path = os.path.join(TEMP_DIR, f"{session_id}_{filename}")
    file.save(session_file_path)

    try:
        extractor = PSDExtractor(session_file_path, filename=filename)
        info = extractor.get_info()
        layers = extractor.get_layers_info()

        SESSIONS[session_id] = {
            "path": session_file_path,
            "filename": filename,
            "extractor": extractor,
            "thumbs_cache": {}
        }

        return jsonify({
            "session_id": session_id,
            "info": info,
            "layers": layers
        })
    except Exception as e:
        logger.error(f"Erro ao processar PSD: {e}", exc_info=True)
        if os.path.exists(session_file_path):
            try:
                os.remove(session_file_path)
            except Exception:
                pass
        return jsonify({"error": f"Falha ao ler o arquivo PSD: {str(e)}"}), 500


@app.route('/api/preview/<session_id>')
def get_preview(session_id):
    """Retorna a imagem completa (composite) do PSD em tamanho otimizado para pré-visualização."""
    session = SESSIONS.get(session_id)
    if not session:
        return "Sessão não encontrada", 404

    try:
        extractor: PSDExtractor = session["extractor"]
        comp = extractor.get_composite_image()
        if not comp:
            return "Imagem indisponível", 404

        # Redimensiona proporcionalmente para preview leve se for gigantesca
        max_dim = 1600
        preview_img = comp.copy()
        if preview_img.width > max_dim or preview_img.height > max_dim:
            preview_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        img_io = io.BytesIO()
        preview_img.save(img_io, format="PNG", optimize=True)
        img_io.seek(0)

        return send_file(img_io, mimetype="image/png")
    except Exception as e:
        logger.error(f"Erro ao gerar preview do PSD: {e}")
        return str(e), 500


@app.route('/api/thumbnail/<session_id>/<int:layer_index>')
def get_thumbnail(session_id, layer_index):
    """Retorna o thumbnail da camada especificada."""
    session = SESSIONS.get(session_id)
    if not session:
        return "Sessão não encontrada", 404

    thumbs_cache = session["thumbs_cache"]
    if layer_index in thumbs_cache:
        return send_file(io.BytesIO(thumbs_cache[layer_index]), mimetype="image/png")

    try:
        extractor: PSDExtractor = session["extractor"]
        layer_img = extractor.render_layer_image(layer_index, mode="cropped", format_type="PNG")

        if layer_img is None:
            # Cria thumbnail vazio / placeholder
            placeholder = Image.new("RGBA", (80, 80), (200, 200, 200, 30))
            img_io = io.BytesIO()
            placeholder.save(img_io, format="PNG")
            img_io.seek(0)
            return send_file(img_io, mimetype="image/png")

        thumb = extractor.generate_thumbnail(layer_img, max_size=(160, 160))
        img_io = io.BytesIO()
        thumb.save(img_io, format="PNG")
        thumb_bytes = img_io.getvalue()
        thumbs_cache[layer_index] = thumb_bytes

        img_io.seek(0)
        return send_file(img_io, mimetype="image/png")
    except Exception as e:
        logger.error(f"Erro ao gerar thumbnail da camada {layer_index}: {e}")
        placeholder = Image.new("RGBA", (80, 80), (255, 0, 0, 50))
        img_io = io.BytesIO()
        placeholder.save(img_io, format="PNG")
        img_io.seek(0)
        return send_file(img_io, mimetype="image/png")


@app.route('/api/export/single/<session_id>/<int:layer_index>')
def export_single_layer(session_id, layer_index):
    """Exporta e baixa diretamente uma única camada."""
    session = SESSIONS.get(session_id)
    if not session:
        return "Sessão não encontrada", 404

    mode = request.args.get("mode", "cropped")
    format_type = request.args.get("format", "PNG").upper()
    quality = int(request.args.get("quality", 90))

    try:
        extractor: PSDExtractor = session["extractor"]
        layer_info = next((l for l in extractor.get_layers_info() if l["index"] == layer_index), None)
        layer_img = extractor.render_layer_image(layer_index, mode=mode, format_type=format_type)

        if not layer_img:
            return "Camada não pôde ser renderizada", 400

        ext = "jpg" if format_type in ["JPG", "JPEG"] else format_type.lower()
        save_format = "JPEG" if ext == "jpg" else format_type
        clean_name = layer_info["safe_name"] if layer_info else f"camada_{layer_index+1}"
        filename = f"{clean_name}.{ext}"

        img_io = io.BytesIO()
        save_kwargs = {"format": save_format}
        if save_format in ["JPEG", "WEBP"]:
            save_kwargs["quality"] = quality
        layer_img.save(img_io, **save_kwargs)
        img_io.seek(0)

        mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
        return send_file(img_io, mimetype=mime, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Erro na exportação avulsa: {e}")
        return str(e), 500


@app.route('/api/export/zip', methods=['POST'])
def export_zip():
    """Gera um arquivo ZIP com as camadas selecionadas e/ou o composite."""
    data = request.json or {}
    session_id = data.get("session_id")
    session = SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Sessão não encontrada"}), 404

    selected_indices = data.get("selected_indices", [])
    include_composite = bool(data.get("include_composite", False))
    mode = data.get("mode", "cropped")
    format_type = data.get("format", "PNG").upper()
    quality = int(data.get("quality", 90))

    if not selected_indices and not include_composite:
        return jsonify({"error": "Nenhuma camada ou imagem composta foi selecionada para exportar"}), 400

    try:
        extractor: PSDExtractor = session["extractor"]
        zip_buffer = extractor.export_selection_to_zip(
            selected_indices=selected_indices,
            include_composite=include_composite,
            mode=mode,
            format_type=format_type,
            quality=quality
        )

        base_name = os.path.splitext(session["filename"])[0]
        zip_filename = f"{base_name}_imagens_extraidas.zip"

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=zip_filename
        )
    except Exception as e:
        logger.error(f"Erro ao gerar ZIP: {e}", exc_info=True)
        return jsonify({"error": f"Erro ao gerar ZIP: {str(e)}"}), 500


@app.route('/api/export/folder', methods=['POST'])
def export_folder():
    """Salva as imagens diretamente em uma pasta local do computador."""
    data = request.json or {}
    session_id = data.get("session_id")
    session = SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Sessão não encontrada"}), 404

    output_dir = data.get("output_dir", "").strip()
    if not output_dir:
        return jsonify({"error": "Caminho da pasta de destino não informado"}), 400

    selected_indices = data.get("selected_indices", [])
    include_composite = bool(data.get("include_composite", False))
    mode = data.get("mode", "cropped")
    format_type = data.get("format", "PNG").upper()
    quality = int(data.get("quality", 90))

    try:
        extractor: PSDExtractor = session["extractor"]
        saved_files = extractor.export_to_directory(
            output_dir=output_dir,
            selected_indices=selected_indices,
            include_composite=include_composite,
            mode=mode,
            format_type=format_type,
            quality=quality
        )

        return jsonify({
            "success": True,
            "saved_count": len(saved_files),
            "output_dir": output_dir,
            "files": [os.path.basename(f) for f in saved_files]
        })
    except Exception as e:
        logger.error(f"Erro ao salvar na pasta local: {e}", exc_info=True)
        return jsonify({"error": f"Erro ao salvar na pasta: {str(e)}"}), 500


def open_browser(port):
    """Abre o navegador automaticamente."""
    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)


def run_app(port=None, auto_open=True):
    """Inicia o servidor web."""
    if port is None:
        port = get_available_port(5000)

    print(f"\n=======================================================")
    print(f"  EXTRATOR DE IMAGENS DE PSD (Photoshop)")
    print(f"  Servidor rodando em: http://127.0.0.1:{port}")
    print(f"  Pressione Ctrl+C para encerrar o servidor.")
    print(f"=======================================================\n")

    if auto_open:
        threading.Timer(1.0, open_browser, args=(port,)).start()

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    run_app(port=port_arg, auto_open=True)
