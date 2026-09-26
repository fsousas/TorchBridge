# Progresso da Investigação: Leitura e Inspeção de Memória do Torchlight 1

Este documento registra o avanço técnico da engenharia reversa do executável `Torchlight.exe`, a identificação e correção da causa do reinício do computador, a cadeia completa de ponteiros e offsets estáticos mapeados e o detector de estado da tela principal e overlays.

---

## 1. Resumo Executivo
- O executável do Torchlight 1 é **32-bit (x86)** em ambas as edições (GOG e Steam), mas com diferenças de empacotamento:
  - **Versão GOG (Standalone)**: **NÃO possui ASLR** (Dynamic Base desativado, tamanho ~9,13 MB). Carrega no endereço base fixo `0x00400000`, e o ponteiro mestre `CGame` reside no RVA `0x0081AD64` (endereço estático `0x00C1AD64`).
  - **Versão Steam**: Possui **ASLR ativado** (`IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE = True`, tamanho ~10,71 MB por conta das camadas Steamworks). O endereço base é dinâmico a cada inicialização, e o ponteiro mestre `CGame` reside no RVA `0x007F0E0C`.
- **Compatibilidade Universal**: Implementamos resolução dinâmica de base de módulo (`EnumProcessModulesEx` e `TH32CS_SNAPMODULE`) e auto-detecção de versão (GOG / Steam) com validação de ponteiros ativos.
- Toda a estrutura interna das classes C++ (`CGameClient`, `CPlayer`, `CLevel`, `CGameUI`, `CMenuManager`), offsets de membros e todos os 14 menus CEGUI são **100% IDÊNTICOS** entre as versões GOG e Steam!
- O leitor lê diretamente da RAM via ponteiros em microssegundos com privilégio mínimo (`PROCESS_VM_READ`), com **risco zero de reinício ou crash**.
- **Ciclo de Vida e Reconexão Automática Robusta**:
  - O motor acopla o PID diretamente da janela ativa visível (`WindowLocator.window_pid`), ignorando processos zumbis em segundo plano.
  - Ao fechar o jogo, o leitor libera imediatamente o handle Win32 (`kernel32.CloseHandle`), evitando que o executável fique preso como zumbi.
  - Ao reabrir o jogo (Steam ou GOG), o módulo resolve a nova base dinâmica em tempo real via `EnumProcessModulesEx` com retry contínuo durante a fase de inicialização do executável, dispensando qualquer reinício manual do overlay.

---

## 2. Diagnóstico do Reinício do PC (Resolvido)
- **Evento do Windows**: Código de erro `0x139` (`KERNEL_SECURITY_CHECK_FAILURE`) / `0xEF`.
- **Causa**: O antigo `test_memory_reader.py` chamava `OpenDesktopW` e `SetThreadDesktop` com acessos crus para tentar achar janelas, o que no Windows 11 moderno corrompe referências internas de desktop no driver `win32k.sys`.
- **Solução implementada**: As chamadas a desktop foram removidas. A detecção de processo agora usa snapshot nativo do Windows (`CreateToolhelp32Snapshot`).

---

## 3. Cadeia de Ponteiros Globais Descoberta

A hierarquia real de objetos do motor do Torchlight é:

