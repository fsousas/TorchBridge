# CONFIGURAÇÃO DE ATALHOS NO TORCHLIGHT

Reorganizar os itens no menu radial para poder suportar mais uma opção
# FASE 1
## AO ABRIR O MENU RADIAL
Devemos mostrar uma nova opção:
- `assets\images\radial-menu-icons\short-cut.png`
- `assets\images\radial-menu-icons\short-cut-ativo.png`

Referente à configuração dos atalhos na parte inferior da tela.
- O menu radial agora passa a suportar 8 opções distribuídas uniformemente (fatias de 45°).
- Ao selecionar e confirmar essa opção no menu radial, o menu radial fecha e ativa o modo de configuração de atalhos.

## MODO CONFIGURAÇÃO DE ATALHOS ATIVO
- **Transição de Entrada / Saída:**
  - O backdrop entra e sai suavemente com **Fade In / Fade Out** a 60 FPS (duração ~0.35s).
- **Backdrop e Spotlight:**
  - Tela escura com **backdrop preto de 70% de opacidade** (`rgba(0, 0, 0, 0.70)`).
  - Efeito de **spotlight / recorte inverso** na parte inferior da tela utilizando:
    - `assets\hud\inferior\mask-hud.png`
  - Centralizado horizontalmente (`offset_x = (largura - mask_w) / 2`) e colado na borda inferior (`offset_y = 0`), escalado proporcionalmente a 1280 x 960.
- **Banner de Instruções:**
  - Elemento posicionado acima do backdrop, carregando dinamicamente a arte correspondente ao controle ativo:
    - `assets\images\instructions\shortcut-instruction-ps.png` (PlayStation)
    - `assets\images\instructions\shortcut-instruction-xbox.png` (Xbox)
    - `assets\images\instructions\shortcut-instruction-nintendo.png` (Nintendo)
  - **Animação de Descida / Subida:**
    - Ao entrar: desce do topo (fora da tela) e para suavemente no centro com desaceleração (*cubic ease-out*).
    - Ao sair: sobe de volta para fora da tela (*slide-up*) enquanto o backdrop faz fade-out.

## SAÍDA DO MODO DE ATALHOS
- O usuário sai do modo de configuração e retorna ao jogo normal ao pressionar o **botão Leste** (Bolinha / B / East Button) ou **Start / ESC**.
- Ao sair, a imagem sobe de volta para fora da tela e o backdrop desaparece em fade-out suave.

## FASE 2
- Os nós devem respeitar o redimencionamento e posicao da hud 

### Mapeamento dos nós de navegação no modo de configuração de atalhos ativado
- Os slots de skill e itens na hud inferior da tela devem ser acessados e navegaveispelo d-pad do controle sempre respeitando os nós na imagem:
- `assets\hud\inferior\nodes.png` imagem em 1280 x 960
- Nessa imagem existem 2 tipos de quadrados:
- Amarelo #E6C12A - Onde o cursor deve ser posicionado ao ativar o modo de configuração
- Verde #09B200 - Nós navegaveis pelo D-pad

- Ao estar em um nó amarelo ou verde e:
    - Pressionarmos o botao norte do controle (Triangulo no ps ou Y no xbox ou X no nintendo ) deve ser disparado o ctrl+clique esquerdo
    - Precssionarmos o botao sul do controle (X no ps ou A no xbox ou leste no nintendo A) deve ser disparado o botao esquerdo para abrir o grid de opções


## FASE 3: MAPEAMENTO E NAVEGAÇÃO NO GRID DE OPÇÕES

### 1. Diagnóstico do Conflito Visual com o Backdrop (`assets\hud\inferior\bug-backdrop.png`)
- **Problema Identificado:**
  - O pop-up com o grid de opções é renderizado nativamente pelo motor do Torchlight na camada do jogo.
  - Como o overlay do TorchBridge desenha um backdrop preto de 70% (`rgba(0, 0, 0, 0.70)`) com recorte apenas na barra inferior da HUD, a janela de opções surge **por trás da máscara escura**, ficando escurecida e com a placa de instruções pendurada no meio cobrindo parcialmente o grid.
- **Soluções Arquiteturais Avaliadas:**
  - **Opção 1 (Transição Inteligente de Estado - Recomendada):**
    - Ao pressionar o botão Sul (`A` / `X`) em um nó para abrir o grid de opções, o sistema transita para o sub-estado `shortcut_grid_active`.
    - Nesse sub-estado, o backdrop preto de 70% faz **fade-out** (ou opacidade 0%) e a placa de instruções central sobe/some, liberando visão total para o grid nativo do jogo e o cenário.
    - Ao confirmar com Sul (`A`) ou cancelar com Leste (`B`), o grid fecha e o overlay retorna ao modo de seleção de slots (restaurando o spotlight suavemente).
  - **Opção 2 (Remoção Definitiva do Backdrop Preto):**
    - Descartar o backdrop escuro de 70% em todo o modo de configuração, utilizando apenas o recorte sutil ou indicadores visuais diretos nos nós (sem escurecer a tela inteira).

