# Extrator de Imagens e Camadas de PSD (Photoshop)

Aplicação completa em Python com **Frontend Web moderno** e **Frontend Desktop nativo (Tkinter)** para visualização, inspeção e extração de camadas e imagens completas de arquivos Photoshop (`.psd` e `.psb`).

---

## 🚀 Funcionalidades

- **Frontend Web Moderno (Flask + HTML5/CSS3)**:
  - Arraste e solte (*Drag & Drop*) para carregar arquivos PSD/PSB de qualquer tamanho.
  - Pré-visualização em alta resolução da imagem composta completa (*Composite*).
  - Grade visual com miniaturas (*thumbnails*) de cada camada com fundo xadrez (*checkerboard*) de transparência.
  - Informações detalhadas de cada camada: Dimensões ($L \times A$), Posição ($X, Y$), Opacidade, Tipo (Pixel, Texto, Smart Object, Grupo, Forma) e Visibilidade.
  - Filtros dinâmicos em tempo real: Busca por nome de camada, filtro por tipo e filtro de apenas visíveis.
  - Seleção em massa (*Marcar Todas*, *Desmarcar*, *Inverter*).
  - Download rápido de camada individual com 1 clique.
  - Exportação em lote para arquivo **.ZIP** ou diretamente para uma **pasta local** no computador.

- **Frontend Desktop Nativo (Tkinter)**:
  - Janela nativa do Windows sem necessidade de navegador.
  - Lista de camadas com caixas de seleção, pré-visualização interativa ao clicar em qualquer camada.
  - Exportação direta para pasta ou arquivo ZIP.

- **Modos e Formatos de Exportação**:
  - **Formatos**:
    - **PNG**: Preserva canal alfa de transparência intacto.
    - **WEBP**: Formato moderno de alta taxa de compressão e suporte a transparência.
    - **JPEG**: Com ajuste de qualidade (10–100%) e mesclagem sobre fundo branco.
  - **Modos de Corte**:
    - **Camada Recortada (Trim/Bounds)**: Extrai apenas a área delimitadora (*bounding box*) com os pixels exatos da camada.
    - **Canvas Completo**: Renderiza a camada preservando o tamanho e a posição exata no canvas original do PSD (ideal para montagens e jogos).

---

## 📦 Estrutura do Projeto

```
extrai_psd/
│
├── app.py                  # Servidor backend Flask e API REST
├── extractor.py            # Motor de processamento PSD (psd-tools + Pillow)
├── gui_desktop.py          # Interface gráfica desktop nativa (Tkinter)
├── gerar_psd_exemplo.py    # Utilitário para gerar PSD de teste com várias camadas
├── banner_exemplo.psd      # Arquivo PSD de exemplo pronto para testar
├── requirements.txt        # Dependências do projeto
│
├── templates/
│   └── index.html          # Frontend web responsivo
│
├── iniciar.bat             # Menu interativo para iniciar Web ou Desktop
├── iniciar_web.bat         # Inicia diretamente a interface Web
└── iniciar_desktop.bat     # Inicia diretamente a interface Desktop
```

---

## 🛠️ Como Usar

### Opção 1: Menu Geral (Recomendado)
Dê um duplo clique no arquivo:
```cmd
iniciar.bat
```
Escolha a opção desejada no terminal:
- `1` para Interface Web
- `2` para Interface Desktop
- `3` para recriar o PSD de exemplo

### Opção 2: Interface Web Direta
Dê um duplo clique em:
```cmd
iniciar_web.bat
```
Ou pelo terminal:
```bash
python app.py
```
O servidor será iniciado e abrirá automaticamente o navegador em `http://127.0.0.1:5000`.

### Opção 3: Interface Desktop Direta
Dê um duplo clique em:
```cmd
iniciar_desktop.bat
```
Ou pelo terminal:
```bash
python gui_desktop.py
```

---

## 📋 Dependências

As seguintes bibliotecas já estão instaladas no ambiente:
- `psd-tools>=1.27.0` (leitura avançada da especificação PSD/PSB)
- `Pillow>=11.0.0` (processamento e conversão de imagens)
- `Flask>=3.0.0` (servidor web e rotas de API)

Para reinstalar em outro ambiente:
```bash
pip install -r requirements.txt
```
