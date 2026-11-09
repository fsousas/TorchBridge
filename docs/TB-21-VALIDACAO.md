# TB-21 — implementação e validação

Data: 2026-11-08. Branch: `feature/TB-21`. Base: `8059fea`.

## Escopo entregue

Backend Linux nativo para Omarchy/Hyprland: entrada Wayland, overlay layer-shell,
leitura PE32 sob Proton, instância única, bandeja, edição de perfil, calibração,
lançamento do jogo como descendente, diagnóstico e distribuição. O motor e os
handlers existentes são compartilhados. `win32.py` e `native/fullscreen/` não
foram alterados; scripts `.bat` continuam sendo as entradas do Windows.

O aplicativo Linux não depende de Wine. O jogo alvo usa a edição Windows x86 via
Proton/WineX11. A edição ELF antiga, outros compositores e gamescope não foram
portados. Detalhes e matriz por funcionalidade: [LINUX.md](LINUX.md).

## Testes executados

| Verificação | Resultado |
| --- | --- |
| Referência anterior às alterações | 500 testes existentes passaram |
| Suíte final `python scripts/run_tests.py` | **526 testes passaram** |
| Overlay com `QT_SCALE_FACTOR=1.5` | 27 testes passaram |
| Ciclo de vida com `QT_SCALE_FACTOR=1.5` | 30 testes passaram |
| Novas fronteiras Linux e CLI com escala 1.5 | 22 testes passaram |
| Build C Linux | compilado com `-Wall -Wextra -Werror` |
| Smoke Wayland real | passou: cursor absoluto, Shift/liberação, texto, clique interceptado, foco, esconder/reabrir e cursor do teclado |
| Destrutor do dispositivo virtual | Alt mantido foi liberado ao fechar o transporte |
| Leitura de memória de processo filho | fixture real via `/proc/PID/mem`, somente leitura; desconexão após saída |
| Arquivo `.desktop` | `desktop-file-validate` sem erros |
| Scripts shell | sintaxe validada com `bash -n` |
| Pacote PyInstaller Linux | build concluído; `--diagnose` encontrou transporte e assets; GUI iniciou e encerrou com SIGTERM/código 0 fora do checkout |
| Wheel e sdist | build concluído; wheel instalado em virtualenv isolada e sdist recompilado/instalado fora do checkout |
| Assets do wheel | **225 PNGs** decodificados por Qt; cursor `.cur` presente |
| Sintaxe Python e whitespace | `compileall` e `git diff --check` sem erros |

O runner sempre força Qt offscreen. As APIs de entrada do motor são substituídas
por fakes na suíte; ela não digita nem clica no desktop. Os avisos deliberados de
liberação de modificador pertencem aos testes que simulam falhas. Os avisos do
plugin offscreen sobre `raise()` são esperados nesse backend de teste.

O smoke real é separado e explícito:

```bash
.venv/bin/python scripts/smoke_linux.py
```

Ele dá foco apenas à janela fixture e revalida foco/PID antes de enviar entrada.
Exercitou texto `baA!zé`, confirmando caixa, símbolo e Unicode, além da região
interativa do overlay. Fecha os recursos e restaura cursor/foco ao terminar.

## Integração com o jogo real

Ambiente: Hyprland 0.56.2, Python 3.13.18, pygame-ce 2.5.8/SDL 2.32.10,
Torchlight Steam PE32, GE-Proton11-12 e SteamLinuxRuntime_4. Yama permaneceu em 1.
Monitor principal 1920×1080/125%; segundo monitor 1440×900/100% com origem Y -900.

Foi executado um harness local do aplicativo completo, com um controle virtual
SDL em modo RAW e perfil temporário. O comando de Proton foi passado por
`--launch`, mantendo o aplicativo como ancestral do jogo. Não foram enviados
comandos de criar/carregar personagem, nem de confirmar saída pelo menu.

Observado:

```text
STATE Aguardando jogo... controller True focus False
STATE Inicializando CGame... controller True focus True
STATE Carregando... controller True focus True
STATE Tela Inicial controller True focus True
FULL APP Overlay: Wayland (janela e fullscreen)
rect Rect(left=0, top=0, width=1536, height=864) title focus continue
REAL SDL -> ENGINE -> TITLE NAVIGATION continue -> quit_game
FULL APP E2E OK
```

