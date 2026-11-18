"""
Script utilitário para gerar um arquivo PSD de exemplo para testes.
Cria 'banner_exemplo.psd' com múltiplas camadas, formas, textos e transparências.
"""

from PIL import Image, ImageDraw
from psd_tools import PSDImage

def criar_psd_exemplo(output_path="banner_exemplo.psd"):
    width, height = 800, 500
    psd = PSDImage.new("RGBA", (width, height))

    # Camada 1: Fundo com degradê/cor sólida
    fundo = Image.new("RGBA", (width, height), (15, 23, 42, 255))
    d_fundo = ImageDraw.Draw(fundo)
    # Detalhes no fundo
    for i in range(0, width, 40):
        d_fundo.line([(i, 0), (i, height)], fill=(30, 41, 59, 120), width=1)
    layer_fundo = psd.create_pixel_layer(fundo)
    layer_fundo.name = "Fundo Tecnológico"

    # Camada 2: Cartão / Container Central
    card = Image.new("RGBA", (500, 280), (30, 41, 59, 230))
    d_card = ImageDraw.Draw(card)
    d_card.rounded_rectangle([0, 0, 500, 280], radius=16, fill=(30, 41, 59, 240), outline=(56, 189, 248, 255), width=2)
    layer_card = psd.create_pixel_layer(card)
    layer_card.name = "Card Central"
    layer_card.offset = (150, 110)

    # Camada 3: Círculo / Ícone
    icone = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    d_ico = ImageDraw.Draw(icone)
    d_ico.ellipse([5, 5, 95, 95], fill=(2, 132, 199, 255), outline=(255, 255, 255, 200), width=3)
    d_ico.polygon([(35, 30), (75, 50), (35, 70)], fill=(255, 255, 255, 255))
    layer_ico = psd.create_pixel_layer(icone)
    layer_ico.name = "Botão Play"
    layer_ico.offset = (350, 150)

    # Camada 4: Selo / Badge Promocional
    badge = Image.new("RGBA", (140, 50), (0, 0, 0, 0))
    d_badge = ImageDraw.Draw(badge)
    d_badge.rounded_rectangle([0, 0, 140, 50], radius=8, fill=(245, 158, 11, 255), outline=(255, 255, 255, 255), width=2)
    layer_badge = psd.create_pixel_layer(badge)
    layer_badge.name = "Selo Destaque"
    layer_badge.offset = (170, 85)

    # Camada 5: Elemento de Brilho / Overlay
    glow = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    d_glow = ImageDraw.Draw(glow)
    d_glow.ellipse([20, 20, 140, 140], fill=(56, 189, 248, 80))
    layer_glow = psd.create_pixel_layer(glow)
    layer_glow.name = "Brilho Neon"
    layer_glow.offset = (320, 120)

    psd.append(layer_fundo)
    psd.append(layer_card)
    psd.append(layer_glow)
    psd.append(layer_ico)
    psd.append(layer_badge)

    psd.save(output_path)
    print(f"PSD de exemplo criado com sucesso: '{output_path}'")

if __name__ == "__main__":
    criar_psd_exemplo()