```
[ModuleBase + RVA]
  • GOG:   0x00400000 + 0x0081AD64 = 0x00C1AD64 (Fixo)
  • Steam: [Base Dinâmica ASLR] + 0x007F0E0C
     │
     ▼
  CGame
     │
     └── [+0x64] ──► CGameClient
                       │
                       ├── [+0x2C] ──► CPlayer (Objeto do Jogador)
                       ├── [+0x38] ──► CLevel  (Objeto do Mapa/Fase atual)
                       │
                       └── [+0x3C] ──► CGameUI
                                         │
                                         ├── [+0x0294] ──► Parent Sheet (CEGUI::Window*)
                                         ├── [+0x0298] ──► Loading Screen (CEGUI::Window*) [+0x80 != 0 quando ativa]
                                         ├── [+0x029C] ──► TipText (CEGUI::Window*)
                                         ├── [+0x0324] ──► CMenuManager
                                         │                   │
                                         │                   └── [+0x0D84] ──► Estado da Tela Inicial (Switch de Estados 0..5, 6: Em Jogo)
                                         │
                                         ├── [+0x02CC] ──► CInventoryMenu   [+0x30 == 1 quando aberto]
                                         ├── [+0x02D0] ──► CStatsMenu       [+0x44 == 1 quando aberto]
                                         ├── [+0x02D4] ──► CPetMenu         [+0x34 == 1 quando aberto]
                                         ├── [+0x02D8] ──► CMerchantMenu    [+0x30 == 1 quando aberto]
                                         ├── [+0x02DC] ──► CEnchantMenu     [+0x38 == 1 quando aberto; +0x90 = modo (0x19: Sockets, 0x15: Encantador)]
                                          ├── [+0x02E0] ──► CCombineMenu     [+0x54 == 1 quando aberto] (Transmutador / Duran the Transmuter)
                                         ├── [+0x02E4] ──► CStashMenu       [+0x30 == 1 quando aberto]
                                         ├── [+0x02E8] ──► COptionsMenu     [+0x18 == 1 quando aberto] (Menu de Pause em Jogo)
                                         ├── [+0x02EC] ──► CSettingsMenu    [+0x18 == 1 quando aberto] (Overlay de Settings)
                                         ├── [+0x02F0] ──► CDieMenu         [+0x18 == 1 quando aberto] (Tela de Morte/Ressurreição)
                                         ├── [+0x02F4] ──► CWaypointMenu    [+0x18 == 1 quando aberto] (Portal / Teleporte)
                                         ├── [+0x02F8] ──► CDialogMenu      [+0x18 == 1 quando aberto] (Diálogo de NPC)
                                         ├── [+0x02FC] ──► CQuestDialogMenu [+0x18 == 1 quando aberto] (Diálogo de Missão)
                                         ├── [+0x0304] ──► CModalMenu       [+0x18 == 1 quando aberto] (Modal de Confirmação/Sair)
                                         ├── [+0x030C] ──► CSkillMenu       [+0x1C == 1 quando aberto]
                                         ├── [+0x0310] ──► CJournalMenu     [+0x1C == 1 quando aberto] (Diário / Estatísticas gerais - Tecla J)
                                         ├── [+0x0314] ──► CQuestMenu       [+0xC8 == 1 quando aberto] (Missões / Quests ativas - Tecla Q)
                                         └── [+0x031C] ──► CFishingMenu     [+0x18 == 1 quando aberto] (Mini-game de Pesca)
```

---

## 4. Mapeamento das Telas Iniciais, Overlays e Carregamento

### A. Telas de Mudança de Cena (`CMenuManager + 0x0D84`)
- `0`: **Tela Inicial (Menu Principal)** com a fogueira e o personagem
- `1`: **Criar Personagem (New Character)** (escolha de classe)
- `2`: **Criar Personagem (Modo Hardcore)**
- `3`: **Carregar Personagem (Load Character / Continue)** (lista de saves)
- `4`: **Carregar Personagem (Detalhes)**
- `6`: **Em Jogo (Gameplay - Cidade / Dungeon)**

### B. Janelas de Overlay / Modais (Herdam de `CDialogMenu`, byte `+0x18`)
- **Settings**: Localizado em `CGameUI + 0x02EC`. Quando aberto sobre a tela inicial ou em jogo, o byte no offset **`+0x18`** se torna **`1`** (0 quando fechado).
- **Quit Game (Confirmação)**: Localizado em `CGameUI + 0x0304` (`CModalMenu`). Quando a caixa "Deseja sair do jogo?" abre, o byte **`+0x18`** se torna **`1`**.
- **Pause em jogo**: Localizado em `CGameUI + 0x02E8` (`COptionsMenu`). O byte **`+0x18`** se torna **`1`**.

### C. Tela de Carregamento (Loading Screen)
- **Layout**: O motor carrega `media/ui/loading.layout` (UTF-16) e armazena o ponteiro da janela CEGUI em **`CGameUI + 0x0298`**.
- **Mecanismo Interno**:
  - O jogo controla a visibilidade via a função `CGameUI::ShowLoading(bool bShow)` em `VA 0x00540CA0`.
  - Ao iniciar o carregamento (ao clicar em Continue, transicionar de mapa, portal ou escadas da dungeon): o jogo chama `addChildWindow` anexando `loadingWindow` à folha principal (`CGameUI + 0x0294`). Na estrutura da CEGUI, o membro `d_parent` no offset **`+0x80`** passa a apontar para a folha principal (`!= 0`).
  - Ao terminar o carregamento: o jogo chama `removeChildWindow`, desanexando a tela de loading e zerando `loadingWindow->d_parent` (`+0x80 == 0`).
  - Além disso, durante todo o carregamento do mapa, o ponteiro do jogador `CPlayer*` (`CGameClient + 0x2C`) permanece em **`0` (NULL)** até que o spawn seja concluído.
