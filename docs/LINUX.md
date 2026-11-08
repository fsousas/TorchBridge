# TorchBridge no Omarchy Linux — TB-21

O TorchBridge roda como aplicação **Linux nativa**, com Python, SDL/pygame-ce,
Qt/PySide6 e um transporte C Wayland. Não execute o TorchBridge pelo Wine.
O jogo suportado é o **Torchlight 1 Windows x86 (Steam/GOG), via Proton/WineX11**:
assim, os mesmos executáveis, offsets de memória e regras de navegação do Windows
continuam em uso. A edição ELF antiga do Torchlight para Linux possui outro layout
de memória e não é suportada por este backend. A compatibilidade aqui documentada
não se estende automaticamente a ela.

Alvo: Omarchy com Hyprland, Wayland, Xwayland e sessão gráfica do próprio usuário.
A implementação usa `wlr-layer-shell`, `wlr-virtual-pointer`, `virtual-keyboard`,
`wl_shm`, IPC do Hyprland e `/proc`. Não requer root, daemon de entrada, grupo
`input`, acesso a `/dev/uinput`, regras do compositor ou alteração de `ptrace_scope`.
Outros compositores, Wine Wayland, gamescope e sessões X11 não fazem parte do alvo
validado. Jogos dentro de outro compositor precisam de integração específica.

## Instalar a partir dos fontes

Use uma pasta permanente, inclusive para a opção de inicialização do Steam.

```bash
cd /caminho/TorchBridge
omarchy pkg add base-devel pkgconf python wayland libxkbcommon xorg-xwayland libx11 libxtst
./INSTALAR.sh
```

O script cria/usa `.venv`, instala o projeto e suas dependências, compila o
transporte Wayland e cria um launcher no menu de aplicativos. A versão Python
mínima é 3.11; a implementação foi exercitada localmente com Python 3.13.
`uv`, se disponível, é usado para a instalação; caso contrário, usa-se pip.
Os headers de Wayland/xkbcommon e `wayland-scanner` são necessários para compilar.
Os XMLs dos protocolos estão versionados; o build não precisa baixá-los.

A instalação cria somente a virtualenv e dois arquivos na pasta de dados do
usuário: o `.desktop` e o ícone. Não altera a configuração do Hyprland.

Para abrir sem lançar o jogo:

```bash
./INICIAR_TORCHBRIDGE.sh
```

O ícone TB na bandeja oferece ativar/pausar, calibração visual, abrir/recarregar
perfil, seleção persistente do controle e saída. O menu de instalação de DLL D3D9
é exclusivo do Windows; no Linux, a camada Wayland já cobre fullscreen.

## Steam e leitura de memória

O Linux normalmente usa `kernel.yama.ptrace_scope=1`. Isso permite ler processos
filhos, mas pode impedir que um programa leia um jogo iniciado separadamente.
O modo `--launch` mantém o TorchBridge como ancestral do Proton e do jogo. Ele
usa o mesmo comando que o Steam já forneceria, sem shell intermediário construído
pelo aplicativo e sem mudar privilégios ou a política global do sistema.

1. No Steam, force a ferramenta de compatibilidade Proton para o Torchlight,
   utilizando a instalação Windows (`Torchlight.exe`).
2. Desative o Steam Input para o jogo, evitando dois mapeadores simultâneos.
3. Feche instâncias do TorchBridge e do jogo que já estiverem abertas.
4. Nas opções de inicialização do Torchlight, coloque, com o caminho real:

```text
"/caminho/TorchBridge/INICIAR_TORCHBRIDGE.sh" --launch %command%
```

5. Inicie o jogo normalmente pelo Steam. O TorchBridge abre junto.

Para uma distribuição portátil, use:

```text
"/caminho/TorchBridge/TorchBridge" --launch %command%
```

Não acrescente `steam -applaunch 41500` depois de `--launch`: o cliente Steam
já aberto cria o jogo fora dessa árvore de processos. O `%command%` original
preserva a versão do Proton, o runtime e os argumentos escolhidos no Steam,
inclusive caminhos com espaços e o delimitador `--` interno.

O TorchBridge preserva o ambiente recebido para o comando filho e nunca instala
a DLL D3D9 Windows no prefixo. DXVK e arquivos do jogo permanecem intactos.
Não use `PROTON_ENABLE_WAYLAND=1`: este backend reconhece janelas WineX11/Xwayland.