O processo foi reconhecido pelo executável, o PE relocou para `0x7B240000`, o
RVA Steam foi resolvido e a pasta de dados do prefixo correto foi encontrada.
A camada `torchbridge-overlay` foi consultada no IPC do compositor: suas dimensões
coincidiam com o cliente fullscreen. O movimento do direcional SDL alterou o foco
de navegação da tela inicial pelo motor real. Ao terminar o teste, o aplicativo
limpou seus recursos e o processo de jogo criado para essa verificação foi fechado.

Essa evidência valida inicialização, foco, overlay fullscreen, conexão de memória
e a entrada do controle no motor. Não representa uma campanha de gameplay ou
validação de todos os itens visuais de cada menu.

## Homologação manual ainda necessária

| Rodada | Estado |
| --- | --- |
| Windows 10/11, Steam/GOG, instalação e D3D9 fullscreen | não executada neste host Linux; regressões isoladas passaram; CI Windows configurado |
| DualSense físico USB e Bluetooth | pendente |
| Xbox físico USB/receptor/Bluetooth | pendente |
| Genérico físico, calibração e rumble | pendente |
| GOG via WineX11 no Omarchy | pendente |
| Gameplay completo: movimento, combate, menus, pet, lojas e crafting | pendente de sessão real; handlers cobertos pela suíte compartilhada |
| Troca de monitor, redimensionamento e Alt+Tab durante combos em jogo | transporte/unidades cobertos; rodada real de gameplay pendente |

Roteiro da rodada:

1. Instalar pelo guia Linux e configurar `--launch %command%` no Steam.
2. Conectar/desconectar cada controle, selecionar o dispositivo e testar a
   persistência da seleção e a calibração RAW quando necessária.
3. Entrar num personagem de teste: andar, mirar, atacar, usar habilidades 1–0,
   combos LT, roda e submenus do pet. Conferir rumble.
4. Percorrer inventário/pet/baú/vendedor, atributos/habilidades/spells, quests,
   journal, diálogos, encantador, sockets, transmutador, pesca, portais e respawn.
5. Criar nomes de personagem/pet no teclado virtual; alternar mouse/controle,
   caps, espaço, apagar e confirmar, sem clique atravessando o teclado.
6. Abrir pause/configurações/áudio e configurar atalhos na HUD/popup CEGUI.
7. Alternar janela/fullscreen, monitor e escala; perder foco segurando ataque ou
   modificadores; pausar/desconectar/sair e verificar ausência de entrada retida.
8. Repetir a rodada Windows, incluindo o roteiro [FULLSCREEN.md](FULLSCREEN.md).

O workflow continua cobrindo Windows e Ubuntu com Python 3.11/3.13 e build/testes
do módulo D3D9 no Windows. O build Linux agora compila o transporte Wayland e
gera wheel; não houve execução remota do workflow nesta sessão.

Não foram alterados executável do jogo, DLLs, saves, configuração do compositor
ou política global de leitura de processos para viabilizar a implementação.

## Correção da escrita dos nomes no teclado virtual

O teclado aparecia e suas teclas respondiam, mas a sequência de ativação do
campo falhava no Proton: o clique podia ocorrer antes de o Torchlight/OIS
processar o movimento do cursor até a caixa. O jogo permanecia em primeiro plano,
mas o edit box não ganhava foco. O envio de texto retornava sucesso sem alterar
o nome. Testar somente um QLineEdit não reproduzia essa sincronização do jogo.

A abertura agora chama um hook de sincronização implementado **apenas no backend
Linux**. Ele aguarda 80 ms entre mover o cursor ao campo e clicar, revalidando a
permissão de entrada a cada intervalo de até 5 ms. Perda de foco, pausa,
desconexão ou parada cancela a operação antes do clique. A espera não é aplicada
ao movimento analógico normal, nem à digitação de cada letra.

O backend Win32 não implementa o hook: conserva a sequência anterior de
mover/pressionar/soltar/mover, sem espera. Os arquivos de desenho, posições,
assets e animações do teclado não foram alterados para essa correção.

Validação adicional em jogo real, com o mesmo overlay visível:

- Oito aberturas, alternando nome de personagem/pet e backend direto/InputSession:
  todas escreveram a letra esperada na caixa selecionada.
- Em cada abertura também foram exercitados caps/maiúscula e backspace, com o
  comprimento do texto conferido na memória somente para leitura.
- Personagem: comprimento 0 → 1 → 2 → 3 → 4; pet: 4 → 5 → 6 → 7 → 8.
- Nenhum personagem foi criado/carregado e nenhum save foi escrito pelo teste.
- Quatro novas regressões cobrem a ordem da ativação Linux, cancelamento durante
  a espera, revalidação de foco e preservação da sequência Win32 sem espera.
- Suíte completa após a correção: 526 testes passaram.