- **Critério de Detecção no Leitor**:
  `is_loading = (loading_parent != 0) or (main_state_id == 6 and p_player == 0)`

---

## 5. Como Usar o Monitor em Tempo Real
Para monitorar continuamente:
```powershell
python scripts/test_memory_reader.py
```
O script atualiza a cada 300ms no terminal com reconexão automática ao PID do jogo, detectando menus da tela inicial, modais/overlays, telas de carregamento e todos os menus de gameplay.

---

## 6. Mapeamento do Sistema de Diálogos e Telas de História

### A. Telas de História / Cinemáticas (`CCinematicMenu`)
- **Ponteiro em CGameUI**: `p_ui + 0x0300`
- **Flag de Aberto**: byte `+0x18 == 1`
- **Botão Skip / Continue**: ponteiro em `+0x68`
  - Coordenadas de clique: $X = \text{center\_x} + \text{height} \times 0.487$, $Y = \text{top} + \text{height} \times 0.948$

### B. Sistema de Diálogos de NPCs e Missões (`CQuestDialogMenu` / `CDialogMenu`)
- **Ponteiros em CGameUI**:
  - `p_ui + 0x02FC`: `CQuestDialogMenu` (Diálogos de história, missões e conversas de NPCs)
  - `p_ui + 0x02F8`: `CDialogMenu` (Diálogos simples genéricos de cidade)
- **Flag de Aberto**: byte `+0x18 == 1`
- **Ponteiros dos Botões na Estrutura C++**:
  - `+0x6C`: Botão **Ok** (`.?AVPushButton@CEGUI@@`)
  - `+0x70`: Botão **Accept** (`.?AVPushButton@CEGUI@@`)
  - `+0x74`: Botão **Decline** (`.?AVPushButton@CEGUI@@`)
- **Flag de Visibilidade dos Botões**: No objeto `CEGUI::Window`, o byte `+0x1A0` é `d_visible` (`1` = visível, `0` = oculto).
- **Enum Nativo de Tipo de Diálogo (`CQuestDialog + 0x5C`)**:
  - `p_ui + 0x02FC` (`CQuestDialogMenu`) -> `+0x98` -> `CQuestDialog*` (`p_qdlg`)
  - O campo **`p_qdlg + 0x5C`** armazena o Enum nativo do motor:
    - `1`: **Missão para Aceitar** (`INTRO` - botões Accept + Decline)
    - `2`: **Missão em Andamento** (`RETURN` - botão Ok de lembrete com recompensas na lateral)
    - `3`: **Missão Concluída** (`COMPLETE` - botão Ok com entrega de recompensas)
    - `4`: **Diálogo Simples** (`PASSIVE` / Conversa - botão Ok sem missões ativas)
- **Identificação dos Tipos de Diálogo**:
  - **1 - Diálogo Simples (Conversa de NPC)**:
    - Enum `p_qdlg + 0x5C == 4` (ou quest passiva / sem recompensas)
    - `ok_visible == 1`, `accept_visible == 0`, `decline_visible == 0`
    - Botão único **Ok** centralizado em $X = \text{center\_x}$, $Y = \text{top} + \text{height} \times 0.745$.
  - **2 - Missão para Aceitar (Validado com Trill-Bot 4000)**:
    - Enum `p_qdlg + 0x5C == 1`
    - `accept_visible == 1` e `decline_visible == 1`, `ok_visible == 0`
    - Botões duplos lado a lado em $Y = \text{top} + \text{height} \times 0.745$:
      - **Accept**: $X = \text{center\_x} - 99 \times (\text{height} / 768)$ (lado esquerdo)
      - **Decline**: $X = \text{center\_x} + 99 \times (\text{height} / 768)$ (lado direito)
    - Navegação via D-pad: D-pad Esquerda seleciona `Accept`, D-pad Direita seleciona `Decline`.
  - **3 - Missão em Andamento (Validado com Trill-Bot 4000)**:
    - Enum `p_qdlg + 0x5C == 2` (branch de retorno / lembrete)
    - `ok_visible == 1`, `accept_visible == 0`, `decline_visible == 0`
    - Botão único **Ok** centralizado em $X = \text{center\_x}$, $Y = \text{top} + \text{height} \times 0.745$.
  - **4 - Missão Concluída (Validado com Vasman / Mago)**:
    - Enum `p_qdlg + 0x5C == 3` (branch `COMPLETE` do arquivo `.DAT`)
    - Identificado quest `VASMAN_QUEST1` ("The Gleaming Ember", branch `OLDMANGREET`)
    - `ok_visible == 1`, `accept_visible == 0`, `decline_visible == 0`
    - Botão único **Ok** centralizado em $X = \text{center\_x}$, $Y = \text{top} + \text{height} \times 0.745$.
  - **5 - Missão Principal (Validado na Introdução e Syl)**:
    - Configurada no arquivo `.DAT` com `FORCEACCEPT: True` (Missões de história não podem ser recusadas pelo jogador)
    - `accept_visible == 1` e `decline_visible == 0` (o botão Decline permanece oculto/desativado)
    - Botão **Accept** ativo em $X = \text{center\_x} - 99 \times (\text{height} / 768)$, $Y = \text{top} + \text{height} \times 0.745$.