Se já houver uma instância do TorchBridge, `--launch` avisa e retorna erro,
sem abrir o jogo com uma relação de processos que impediria a leitura.
Fechar o TorchBridge libera todas as entradas; não encerra à força o jogo.
O aplicativo permanece na bandeja quando o jogo é fechado, para permitir reinício.

Em sistemas que já permitem leitura entre processos do usuário, iniciar o jogo
e o aplicativo separadamente continua funcionando. Se a política impedir a
leitura, a bandeja/log mostra o motivo e o motor suspende novas entradas até a
conexão ser restabelecida. Políticas mais restritas que o padrão, processos não
dumpáveis e namespaces isolados podem impedir a leitura mesmo com `--launch`.
Nenhuma dessas políticas é alterada automaticamente.

## GOG e Wine

Use a edição Windows x86 e um prefixo Wine existente e funcional. Execute o
comando real do jogo como filho do TorchBridge:

```bash
WINEPREFIX="/caminho/prefixo" ./INICIAR_TORCHBRIDGE.sh --launch wine "/caminho/Torchlight.exe"
```

O Wine precisa oferecer a janela por Xwayland. A lógica de detecção do layout
GOG é compartilhada com o Windows; a sessão real exercitada nesta máquina foi
Steam + GE-Proton. GOG/Wine ainda precisa de homologação em jogo.

## Configuração e dados

| Item | Windows | Omarchy Linux |
| --- | --- | --- |
| Perfil padrão | `%APPDATA%\TorchBridge\perfil.json` | `$XDG_CONFIG_HOME/TorchBridge/perfil.json`, padrão `~/.config/TorchBridge/perfil.json` |
| Log | `%APPDATA%\TorchBridge\torchbridge.log` | mesma pasta do perfil padrão, `torchbridge.log` |
| Perfil alternativo | `--perfil CAMINHO` | `--perfil CAMINHO` |
| Dados do jogo | `%APPDATA%\runic games\torchlight` | prefixo do processo selecionado, `drive_c/users/<usuário>/AppData/Roaming/runic games/torchlight` |

O formato do perfil é o mesmo. Pode-se copiar `perfil.json` entre Windows e
Linux. GUIDs/mapeamentos RAW do SDL podem variar entre sistemas e conexões; se o
controle selecionado não aparecer, escolha-o na bandeja e refaça a calibração
RAW, quando necessária. Um dispositivo diferente não assume a seleção salva.

Os volumes e a quantidade de personagens são lidos do prefixo do jogo
selecionado, por `WINEPREFIX` ou `STEAM_COMPAT_DATA_PATH`. Pastas com a capitalização
Windows (`Runic Games`, `Torchlight`) também são reconhecidas. Para instalações
atípicas, `TORCHBRIDGE_GAME_DATA=/caminho/runic\ games/torchlight` define o diretório
que contém `save/` e `local_settings.txt`. Não há escrita nos saves pelo leitor.

Ao abrir o teclado virtual, o backend Linux sincroniza o movimento até o campo
com o jogo por 80 ms antes do clique de foco. Essa espera, cancelável na perda de
foco/pausa/desconexão, ocorre somente na ativação do campo; não reduz a velocidade
do cursor analógico nem adiciona atraso a cada letra. O Windows mantém sua
sequência original. Diagnóstico e regressão: [TB-21-VALIDACAO.md](TB-21-VALIDACAO.md).

A calibração do controle genérico funciona no terminal:

```bash
./CALIBRAR_CONTROLE_GENERICO.sh
```

A calibração da âncora do herói, sensibilidade, bindings, recarga automática e
configuração de atalhos usam exatamente o mesmo motor descrito no README.

## Overlay, foco e escala

O Qt desenha os mesmos assets e animações do Windows numa imagem ARGB
premultiplicada. O transporte apresenta essa imagem numa superfície layer-shell
na camada `overlay`, acima do fullscreen, vinculada ao monitor do jogo. Não há
proxy D3D9, injeção no jogo ou processo Quickshell auxiliar.

O motor, o cursor e os eventos do teclado virtual usam coordenadas lógicas do
compositor. O raster usa `ceil(escala do monitor)` e `wl_surface.set_buffer_scale`,
para manter definição em escalas fracionárias sem duplicar posições. Origens
negativas, monitores com escalas diferentes e rotação são considerados. A camada
é recriada quando o jogo muda de saída ou o monitor desaparece.

A região de entrada é vazia, exceto no retângulo do teclado virtual enquanto
aberto. Essa região recebe cliques/hover e os entrega ao mesmo motor de teclado;
não recebe foco de teclado. O cursor `pointer.cur` também é apresentado por uma
superfície de cursor Wayland sobre o teclado, sem depender do cursor oculto do jogo.
A perda de foco, pausa, desconexão do controle ou
saída cancela sequências e libera botões/modificadores. A UI revalida o foco antes
de apresentar o overlay, independentemente do snapshot do motor.