---

### 2. Análise Estrutural e Comportamento do Grid Nativo
A partir da análise comparativa das 10 imagens capturadas:
- `assets\hud\inferior\abrir-grid.png`
- `assets\hud\inferior\abrir-grid-skill-spell.png`
- `assets\hud\inferior\abrir-grid-skill-spell-2.png`
- `assets\hud\inferior\abrir-grid-skill-spell-3.png`
- `assets\hud\inferior\abrir-grid-skill-spell-4.png`
- `assets\hud\inferior\abrir-grid-skill-spell-5.png`
- `assets\hud\inferior\abrir-grid-skill-spell-6.png`
- `assets\hud\inferior\abrir-grid-skill-spell-7.png`
- `assets\hud\inferior\abrir-grid-skill-spell-8.png`
- `assets\hud\inferior\abrir-grid-skill-spell-9.png`

#### A. Filtros Específicos por Tipo de Slot:
1. **Slot do Clique Esquerdo (Ataque Primário - Mais Restritivo):**
   - Na **Linha 1, Índice 0**: Exibe o ícone de **Ataque Físico Básico**.
   - Seguido apenas por **skills ativas adquiridas de Nível 1** compatíveis com o botão esquerdo.
   - **NÃO exibe feitiços (spells)** e **NÃO exibe consumíveis/itens**.
2. **Slot do Clique Direito (Ataque Secundário) e Slot de Troca Rápida (Tab) (`abrir-grid-skill-spell-2.png`, `4.png`, `9.png`):**
   - Exibem **Skills Ativas (de todos os níveis)** + **Feitiços Aprendidos (Spells)**.
   - **NÃO exibem itens/consumíveis**.
3. **Slots Numéricos de Ação (1 a 0 / Nós de atalho geral) (`abrir-grid.png`, `abrir-grid-skill-spell-3.png`):**
   - Aceitam **tudo**: Skills Ativas + Feitiços (Spells) + Itens Consumíveis de Inventário.

#### B. Hierarquia, Regras de Tiers e Ordenação das Linhas:
- **Linhas 1 a 6 (Skills Ativas por Faixa de Nível):**
  - Cada linha representa um tier de 5 níveis de habilidades ativas (não-passivas) adquiridas:
    - **Linha 1:** Skills de Nível 1
    - **Linha 2:** Skills de Nível 5
    - **Linha 3:** Skills de Nível 10
    - **Linha 4:** Skills de Nível 15
    - **Linha 5:** Skills de Nível 20
    - **Linha 6:** Skills de Nível 25
  - **Regra de Omissão de Linhas Vazias:** Se o personagem não tiver nenhuma skill ativa adquirida naquele nível específico, **a linha correspondente NÃO existe** e não ocupa espaço vertical vazio no grid.
- **Feitiços (Spells):**
  - Os feitiços aprendidos pelo jogador (até 4 spells equipados na ficha do personagem, como visto em `abrir-grid-skill-spell-6.png`) são exibidos **diretamente na Linha 1**, anexados à direita das skills de nível 1.
- **Linhas de Itens Utilizáveis (Consumíveis):**
  - Exibidos logo abaixo das linhas de skills (geralmente Linha 7 em personagens avançados, ou logo após a última linha de skill presente):
  - Agrupa itens da **aba de Inventário** (poções, pergaminhos) + itens da **aba de Peixes**.
  - Pode expandir a altura do grid para 8, 9 ou até 10 linhas dependendo da quantidade de consumíveis diferentes utilizáveis.

#### C. Regra Crítica de Quantidade de Colunas:
- **Quem define as colunas:** A linha de itens utilizáveis **NÃO** expande a quantidade de colunas; ela apenas se dobra em novas linhas para respeitar a largura estabelecida.
- **A Linha 1 (Skills Lv 1 + Spells)** e as linhas de skills de classe são as **responsáveis por ditar a quantidade total de colunas do grid**.
- **Limite Máximo:** O grid comporta no máximo **8 colunas** horizontais.

#### D. Geometria e Posicionamento na Tela:
- **Posicionamento Vertical:** A base do grid é colada logo acima da HUD inferior (`grid_bottom = hud_top`).
- **Posicionamento Horizontal (Âncora com Clamping e Alinhamento por Lado):**
  - **Slots da Esquerda (1 a 5 e Clique Esquerdo):** O grid abre deslocado para a direita em relação ao slot selecionado (`start_x = slot_x + 78.12 * scale`).
  - **Slots da Direita (Clique Direito, Tab, 6 a 0 - Clamping):** Como esses slots ficam na metade direita da HUD, o grid faz clamping colado à borda direita da janela (`max_right = rect.right - 44.0 * scale`), garantindo que a Coluna 1 fique perfeitamente alinhada sobre o primeiro item do grid.
