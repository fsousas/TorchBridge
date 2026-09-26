# Arquitetura do TorchBridge

## Fluxo

1. `ControllerHub` lê o dispositivo pelo SDL GameController.
2. Se o SDL não tiver um mapa, o backend RAW usa a calibração salva pelo GUID.
3. `BridgeEngine` processa deadzone, curva e transições em 120 Hz.
4. `WindowLocator` confirma que `Torchlight.exe` está em primeiro plano.
5. `InputInjector` envia scan codes e eventos de mouse pelo Win32 `SendInput`.
6. `SharedOverlayState` entrega apenas o estado visual para a thread do Qt.
7. `GameOverlay` desenha mira, modo, avisos e roda sem receber cliques ou foco.
8. Em fullscreen exclusivo, os mesmos desenhos são rasterizados em BGRA e
   publicados num canal local por PID. A DLL D3D9 x86 os compõe antes de `Present`.

## Princípios de segurança operacional

- Nenhum comando é enviado com o jogo fora de foco.
- Todo clique ou modificador mantido é liberado na perda de foco, pausa ou saída.
- O overlay usa `NOACTIVATE` e é transparente a cliques.
- O leitor de memória acompanha o estado dos menus sem escrever no processo.
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

