# Arquitetura do TorchBridge

## Fluxo

1. `ControllerHub` lê o dispositivo pelo SDL GameController.
2. Se o SDL não tiver um mapa, o backend RAW usa a calibração salva pelo GUID.
3. `BridgeEngine` processa deadzone, curva e transições em 120 Hz.
4. `platform.py` seleciona o backend pelo sistema, sem carregar bibliotecas Linux no Windows.
5. `WindowLocator` confirma identidade e foco do processo; `InputSession` cancela ações se jogo, controle ou ativação mudarem.
6. `InputInjector` envia scan codes/mouse pelo Win32 `SendInput` ou pelos dispositivos virtuais Wayland no Omarchy.
7. `SharedOverlayState` entrega apenas o estado visual para a thread do Qt.
8. `GameOverlay` desenha mira, modo, avisos e roda sem receber cliques ou foco.
9. No Windows, em fullscreen exclusivo, os mesmos desenhos são rasterizados em BGRA e
   publicados num canal local por PID. A DLL D3D9 x86 os compõe antes de `Present`.
10. `WorldMemoryReader` publica posições e entidades ativas do cenário em fotografias
    imutáveis. O módulo x86 seleciona o alvo mais próximo, aplica o highlight e executa
    movimento/interação na thread do jogo; o mesmo painter desenha o aviso nos três
    backends de overlay. A caminhada não gera cliques.
    Layout, limites e uso: [POSICIONAMENTO.md](POSICIONAMENTO.md).

11. `NativeInputClient` descobre o endpoint do módulo na memória do processo
    selecionado e envia intenções por loopback. Sequência, token e validade são
    conferidos no receptor. Uso, catálogo e limites: [MOVIMENTO-SEGURO.md](MOVIMENTO-SEGURO.md).

## Princípios de segurança operacional

- Nenhum comando é enviado com o jogo fora de foco.
- Todo clique ou modificador mantido é liberado na perda de foco, pausa ou saída.
- O overlay usa `NOACTIVATE` e é transparente a cliques.
- O leitor de memória acompanha o estado dos menus sem escrever no processo.
- O módulo de movimento instala hooks apenas em builds reconhecidas, na memória
  do próprio jogo. Destinos e parada usam as funções originais; a posição não é
  escrita. O arquivo executável permanece intacto.
- Fullscreen exclusivo usa uma DLL proxy opcional, carregada pelo Windows junto
  ao jogo. Não há patch no executável nem injeção remota. O instalador acrescenta
  `d3d9.dll` e um manifesto de remoção e recusa substituir DLLs existentes.
- O renderer salva/restaura o estado D3D9 e libera suas texturas antes de `Reset`.
- O canal de imagens usa mutex sem espera na renderização e expira frames em
  1,5 segundo se o TorchBridge parar. O renderer também confere o foco do jogo.
- O Qt usa coordenadas físicas no desenho e posicionamento nativo no Windows,
  corrigindo a diferença entre pixels do jogo e a escala DPI da interface.
- O perfil inválido nunca substitui a última configuração válida em memória.

Veja [FULLSCREEN.md](FULLSCREEN.md) para build, protocolo e validação no Windows.

## Extensões previstas

- editor visual de bindings;
- perfis por classe/personagem;
- action layers para cidade, combate e inventário;
- ícones adaptativos para Xbox e PlayStation;
- telemetria local opcional de latência;
- assinatura de código e instalador MSI para distribuição pública.


## Omarchy Linux (TB-21)

`linux.py` concentra consultas ao IPC Hyprland, coordenadas lógicas, leitura do
estado físico pelo Xwayland, instância única com flock e injeção de entrada.
`linux_process.py` abre `/proc/PID/mem` somente para leitura e descobre bases PE32
pelos mapas reais do processo Proton. `memory.py` conserva a mesma interpretação
de CGame, CEGUI, menus e atributos nas duas plataformas. PID/starttime, bases de
módulos, prefixo e caches são invalidados quando a sessão muda.

`native/linux/wayland.c`, compilado durante a instalação Linux, possui uma conexão
por thread. O motor envia entrada pelos protocolos virtual-keyboard/pointer. A
thread Qt rasteriza o mesmo `_paint_overlay` em ARGB e apresenta buffers shm em
layer-shell. São usados até três buffers, reaproveitados apenas após `release` do
compositor. Sem buffer livre, descarta-se o frame, sem escrever num buffer em uso.
A camada não recebe foco de teclado e só intercepta mouse na região do teclado
virtual. Não há regras locais de Hyprland ou processo Quickshell. O overlay é nativo
Wayland; a DLL de movimento roda dentro do processo PE32 sob Proton.

`--launch` executa o comando Proton/Wine como descendente do aplicativo para
atender Yama em 1. O leitor continua somente leitura e não há mudança de sysctl ou elevação de
privilégios. O launcher acrescenta o override WinMM para o módulo de movimento. O perfil permanece comum, e `resources.py` resolve assets em
checkout, wheel e bundle sem depender do diretório de trabalho.

Guia de uso, limites e matriz de paridade: [LINUX.md](LINUX.md).