As teclas do teclado virtual fornecido são ASCII US QWERTY e usam códigos evdev
via teclado virtual Wayland, com Shift explícito para maiúsculas e símbolos.
A API de texto também aceita Unicode: além desse teclado, o fallback Xwayland
empresta temporariamente um keycode sem uso, envia o caractere via XTEST e restaura
o mapa original. O foco é revalidado após a espera de atualização do mapa. Não
há mudança permanente do layout do usuário.

## Diagnóstico e testes

Verificação sem enviar teclas, cliques ou mover o cursor:

```bash
./INICIAR_TORCHBRIDGE.sh --diagnose
```

O JSON informa a sessão, monitores, protocolos, política Yama e jogo encontrado.
O resultado `ready=true` sem jogo significa que os pré-requisitos estão presentes,
não que cada tela/controle foi homologado. A permissão de memória é relativa ao
processo que executa o diagnóstico: um diagnóstico separado pode ser impedido
pelo Yama mesmo quando a instância que lançou o jogo consegue lê-lo. Consulte o
log dessa instância para avaliar sua conexão.

Testes isolados (nenhuma entrada no desktop):

```bash
.venv/bin/python scripts/run_tests.py
QT_SCALE_FACTOR=1.5 .venv/bin/python scripts/run_tests.py --pattern 'test_overlay*.py'
```

Integração real e opt-in do transporte, numa janela de teste própria:

```bash
.venv/bin/python scripts/smoke_linux.py
```

Esse teste abre uma janela Xwayland, dá foco a ela, move o cursor, digita, confere
modificadores e cliques no overlay e restaura o foco/cursor anteriores. Ele cancela
novas entradas se a janela de teste perder foco. Não abre o jogo nem usa saves.

Os scripts de inspeção PE aceitam o caminho como argumento:

```bash
.venv/bin/python scripts/inspect_torchlight.py "/caminho/Torchlight.exe"
.venv/bin/python scripts/analyze_rtti_and_vtables.py "/caminho/Torchlight.exe"
.venv/bin/python scripts/test_memory_reader.py --once
```

Monitores/sondas de hover em `scripts/` usam agora o backend compartilhado e
resolvem a base real do processo, incluindo ASLR. As mesmas permissões de leitura
se aplicam a essas ferramentas. Os experimentos em `scratch/` são registros de
engenharia reversa do Windows e não são entradas de produção do aplicativo.

## Distribuir e desinstalar

```bash
./GERAR_LINUX.sh
```

Distribua **toda a pasta** `dist/TorchBridge`, gerada no Linux. Não é um `.exe`
Windows nem exige a virtualenv no destino. O binário depende do Linux/ABI e do
compositor; gere a distribuição numa base compatível com as máquinas de destino.
Windows continua sendo empacotado separadamente com `GERAR_EXE.bat`.
O `.spec` compartilhado inclui a biblioteca Wayland somente no build Linux.

Para instalar um launcher para uma pasta portátil:

```bash
python scripts/install_linux_desktop.py --bundle /caminho/dist/TorchBridge
```

Também é possível distribuir um wheel compilado com `python -m pip wheel
--no-deps . -w dist`. Ele inclui a biblioteca nativa e os assets, resolvidos em
`share/torchbridge`. O build de um wheel Linux precisa dos headers; o uso de um
wheel já compilado precisa das bibliotecas compartilhadas de runtime.

Para remover o launcher e o ícone:

```bash
python scripts/install_linux_desktop.py --remove
```

Feche o TorchBridge e retire a opção de inicialização do Steam antes de mover ou
apagar a pasta. A remoção não apaga perfil, log nem saves. Não há autostart, regras
Hyprland ou serviço de sistema instalado para desfazer.

## Paridade e validação

O núcleo abaixo é único para Windows e Omarchy; não existem versões simplificadas
dos handlers Linux. A mudança está nas fronteiras de sistema.

