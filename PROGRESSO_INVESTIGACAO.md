# Progresso da Investigação: Leitura e Inspeção de Memória do Torchlight 1

Este documento registra o avanço técnico da engenharia reversa do executável `Torchlight.exe`, a identificação e correção da causa do reinício do computador, a cadeia completa de ponteiros e offsets estáticos mapeados e o detector de estado da tela principal e overlays.

---

## 1. Resumo Executivo
- O executável do Torchlight 1 (versão GOG/Steam) é **32-bit (x86)** e **NÃO possui ASLR** (Dynamic Base). Todos os endereços de código e dados globais são **estáticos e fixos na memória RAM** a cada execução.
- Eliminamos totalmente o método de varredura ampla de RAM (`VirtualQueryEx`), que causava instabilidade, e mapeamos a **cadeia exata de ponteiros estáticos**.
- O leitor lê diretamente da RAM via ponteiros fixos em microssegundos com privilégio mínimo (`PROCESS_VM_READ`), com **risco zero de reinício ou crash**.
- Implementado modo de monitoramento contínuo em tempo real (loop de atualização a cada 300ms) com **reconexão automática de processo** (caso o jogo seja fechado e reaberto).

---

## 2. Diagnóstico do Reinício do PC (Resolvido)
- **Evento do Windows**: Código de erro `0x139` (`KERNEL_SECURITY_CHECK_FAILURE`) / `0xEF`.
- **Causa**: O antigo `test_memory_reader.py` chamava `OpenDesktopW` e `SetThreadDesktop` com acessos crus para tentar achar janelas, o que no Windows 11 moderno corrompe referências internas de desktop no driver `win32k.sys`.
- **Solução implementada**: As chamadas a desktop foram removidas. A detecção de processo agora usa snapshot nativo do Windows (`CreateToolhelp32Snapshot`).

---

## 3. Cadeia de Ponteiros Globais Descoberta

A hierarquia real de objetos do motor do Torchlight é:

```
[0x00C1AD64] (Ponteiro Estático Global em .data)
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
                                         ├── [+0x02DC] ──► CEnchantMenu     [+0x38 == 1 quando aberto]
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