---

## 7. Mapeamento das Telas de Crafting (Transmutador, Sockets e Encantador)

As telas de crafting são placas de madeira suspensas por correntes no lado esquerdo da tela, e **não possuem a aba lateral de fechar** presente nos painéis normais (Pet e Atributos).

### A. Transmutador (Duran the Transmuter)
- **Estrutura C++**: `CCombineMenu` em `CGameUI + 0x02E0`
- **Flag de Aberto**: byte `+0x54 == 1`
- **Painel Lateral**: Painel Esquerdo (`PANEL_SIDE['T'] = 0`)
- **Slots de Itens (1024x768)**:
  - 4 slots retangulares (48x68 px) em grid 2x2:
    - Slot 1 (topo-esq): `(216, 266)`
    - Slot 2 (topo-dir): `(268, 266)`
    - Slot 3 (baixo-esq): `(216, 339)`
    - Slot 4 (baixo-dir): `(268, 339)`
- **Botões (1024x768)**:
  - `decline` (Fechar): `(240, 405)` (128x24 px)
  - `transmute` (Transmutar): `(240, 450)` (128x24 px)

### B. Sockets e Remoção de Gemas (Gron the Enchanter / Furl the Gem Inlayer)
- **Estrutura C++**: `CEnchantMenu` em `CGameUI + 0x02DC`
- **Flag de Aberto**: byte `+0x38 == 1`
- **Modo**: `+0x90 in (0x19, 0x1A, 0x1B)`
- **Painel Lateral**: Painel Esquerdo (`PANEL_SIDE['K'] = 0`)
- **Slot de Item (1024x768)**: Slot único quadrado (96x96 px) em `(240, 314)`
- **Botões (1024x768)**:
  - `decline` (Fechar): `(240, 402)` (128x24 px)
  - `recover` (Recuperar): `(240, 447)` (128x24 px)

### C. Encantador de Itens (Goren the Enchanter)
- **Estrutura C++**: `CEnchantMenu` em `CGameUI + 0x02DC`
- **Flag de Aberto**: byte `+0x38 == 1`
- **Modo**: `+0x90 == 0x15` (21) ou `0x16` (22)
- **Painel Lateral**: Painel Esquerdo (`PANEL_SIDE['E'] = 0`)
- **Slot de Item (1024x768)**: Slot único quadrado (96x96 px) em `(240, 314)`
- **Botões (1024x768)**:
  - `decline` (Fechar): `(240, 402)` (128x24 px)
  - `enchant` (Encantar): `(240, 447)` (128x24 px)

---

## 8. Mapeamento do Menu de Pause em Jogo (`COptionsMenu` / `Options`)

### A. Detecção na Memória
- **Estrutura C++**: `COptionsMenu` em `CGameUI + 0x02E8`
- **Flag de Aberto**: byte `+0x18 == 1`
- **Registro no Leitor**: `"Pause": (0x02E8, 0x18)` em `GAMEPLAY_MENUS`
- **Critério de Ativação**: `state_id == 6` (Em Jogo) e `"Pause"` presente em `open_menus`.

