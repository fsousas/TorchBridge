# Overlay em fullscreen no Windows

O backend externo Qt depende da composição do desktop. Em fullscreen exclusivo,
o jogo controla a apresentação; elevar uma janela com `TOPMOST` não garante que
ela apareça. O backend nativo adiciona o desenho ao próprio backbuffer D3D9.
A distinção e o papel das otimizações de fullscreen estão documentados pela
[Microsoft](https://devblogs.microsoft.com/directx/demystifying-full-screen-optimizations/).

## Instalação e remoção

O alvo é **Torchlight 1, Windows 10/11, x86, Direct3D 9 clássico**. Steam e GOG
usam executáveis de 32 bits, mesmo em Windows/Python de 64 bits.

Com o jogo fechado, use o menu do ícone TB: **Instalar suporte a fullscreen...**.
Selecione o `Torchlight.exe` real, não um atalho. Depois, reinicie o jogo.
O módulo deve estar em `assets/native/x86/d3d9.dll` na distribuição do TorchBridge.
O empacotamento PyInstaller inclui esse arquivo quando ele existe.

Também é possível instalar a partir dos fontes:

```powershell
.venv\Scripts\python.exe -m torchbridge.fullscreen install "C:\Games\Torchlight\Torchlight.exe"
.venv\Scripts\python.exe -m torchbridge.fullscreen remove "C:\Games\Torchlight\Torchlight.exe"
```

O executável empacotado aceita `--fullscreen-setup install` e
`--fullscreen-setup remove`, que abrem o seletor de arquivo.

A instalação acrescenta somente `d3d9.dll` e `.torchbridge-overlay.json` à pasta
do jogo. Ela verifica o formato PE32 e a identidade da DLL, recusa qualquer
`d3d9.dll` já existente e registra o hash SHA256. A remoção exige que a DLL ainda
corresponda a esse hash. O executável, saves e configurações do jogo são preservados.
Se o Windows negar acesso à pasta, execute o TorchBridge com o mesmo nível de
privilégio necessário para escrever nela. Feche o jogo antes de remover a DLL.
Durante o uso, mantenha jogo e TorchBridge no mesmo nível de privilégio; se o
jogo estiver como administrador, use `INICIAR_COMO_ADMIN.bat`.

Para atualizar uma instalação, remova a versão anterior e instale a nova. Se
alguém tiver substituído a DLL após a instalação, a remoção automática recusará
apagá-la. ReShade, DXVK e outros proxies que usem `d3d9.dll` não são encadeados.

## Funcionamento

O Qt continua responsável pelos desenhos e animações. `GameOverlay` consulta o
canal do PID publicado pelo motor. O consumidor nativo informa o `Windowed` real
do swap chain, dimensões e limites de textura. Com `Windowed = FALSE`, a UI oculta
sua janela e envia um `QImage` em BGRA premultiplicado. Com `Windowed = TRUE`, o
canal é limpo e a janela Qt volta a desenhar. Não há alteração automática de modo
de tela, resolução, bindings ou cadência do motor.

A DLL carrega o runtime D3D9 do diretório do sistema e encaminha as interfaces
clássicas. Os pontos de desenho são `IDirect3DDevice9::Present` e
`IDirect3DSwapChain9::Present`. O renderer salva o estado gráfico, desenha um
quad com alpha premultiplicado e restaura estado, render targets e depth stencil.
As texturas do overlay são liberadas antes de `Reset`, como exige o tratamento de
[dispositivos perdidos do D3D9](https://learn.microsoft.com/en-us/windows/win32/direct3d9/lost-devices).
`Direct3DCreate9Ex` é encaminhado sem overlay; APIs diferentes de D3D9 clássico
não fazem parte deste backend.

O processo do jogo abre `Local\TorchBridge.Overlay.v1.<PID>` e o mutex com sufixo
`.Mutex`. O protocolo é um cabeçalho de 64 bytes (`<16I`), seguido de BGRA. Ele
não contém ponteiros: produtor de 64 bits e consumidor de 32 bits compartilham
o mesmo layout. O mapping tem capacidade de 4096×4096 pixels. Resoluções maiores
são reduzidas proporcionalmente para a textura e ampliadas na composição final.
Isso pode reduzir a nitidez do overlay acima desse limite.

O mutex usa espera zero no loop gráfico. Na contenção, o jogo pode reutilizar o
último frame completo; nunca lê pixels sendo escritos. Frames expiram após
1,5 segundo sem atualização, inclusive após fechamento abrupto do TorchBridge.
Ao pausar, perder foco ou sair normalmente, o produtor limpa a visibilidade.
O consumidor confere novamente o foco antes de desenhar.

No backend externo, posicionamento usa `SetWindowPos` com pixels físicos e
`SWP_NOACTIVATE`. O desenho compensa o fator de escala do Qt; não divide a origem
global de monitores com escalas diferentes. A distinção entre esses espaços é
descrita na [documentação de DPI do Qt](https://doc.qt.io/qt-6/highdpi.html).

## Compilação

No Windows, instale CMake e Visual Studio Build Tools com o componente C++ e o
SDK do Windows. Execute `GERAR_OVERLAY_FULLSCREEN.bat` ou:

```powershell
python scripts/build_fullscreen.py
ctest --test-dir build/fullscreen -C Release --output-on-failure
```

O script configura MSVC com `-A Win32` e copia a DLL para `assets/native/x86`.
Depois, `GERAR_EXE.bat` inclui essa DLL no pacote. Ela é opcional para quem usa
somente o overlay externo. Não copie DLL de 64 bits para a pasta do Torchlight.

No Linux, use LLVM-MinGW ou MinGW com alvo **i686 Windows**:

```sh
python scripts/build_fullscreen.py --compiler /caminho/bin/i686-w64-mingw32-clang++
```

Não há download automático nem escrita na instalação do jogo durante o build.
Arquivos compilados ficam ignorados pelo Git. O workflow `fullscreen.yml`
compila com MSVC, executa os testes nativos no Windows e disponibiliza a DLL como
artefato `torchbridge-fullscreen-x86`.

## Verificações automatizadas

```sh
python scripts/run_tests.py
QT_SCALE_FACTOR=1.5 python scripts/run_tests.py --pattern 'test_overlay*.py'
clang++ -std=c++17 native/fullscreen/protocol_test.cpp -o /tmp/tb-protocol
/tmp/tb-protocol
```

No Windows, defina `QT_SCALE_FACTOR=1.5` no ambiente antes do segundo comando.
Os testes Python usam APIs de entrada simuladas e Qt offscreen. Cobrem transições
Qt/D3D9, perda de foco, PID, coordenadas e rasterização, timeout, contenção do
mutex, frames inválidos e instalação/remoção. O teste C++ portátil cobre os
limites do mesmo protocolo. O teste nativo `proxy_smoke_test` usa D3D9 NULLREF em
janela para conferir carregamento, interfaces COM, `Present` e `Reset`.

**Esses testes e o cross build não comprovam a exibição em fullscreen no jogo.**
A execução visual do Torchlight e do smoke nativo no Windows não foi possível no
ambiente de desenvolvimento Arch Linux. O workflow foi adicionado, mas sua
execução remota não faz parte da validação local.

## Roteiro no Windows, antes de distribuir

1. Sem o módulo, conferir controle/overlay em janela e janela sem bordas.
2. Instalar o módulo, abrir o jogo em fullscreen e abrir radial, inventário, pet,
   menus, diálogos e calibração. A dica do TB deve mostrar Direct3D 9 (fullscreen).
3. Repetir com as otimizações de fullscreen do executável desativadas para
   exercitar fullscreen exclusivo, além do modo otimizado do Windows.
4. Alternar janela/fullscreen e resoluções várias vezes, incluindo 4:3, 1080p e
   1440p; confirmar ausência de tela preta e alinhamento com os cliques.
5. Testar Alt+Tab, minimizar/restaurar, pausa e desconexão do controle. Nenhum
   overlay deve cobrir outro aplicativo e nenhuma entrada deve ficar presa.
6. Fechar o TorchBridge normalmente e também encerrar seu processo. O desenho
   nativo deve sumir imediatamente ou após, no máximo, 1,5 segundo. Reiniciá-lo
   deve reconectar sem reiniciar o jogo. Fechar/reabrir o jogo deve trocar o PID.
7. Testar monitores a 100%, 125% e 150%, inclusive monitor à esquerda do principal.
8. Abrir o jogo sem TorchBridge com a DLL instalada, depois remover a DLL pelo
   menu e abrir novamente. Comparar Steam/GOG e medir FPS/latência em combate.

Se o overlay aparecer em janela mas não em fullscreen, confira se a DLL x86 está
ao lado do executável correto e se o jogo foi reiniciado após instalar. O log
do TorchBridge registra falhas ao abrir o canal. A instalação não cobre OpenGL,
DXVK/Vulkan, D3D9Ex ou wrappers de terceiros que troquem a API gráfica.
