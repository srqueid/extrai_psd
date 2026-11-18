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

- **🌐 Reconstrução e Renderização HTML (Web & Mobile)**:
  - Reconstrói a composição visual do PSD em **HTML e CSS puros** utilizando as peças recortadas.
  - **Seleção Dinâmica de Peças Renderizáveis**:
    - Escolha exatamente quais camadas participam da composição HTML (via checkbox no card da camada ou no **checklist lateral interativo** dentro da própria aba de Render HTML).
    - Ações rápidas: *Todas*, *Nenhuma* ou *Apenas Visíveis*.
    - **Enquadramento Perfeito (Bounding Box Fit)**: O contêiner se recalcula automaticamente para as dimensões exatas das peças selecionadas, evitando margens ou espaços vazios gigantes.
  - **Renderização Diferenciada por Peça (Web vs Mobile)**:
    - **Alvo de Dispositivo**: Escolha se cada peça aparece em `🖥️+📱 Ambos`, `🖥️ Apenas Web` ou `📱 Apenas Mobile`.
    - **Comportamento no Mobile**:
      - *Vertical (Stack)*: Transforma peças horizontais em blocos empilhados legíveis em smartphones.
      - *Absoluto*: Mantém a posição proporcional e escalonada.
      - *Fundo (Cover)*: Ajusta imagens de background para cobrir o contêiner mobile.
      - *Ocultar*: Esconde a peça em telas menores.
    - **Alinhamento no Mobile**: Centralizado, Largura Total (100%), Esquerda ou Direita.
  - **Simulador Interativo de Viewport**:
    - Alterne entre visualizações `🖥️ Web (100%)`, `💻 Tablet (768px)`, `📱 Mobile (375px)` e `📱 Mobile Grande (414px)`.
  - Posicionamento proporcional (`%`) e responsivo com `aspect-ratio` que se ajusta com precisão a qualquer tela ou dispositivo.
  - Preserva a hierarquia original de profundidade (`z-index`), opacidade e modos de mesclagem (`mix-blend-mode`).
  - **Aba de Pré-visualização Interativa (Live Render)** com inspetor flutuante (*hover revela nome da camada, coordenadas X/Y e dimensões*).
  - **Opções de Exportação HTML**:
    1. **Pacote Completo (.ZIP)**: Contendo `index.html`, `style.css` e a pasta `images/` apenas com as peças escolhidas.
    2. **Arquivo Único (.HTML)**: Arquivo autônomo com todas as imagens embutidas em Base64 Data URI (abre diretamente em qualquer computador sem precisar de pastas anexas).
    3. **Salvar em Pasta Local**: Grava a estrutura `index.html` + `style.css` + `images/` diretamente em um diretório do computador.
    4. **Copiar Código Fonte**: Permite visualizar e copiar o HTML e CSS gerados com 1 clique.

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