### B. Coordenadas Calibradas dos Marcadores (Base 1024x768)
Extraídas diretamente dos marcadores inseridos em `assets/images/menus/in-game paused.png`:
- **Default (Amarelo) - Retornar ao Jogo**:
  - `return_to_game`: `(599, 413)`
  - Posição inicial do cursor ao abrir o menu de pause
- **Possibilidades (Verde)**:
  - `settings` (Opções): `(599, 233)`
  - `exit_to_title` (Sair para o Menu Principal): `(599, 323)`

### C. Navegação via Controle
- **D-pad Cima / Baixo**: Alterna ciclicamente entre `settings` $\leftrightarrow$ `exit_to_title` $\leftrightarrow$ `return_to_game` com feedback tátil (rumble).
- **Botão B**: Atalho direto para focar e clicar em `return_to_game`, fechando o menu e retornando à jogatina.
- **Modo Calibração (Overlay)**: Exibe os 3 quadradinhos (17x17 px), amarelo no foco ativo e verde nas possibilidades.

---

## 9. Mapeamento da Tela de Carregar Personagem (`state_id == 3`)

### A. Detecção na Memória
- **Identificador de Estado**: `state_id == 3` (`CMenuManager + 0x0D84`)
- **Descrição**: `state_desc == "Carregar Personagem"`
- **Total de Saves Detectados**: `get_save_character_count()` (contagem de arquivos `.svt` em `APPDATA/runic games/torchlight/save`).

### B. Coordenadas Calibradas dos Marcadores (Base 1024x768)
Extraídas das imagens em `assets/images/sreensXcursor/load-char/`:
- **Lista de Personagens (Direita)**:
  - `slot_1` (Default / Amarelo): `(971, 227)`
  - `slot_2`: `(971, 300)`
  - `slot_3`: `(971, 372)`
  - `slot_4`: `(971, 445)`
  - `slot_5`: `(971, 517)`
  - `scroll_up` (Seta de Rolagem Superior): `(979, 155)`
  - `scroll_down` (Seta de Rolagem Inferior): `(971, 618)`
- **Barra Inferior (Centralizada)**:
  - `delete` (Botão Pequeno de Exclusão): `(558, 663)`
  - `back` (Voltar / Cancelar): `(300, 728)`
  - `play` (Jogar / Play): `(859, 728)`
- **Modal de Confirmação de Delete (Centro da Tela)**:
  - `delete_confirm` (Botão Delete): `(576, 362)`
  - `delete_cancel` (Botão Cancel - Padrão Seguro / Amarelo): `(576, 411)`

### C. Navegação e Regras de Fluxo
1. **Seleção de Personagem com Ação Rápida**:
   - Ao pressionar **A ou X** em qualquer slot de personagem (`slot_1`..`slot_5`), o motor executa o clique de seleção no personagem e move imediatamente o cursor para o botão **Play** `(859, 728)`.
   - Um segundo toque em **A ou X** aciona o Play para iniciar a partida imediatamente.
2. **Navegação com D-pad**:
   - **D-pad Esquerda**: Sai da lista de personagens direto para o botão Play na barra inferior. Se já estiver na barra inferior, caminha `Play` $\rightarrow$ `Delete` $\rightarrow$ `Voltar`.
   - **D-pad Direita**: Caminha `Voltar` $\rightarrow$ `Delete` $\rightarrow$ `Play` $\rightarrow$ retorna ao último slot de personagem visitado.
   - **D-pad Cima / Baixo (Rolagem Contínua Automática)**:
     - Percorre os slots de `slot_1` até `slot_5`.
     - Ao pressionar **D-pad Baixo** no `slot_5`, se houver mais personagens abaixo na lista (`save_count > 5`), o motor clica automaticamente na seta inferior `(971, 618)` para rolar 1 personagem e mantém o cursor no `slot_5`.
     - Ao pressionar **D-pad Cima** no `slot_1`, se a lista tiver sido rolada, o motor clica automaticamente na seta superior `(979, 155)` para rolar 1 personagem para cima e mantém o cursor no `slot_1`.
     - Permite percorrer todos os personagens da conta continuamente com o direcional digital sem precisar desviar para os botões de scroll.