- **Dimensões e Pitch Calibrados:** Espaçamento entre nós (pitch) de $48\text{ px}$ na base 768p ($60\text{ px}$ na base 960p, escalado por `rect.height / 768.0`), eliminando qualquer desvio cumulativo entre as colunas e linhas.

---

### 3. Estrutura Interna Mapeada por Engenharia Reversa (CEGUI)

Através da varredura direta no processo ativo do jogo via `CEGUIBase.dll`:
- **Janela Base do Grid:** `gui__3501Base`
- **Células da Matriz:** `gui__3501SkillIcon<Linha><Coluna>`
- **Dimensões das Células:** $62.5 \times 62.5\text{ px}$ com pitch de $65.1\text{ px}$ (gap de $2.6\text{ px}$) na escala $1280 \times 960$.
- **Linhas e Colunas (Confirmado nos Prints):**
  - **Largura Máxima:** 8 colunas (ditadas pelas skills ativas e spells da Linha 1).
  - **Itens de Inventário / Consumíveis:** Preenchem a largura de 8 colunas e dobram automaticamente em novas linhas (ex: 3 linhas no print inicial; 4 linhas ao adquirir mais poções).

---

### 4. Implementação Concluída da Fase 3

1. **Bug do Backdrop Resolvido:**
   - Quando o grid de atalhos está ativo (`shortcut_grid_active = True`), a opacidade da máscara escura do spotlight transiciona para **0% (invisível)**, deixando o popup nativo do jogo 100% visível e nítido.
   - A placa suspensa de instruções de controle permanece na tela.
2. **Adaptação Dinâmica de Colunas e Linhas por Categoria de Slot:**
   - **Clique Esquerdo (Ataque, Nó 5):** Filtra e exibe **apenas Ataque Físico + Skills ativas de Nível 1** (sem spells e sem consumíveis). Grid fixo de **1 linha $\times$ 3 colunas**, diretamente acima do botão de ataque.
   - **Clique Direito e Tab (Nós 6 e 7):** Filtra e exibe **apenas Skills ativas + Spells equipados** (sem consumíveis). Grid de **2 linhas $\times$ 7 colunas** (ou total de skills/spells), posicionado acima do botão direito/tab.
   - **Slots 1 a 5 (Nós 0 a 4):** Exibe Skills + Spells + Consumíveis (itens de inventário e peixes). Grid de **7 colunas $\times$ 3 linhas** (ou ajustável pela memória), alinhado com o slot selecionado deslocado 1 bloco para a direita.
   - **Slots 6 a 0 (Nós 8 a 12):** Exibe Skills + Spells + Consumíveis. Grid de **8 colunas $\times$ 4 linhas**, com **clamping automático na margem direita** (`rect.right - 46px`) para que o popup não ultrapasse o limite da tela.
   - **Ancoragem Vertical Real:** O grid repousa logo acima da barra inferior de atalhos e se expande **PARA CIMA** a partir da base (`rect.bottom - 112px * scale`), mantendo a última linha sempre fixa e o topo ajustado conforme `num_rows`.
   - **Centralização Fina:** O ponto de partida horizontal aplica deslocamento de `+78.12px * scale` com clamping direito em `rect.right - 72px * scale`, centralizando com exatidão sobre os ícones das células do grid nativo.
3. **Leitura Dinâmica da Memória (CEGUI Base Dinâmica):**
   - O método `TorchlightMemoryReader.read_shortcut_grid_dims()` resolve dinamicamente a base de `CEGUIBase.dll` e a RVA `0x001B4844` (`ms_Singleton` do `WindowManager`), buscando a janela `gui__3501Base` em tempo real.
   - Lê a largura e altura na hora e adapta `cols` e `rows` perfeitamente, mesmo com ASLR e reloads do jogo.
4. **Ciclo de Controle do Grid:**
   - **Abertura do Grid:** Pressionar **Sul (A / X)** em qualquer nó da HUD dispara clique esquerdo, abre o pop-up nativo e ativa `shortcut_grid_active = True`, posicionando o cursor na célula `(0, 0)`.
   - **Navegação 2D no D-pad:** O D-pad (Cima, Baixo, Esquerda, Direita) navega na matriz `(row, col)` respeitando a quantidade de itens por linha e move o cursor suavemente ao centro da célula.
   - **Confirmação (Botão A / X):** Clica na célula selecionada, associando a habilidade/item ao slot, fecha o grid e devolve o cursor ao nó correspondente da HUD.
   - **Cancelamento (Botão B / Bolinha ou Start/ESC):** Fecha o popup do grid e devolve o foco para a navegação de nós da HUD.
5. **Modo Calibração (`show_calibration: True`):**
   - Desenha as caixas delimitadoras de todas as células do grid na tela com destaque amarelo na célula em foco perfeitamente sobreposta aos ícones reais do jogo.

 