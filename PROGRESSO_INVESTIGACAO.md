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
                                         ├── [+0x0324] ──► CMenuManager
                                         │                   │
                                         │                   └── [+0x0D84] ──► Estado da Tela Inicial (Switch de Estados 0..5, 6: Em Jogo)
                                         │
                                         ├── [+0x02CC] ──► CInventoryMenu   [+0x30 == 1 quando aberto]
                                         ├── [+0x02D0] ──► CStatsMenu       [+0x44 == 1 quando aberto]
                                         ├── [+0x02D4] ──► CPetMenu         [+0x34 == 1 quando aberto]
                                         ├── [+0x02D8] ──► CMerchantMenu    [+0x30 == 1 quando aberto]
                                         ├── [+0x02DC] ──► CEnchantMenu     [+0x30 == 1 quando aberto]
                                         ├── [+0x02E4] ──► CStashMenu       [+0x30 == 1 quando aberto]
                                         ├── [+0x02E8] ──► COptionsMenu     [+0x18 == 1 quando aberto] (Menu de Pause em Jogo)
                                         ├── [+0x02EC] ──► CSettingsMenu    [+0x18 == 1 quando aberto] (Overlay de Settings)
                                         ├── [+0x02F0] ──► CDieMenu         (Tela de Morte/Ressurreição)
                                         ├── [+0x02F4] ──► CWaypointMenu    (Portal/Teleporte)
                                         ├── [+0x02F8] ──► CDialogMenu      [+0x18 == 1 quando aberto] (Diálogo de NPC)
                                         ├── [+0x02FC] ──► CQuestDialogMenu (Diálogo de Missão)
                                         ├── [+0x0304] ──► CModalMenu       [+0x18 == 1 quando aberto] (Modal de Confirmação/Sair)
                                         ├── [+0x030C] ──► CSkillMenu       [+0x1C == 1 quando aberto]
                                         ├── [+0x0310] ──► CJournalMenu     (Diário de Quests)
                                         └── [+0x031C] ──► CFishingMenu     (Mini-game de Pesca)
```

---

## 4. Mapeamento das Telas Iniciais e Overlays

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

---

## 5. Como Usar o Monitor em Tempo Real
Para monitorar continuamente:
```powershell
python scripts/test_memory_reader.py
```
O script atualiza a cada 300ms no terminal com reconexão automática ao PID do jogo.