3. **Fluxo do Botão Delete (com Debounce e Auto-Sync)**:
   - Clicar em `delete` (pequeno) aciona o clique do mouse e aguarda **200 ms** (debounce com cursor retido na posição inferior) para o modal abrir completamente no jogo antes de mover o cursor para `delete_cancel` (amarelo de segurança), prevenindo que a soltura do clique ou o toque no controle feche o popup instantaneamente.
   - Uma janela de proteção de **250 ms** ignora entradas imediatas ao abrir ou fechar o modal.
   - Ao confirmar a exclusão (`delete_confirm`) ou cancelar (`delete_cancel` / botão B), o modal fecha no jogo com debounce de 200 ms e o cursor **retorna exatamente para o botão delete pequeno** `(558, 663)`.
   - O estado do modal é gerenciado pelo ciclo de vida explícito de abertura e confirmação/cancelamento, mantendo o cursor focado no popup até o jogador escolher uma das opções ou apertar B para voltar.
4. **Modo Calibração (Overlay)**:
   - Exibe os marcadores de 34x18 px: amarelo no foco atual e verde nas possibilidades disponíveis.

---

## 10. Mapeamento da Tela de Configurações (Settings)

### A. Detecção na Memória
- **Estrutura C++**: `CSettingsMenu` em `CGameUI + 0x02EC`
- **Flag de Aberto**: byte `+0x18 == 1`
- **Valores de Áudio**: Leitura de `SOUND VOLUME`, `MUSIC VOLUME`, `SOUND MUTE`, `MUSIC MUTE` diretamente de `local_settings.txt` e `SETTINGS.TXT`.
- **Identificação**: `"Configurações"` em `open_menus` (tanto no menu inicial quanto dentro do jogo via Menu de Pause).

### B. Coordenadas e Marcadores de Calibração (Base 1024x768)
Extraídos e normalizados a partir das imagens em `assets/images/sreensXcursor/settings/`:
- **Cores Padronizadas**:
  - `verde`: `#09B200` (pontos navegáveis comuns)
  - `amarelo`: `#E6C12A` (ponto inicial padrão do cursor e 1ª opção de dropdowns)
  - `rosa`: `#B2007C` (botões de abertura de dropdown)
  - `roxo`: `#5600B2` (marcador dos sliders de som e música baseado no volume salvo)
  - `ciano`: `#00C7D5` (linha horizontal de limites mín/máx dos sliders de volume: $X \in [228, 447]$)

- **Tela Principal**:
  - `row1_col1` (Default / Amarelo): `(238, 132)`
  - `row1_col2` (Verde): `(437, 132)`
  - `row1_col3` (Verde): `(636, 132)`
  - `row2_col1` (Verde): `(238, 184)`
  - `row2_col2` (Verde): `(437, 184)`
  - `row2_col3` (Verde): `(636, 184)`
  - `resolution` (Dropdown Rosa): `(398, 247)`
  - `shadows` (Dropdown Rosa): `(800, 247)`
  - `music_slider` (Music Volume / Slider Roxo Superior): $X = 228 + \text{volume} \times 219$, $Y = 344$
  - `music_mute` (Mudo Música / Verde): `(486, 346)`
  - `particle_detail` (Dropdown Rosa): `(800, 346)`
  - `row5_col3` (Opção Verde): `(636, 401)`
  - `sound_slider` (Sound Volume / Slider Roxo Inferior): $X = 228 + \text{volume} \times 219$, $Y = 445$
  - `sound_mute` (Mudo Som / Verde): `(486, 448)`
  - `row6_col3` (Opção Verde): `(636, 444)`
  - `row7_col1` (Opção Verde): `(238, 488)`
  - `row7_col3` (Opção Verde): `(636, 488)`
  - `cancel` (Cancelar / Verde): `(465, 552)`
  - `apply` (Salvar/OK / Verde): `(657, 552)`

- **Menus Dropdown (Abertos)**:
  - **Shadows**:
    - Rosa (Opener): `(800, 247)`
    - Amarelo (Opção 0): `(789, 293)`
    - Verdes (Opções 1 a 5): `(789, 310)`, `(789, 329)`, `(789, 346)`, `(789, 363)`, `(789, 380)`
  - **Resolution**:
    - Rosa (Opener): `(398, 247)`
    - Amarelo (Opção 0): `(385, 296)`
    - Verdes (Opções 1 a 17): de $Y = 313$ até $Y = 586$ em passos de ~17px ($X = 385$)
  - **Particle Detail**:
    - Rosa (Opener): `(800, 346)`
    - Amarelo (Opção 0): `(785, 396)`
    - Verdes (Opções 1 a 2): `(785, 413)`, `(785, 431)`