| Funcionalidade preservada | Implementação Linux / verificação |
| --- | --- |
| PS5/DualSense, Xbox, genéricos, USB/Bluetooth | mesmo SDL/GameController/RAW; enumeração e reconexão cobertas por testes; hardware físico ainda precisa de rodada |
| Escolha persistente, hotplug, calibração RAW, rumble | mesmo `ControllerHub`/perfil/assistente; rumble depende do dispositivo/permissões SDL |
| Movimento direto, âncora, deadzone, aceleração, cursor | mesmo motor; pointer Wayland, coordenadas lógicas; transporte exercitado em sessão real |
| Ataque, habilidades 1–0, modificadores e combos | mesmos handlers; teclado/mouse Wayland; regressões de liberação/cancelamento |
| Roda, pet, deslocamento por painéis e HUD | mesmos modelos, assets e desenho; testes existentes de setores, navegação e animação |
| Tela inicial, criar/carregar personagem e dificuldade | mesmos handlers e offsets; menu inicial exercitado no jogo real com controle virtual SDL |
| Teclado virtual de personagem/pet, caps e confirmação | mesma navegação e assets; região de clique Wayland; texto/caps/símbolos/Unicode testados em janela isolada |
| Inventário, pet, baú e vendedor | mesmos handlers de slots, abas, atalhos e cliques modificados; suíte de regressão compartilhada |
| Atributos, três árvores de habilidades, spells e upgrades | mesmos offsets e regras de foco; testes compartilhados |
| Missões, diário, diálogos, história e recompensas | mesma leitura e navegação; testes compartilhados |
| Encantador, transmutação, sockets | mesmos handlers; testes compartilhados |
| Pesca, portais, morte/respawn, pause, configurações/áudio | mesmos handlers; dados locais lidos do prefixo; testes compartilhados |
| Configuração de atalhos na HUD e popup CEGUI | mesma árvore de memória; base de `CEGUIBase.dll` obtida dos mapas PE do processo |
| Bandeja, ativar/pausar, perfil/reload, calibração visual | mesmo app Qt; abertura de arquivo pelo desktop Linux |
| Instância única, shutdown e perda de foco | flock por usuário; liberação/cancelamento mantidos; SIGINT/SIGTERM com cleanup |
| Janela, sem bordas e fullscreen | layer-shell no Linux; Qt/Win32 + D3D9 opcional no Windows |
| Assets instalados/portáteis | resolução comum de checkout, wheel e PyInstaller; Windows mantém layout do bundle |

### Evidências desta implementação — 2026-11-08

- Omarchy/Hyprland 0.56.2, Python 3.13, pygame-ce 2.5.8, Wayland/Xwayland.
- Monitores 1920×1080 em 125% e 1440×900 em 100%, com origem Y negativa.
- Testes automatizados compartilhados e novos testes Linux: consulte o relatório
  em [TB-21-VALIDACAO.md](TB-21-VALIDACAO.md).
- Transporte real: posição/escala do overlay, esconder/reabrir, cursor absoluto,
  Shift e sua liberação observados no Xwayland, texto exato e clique interceptado
  sem roubar foco.
- Torchlight Steam PE32 + GE-Proton11-12 + SteamLinuxRuntime_4: módulo principal
  encontrado em base relocada `0x7B240000`, layout Steam reconhecido e prefixo
  correto identificado, com Yama em 1.
- Aplicativo completo: jogo lançado por `--launch`, fullscreen lógico 1536×864,
  camada Wayland ativa, tela inicial lida e foco de navegação alterado por um
  controle virtual SDL. Nenhum personagem foi criado/carregado por esse teste.

Isso não comprova uma sessão completa de gameplay nem substitui homologação no
Windows e em controles físicos. A rodada final deve cobrir USB/Bluetooth/rumble,
Steam e GOG, todas as telas da matriz, combate, troca de monitor, Alt+Tab com
modificadores retidos e encerramento. O roteiro Windows original de fullscreen
continua em [FULLSCREEN.md](FULLSCREEN.md). Não há alegação de que testes Linux
validam visualmente o Windows ou a DLL D3D9.

## Referências

- [IPC Hyprland](https://wiki.hypr.land/ipc/): consultas de janela, foco e monitores.
- [Protocolo layer-shell](https://github.com/swaywm/wlr-protocols/blob/master/unstable/wlr-layer-shell-unstable-v1.xml): camada overlay, configuração e foco.
- [Virtual pointer](https://github.com/swaywm/wlr-protocols/blob/master/unstable/wlr-virtual-pointer-unstable-v1.xml).
- [Virtual keyboard](https://github.com/swaywm/wlroots/blob/master/protocol/virtual-keyboard-unstable-v1.xml).
- [Yama no kernel Linux](https://docs.kernel.org/admin-guide/LSM/Yama.html): leitura de processos descendentes e políticas de ptrace.
- As licenças dos protocolos estão preservadas nos próprios XMLs em `native/linux/protocols/`.