### C. Comportamentos Especiais do Controle
1. **Comportamento de Slider de Volume (OBS 1)**:
   - Ao focar no marcador roxo (`sound_slider` ou `music_slider`), pressionar **A ou X** engaja o modo de arrasto (`mouse_button("left", True)` mantido retido).
   - Com o arrasto ativo, **D-pad Esquerda / Direita** (ou analógico esquerdo) desloca o cursor suavemente em passos de 5% ao longo do segmento ciano ($X \in [228, 447]$), ajustando o volume do jogo.
   - Pressionar **B ou O** libera o clique esquerdo (`mouse_button("left", False)`), finaliza o arrasto e restaura a navegação livre pelo D-pad.
2. **Comportamento de Menus Dropdown (OBS 2)**:
   - Ao pressionar **A ou X** sobre um botão rosa de dropdown (`resolution`, `shadows` ou `particle_detail`), o motor clica para abrir o menu suspenso e move instantaneamente o cursor para o ponto amarelo (opção inicial do dropdown).
   - O D-pad Cima / Baixo passa a navegar exclusivamente a lista de opções do dropdown.
   - Ao pressionar **A ou X** em uma das opções, o motor clica na opção selecionada, fecha o dropdown e retorna o cursor para o botão rosa de origem.
   - Ao pressionar **B ou O** para cancelar o dropdown, o motor posiciona o cursor de volta no botão rosa e realiza o clique para fechar o dropdown no jogo.
3. **Botão B na Tela Principal**:
   - Pressionar **B ou O** na tela principal de configurações foca e clica automaticamente no botão Cancelar `(465, 552)`, fechando as configurações.
4. **Supressão Total de Cliques Residuais e Bloqueio de Overworld/Combat**:
   - Durante toda a permanência na tela de configurações, o pipeline de `_process_active` retorna imediatamente após o handler `_handle_settings_navigation`. Isso impede que atalhos de overworld (como ESC do B, combos de gatilho LT/RT) e o `_move_pointer` livre do analógico interfiram no menu.
   - Os cliques de mouse padrão (`_set_mouse`) permanecem suprimidos (`suppress_mouse = True`) de ponta a ponta na tela de configurações, prevenindo que o aperto de X vaze um clique com botão direito que cancelaria o arrasto no CEGUI/Torchlight.
   - O arrasto pelo analógico conta com limitação de taxa (rate-limiting de 80ms) para ajuste suave e controlado do volume.

---

## 11. Interface de Pescaria e Modal de Confirmação (Resultado de Pesca / Mensagens)

### A. Interface de Pesca (Minigame do Anzol)
- **Detecção via RAM**: Menu `"Pesca"` ativo em `CGameUI + 0x031C` (byte `+0x18 == 1`).
- **Coordenada do Anzol (1024x768)**:
  - Centro do botão octogonal de anzol com ondas de água: `(512, 498)`.
- **Comportamento do Motor**:
  - O cursor vai automaticamente para o anzol `(512, 498)` e permanece fixo nele como **única opção**, impedindo que o cursor se perca na tela durante a pescaria.
  - Pressionar **A ou X** no controle dispara o clique esquerdo (`mouse_button("left", True)` seguido de `False`), fisgando o peixe.
  - Abertura da **roda de habilidades (LB)** é **estritamente bloqueada** durante a pescaria.
  - Comandos de combate, atalhos de overworld e cliques residuais são suprimidos.

### B. Modal de Confirmação (Resultado da Pesca / Mensagens com botão Ok)
- **Detecção via RAM**: `CModalMenu` ativo em `CGameUI + 0x0304` (`is_modal_open == True` / menu `"Confirmação Sair"`).
- **Coordenada do Botão Ok (1024x768)**:
  - Centro do botão Ok vermelho no pergaminho de resultado ("You caught a Bat Fish!" ou "You caught nothing!"): `(509, 467)`.
- **Comportamento do Motor**:
  - O cursor posiciona-se automaticamente no centro do botão **Ok** `(509, 467)`.
  - Pressionar **A, X ou B** aciona o clique no botão Ok para confirmar e fechar o diálogo.
  - Abertura da **roda de habilidades (LB)** é **estritamente bloqueada** no modal de confirmação.
  - Comandos de combate e movimento de cursor livre são suprimidos.



