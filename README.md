# TorchBridge

Controle de PS5, Xbox e controles genéricos no **Torchlight 1 para PC**, com
movimento direto, cursor analógico, roda de habilidades e overlay transparente.

O TorchBridge reconhece o controle pelo SDL, acompanha a janela do Torchlight e
lê o estado dos menus na memória. Funciona no **Windows 10/11** e como aplicação
**nativa no Omarchy Linux/Hyprland**, usando a edição Windows x86 do jogo via Proton.
O motor, os menus, o teclado virtual, os perfis e os desenhos são compartilhados.

No Windows, usa `SendInput`, overlay Qt e um módulo Direct3D 9 opcional para
fullscreen exclusivo. No Omarchy, usa entrada virtual e overlay Wayland acima do
fullscreen. O movimento seguro usa um módulo x86 no jogo nos dois sistemas.
Instalação, Steam/Proton, permissões, matriz de
funcionalidades e evidências: **[docs/LINUX.md](docs/LINUX.md)**.

### Começar no Omarchy

```bash
./INSTALAR.sh
./INICIAR_TORCHBRIDGE.sh --diagnose
```

Para o Steam, feche o TorchBridge e configure a opção de inicialização do jogo:

```text
"/caminho/TorchBridge/INICIAR_TORCHBRIDGE.sh" --launch %command%
```

Esse modo permite a leitura de memória com a política Linux padrão, sem root.
Desative Steam Input e use Proton/WineX11. A edição ELF do jogo não usa os mesmos
mapas de memória e não está no escopo deste backend. Veja o guia Linux antes de
instalar ou distribuir; a paridade implementada e a homologação pendente estão
separadas na matriz de validação.

## O que já está implementado

- DualSense/PS5 via USB ou Bluetooth;
- controles Xbox 360, One e Series via USB, receptor ou Bluetooth;
- controles genéricos reconhecidos pelo banco de mapeamento SDL;
- assistente de calibração para controles genéricos não reconhecidos;
- conexão e desconexão do controle com o programa aberto;
- loop de entrada configurado em 120 Hz;
- movimento direto no analógico esquerdo;
- mira/cursor com aceleração no analógico direito;
- modo separado para inventário, lojas e menus;
- roda visual de seis atalhos (uma por posição do perfil);
- detecção automática das versões Steam e GOG pelo `Torchlight.exe`;
- rastreador de painéis abertos pela roda (C/P à esquerda, I/S/Q/J à direita), com
  indicador discreto no topo central do overlay;
- envio de comandos somente quando o jogo está em primeiro plano;
- leitura das posições do jogador e dos elementos interativos do cenário;
- aviso de proximidade com ícones por controle: **A/×** coleta itens no chão e ataca destrutíveis,
  **D-pad para cima** interage com os demais elementos;
- liberação automática de cliques e teclas ao trocar de janela;
- calibração do ponto central do personagem dentro do jogo;
- perfil JSON editável e recarregado automaticamente;
- script para gerar um executável portátil com PyInstaller.

## Instalação rápida no Windows

Requisitos: Windows 10/11, Torchlight 1 e Python 3.11 ou mais recente.

1. Extraia a pasta em um local permanente.
2. Execute `INSTALAR.bat` uma única vez.
3. Execute `INICIAR_TORCHBRIDGE.bat`.
4. Conecte o controle e abra o Torchlight.

O programa fica no ícone **TB** ao lado do relógio do Windows. Pelo menu desse
ícone é possível pausar, abrir o perfil, recarregar alterações ou sair.

No submenu **Controle**, escolha o dispositivo que deseja usar. A preferência
fica salva entre execuções; desconectar o controle selecionado não transfere
os comandos para outro dispositivo. **Selecionar automaticamente** escolhe e
salva o primeiro controle disponível novamente.

### Se o jogo for aberto como administrador

O Windows bloqueia entradas enviadas por um programa com privilégio menor.
Nesse caso, use `INICIAR_COMO_ADMIN.bat`. Não é necessário usar essa opção se o
Torchlight estiver rodando normalmente.

### Steam

Nas propriedades do Torchlight, desative o Steam Input para esse jogo enquanto
usar o TorchBridge. Deixar os dois mapeadores ativos ao mesmo tempo pode gerar
cliques ou teclas duplicados.

### Overlay

Em janela e janela sem bordas, o overlay Qt acompanha o jogo e desaparece ao
perder foco. Em **fullscreen exclusivo**, o módulo Direct3D 9 desenha os mesmos
elementos dentro do frame do Torchlight, sem mudar o modo de tela do jogo.

Para habilitar fullscreen:

1. Feche o Torchlight. A distribuição precisa incluir `assets/native/x86/d3d9.dll`;
   ao desenvolver a partir dos fontes, gere-a com `GERAR_OVERLAY_FULLSCREEN.bat`
   (CMake + Visual Studio Build Tools com C++ para x86).
2. No menu do ícone **TB**, escolha **Instalar suporte a fullscreen...** e
   selecione o `Torchlight.exe` da instalação Steam ou GOG.
3. Abra o Torchlight com o TorchBridge ativo e habilite tela cheia no jogo.
   A dica do ícone TB indicará `Overlay: Direct3D 9 (fullscreen)` quando conectado.

Para desfazer, feche o jogo e use **Remover suporte a fullscreen...**. A instalação
recusa substituir uma `d3d9.dll` existente, inclusive de ReShade ou DXVK.

O backend nativo foi compilado para Windows x86 e tem testes de protocolo e de
integração preparados. **A validação visual em fullscreen com o Torchlight no
Windows ainda precisa ser realizada**; compilar e testar no Linux não a substitui.
Detalhes, limites e roteiro: [docs/FULLSCREEN.md](docs/FULLSCREEN.md).

## Mapeamento padrão

| Controle | Ação no Torchlight |
| --- | --- |
| Analógico esquerdo | Movimento pela navegação nativa; cursor acompanha a mira |
| Analógico direito | Mira e cursor |
| A / Cruz (botão de baixo) | Clique esquerdo: atacar, mover, coletar e confirmar |
| X / Quadrado (botão da esquerda) | Clique direito: habilidade secundária |
| B / Círculo | Atalho 2, repete enquanto segurado |
| Y / Triângulo | Atalho 1, repete enquanto segurado |
| Direcional cima | Interagir com o elemento próximo indicado no overlay |
| Direcional direita | Tab, mapa/minimapa |
| Direcional esquerda | Aciona o botão roxo da HUD e retorna o cursor |
| Segurar LB / L1 + analógico direito | Roda de atalhos 1–6 |
| RB / R1 | Atalho 3, repete enquanto segurado |
| RT / R2 | Atalho 4, repete enquanto segurado |
| LT / L2 + A, X, Y, B, RB, RT | Atalhos 5, 6, 7, 8, 9, 0; repetem enquanto segurados |
| R3 | Clique esquerdo |
| Back / Create / Select | Alterna entre movimento direto e modo cursor |
| Start / Options | Esc, menus e retorno |

As habilidades de 1 a 0 são acionadas novamente a cada 120 ms enquanto o botão
estiver pressionado. O próprio jogo controla cooldown, mana e tempo de execução.

Na roda, a posição superior é o atalho 1 e as demais seguem no sentido horário.
O botão A confirma a seleção (com a roda aberta, A e X não geram clique de
mouse no jogo). Uma vibração curta indica a troca de posição.

As opções da roda também abrem os painéis do jogo: **C** e **P** no lado
esquerdo da tela; **I**, **S**, **Q** e **J** no lado direito. Escolher a mesma
opção de novo fecha o painel, e um indicador discreto no topo central do overlay
mostra, em tempo real, quais painéis estão abertos (esquerdo | direito). Com um
único painel aberto, a roda de atalhos e o ponto central do movimento deslocam-se
12,5% da largura para o lado oposto do painel (ex.: painel esquerdo aberto → roda
e âncora à direita), mantendo o alvo na área visível.

## Modos de uso

### Elementos próximos (TB-18)

Em movimento direto, aproxime-se de um NPC, portal, escadas, fonte, porta,
alavanca ou local de pesca. O overlay indica o alvo mais próximo; pressione
**D-pad ↑** para interagir. O módulo valida a instância e o alcance no próprio jogo. Segurar não repete a ação.

Se o NPC estiver dentro do raio, mas além do alcance da conversa, o personagem
se aproxima pela navegação do jogo antes de conversar. Mover o analógico durante
essa aproximação cancela a conversa pendente e retoma a caminhada imediatamente.

Barris comuns, explosivos e demais destrutíveis recebem um ataque com **A (Xbox/Nintendo)**
ou **× (PlayStation)**, com o ícone `interact-*.png`,
mantendo o personagem parado. O ataque usa a habilidade configurada no clique
esquerdo, com o alcance, mana e cooldown dela; quando esse slot usa ataque comum,
vale o alcance da arma. O jogo verifica obstáculos e disponibilidade da ação.
Fora de alcance, o personagem permanece parado, sem caminhar até o objeto.
O raio de seleção dos destrutíveis é o dobro do raio comum: 9 unidades no padrão
de 4,5. Fishing holes têm um círculo próprio de pelo menos 2,5 unidades;
a interação fica disponível quando esse círculo toca o raio do personagem.
Para pesca, a altura do píer em relação à água não bloqueia essa seleção.
Na interface de pesca, somente os botões sul e leste funcionam: no Xbox e
PlayStation, sul faz um clique esquerdo simples no anzol e leste clica 50 px
acima para fechar. No Nintendo, essas duas ações são invertidas. Os cliques
liberam os modificadores anteriores e não usam Shift ou Ctrl.

Itens, equipamentos e ouro no chão usam **A (Xbox/Nintendo)** ou **× (PlayStation)**
para coleta nativa. O aviso usa `interact-*.png` para coletas e destrutíveis e
`dpad-up-*.png` para os demais elementos, seguindo a família do controle ou o
layout escolhido na HUD. Só a indicação do botão é substituída por imagem;
nome, informações e distância continuam visíveis. Quando Alt/D-pad ← mostra
o nome nativo de um objeto usado pelo D-pad ↑, aparece somente o ícone à
esquerda desse tooltip, usando o novo ícone com fundo claro em 48 px.
NPCs mantêm suas informações completas.
Segurar a coleta não vira
ataque quando o item desaparece: é preciso soltar o botão antes de outra ação.
Concluir uma coleta ou um ataque a destrutível libera a caminhada sem a espera
extra de 1,5 s; a duração normal da ação do jogo continua sendo respeitada.

Ao ativar **Modo de calibração** no ícone TB, o overlay também mostra as
coordenadas, os marcadores dos elementos do cenário e o raio de interação.
Mercadores e NPCs com missão recebem identificação própria, incluindo missão
disponível, em andamento ou pronta para entregar, conforme o marcador do jogo.

Coordenadas X/Y, raio configurável, lista completa em JSON, limites e validação
Windows/Omarchy: [docs/POSICIONAMENTO.md](docs/POSICIONAMENTO.md).

### Movimento direto

O analógico esquerdo envia destinos à navegação do próprio jogo e pede parada
quando volta ao centro. Durante a caminhada, o cursor acompanha a mira indicada
pelo analógico, sem manter clique esquerdo. Ao soltar o analógico, o cursor fica
na última posição. O alvo interativo mais próximo recebe o highlight nativo, sem precisar
apontar o mouse, e **D-pad ↑** envia a interação explícita. Segurar não repete.

O TorchBridge prepara automaticamente a integração nas instalações Steam/GOG
reconhecidas. Abra o aplicativo e o jogo normalmente; se o Torchlight já estava
aberto durante uma atualização, reinicie o jogo uma vez. No Omarchy, a ativação
fica associada ao Torchlight no Proton e o próprio módulo fornece acesso somente
de leitura, sem exigir --launch. Na calibração aparecem estado, direção, destino, highlight
e eventuais bloqueios. Instalação, tipos cobertos e detalhes:
[Movimento seguro](docs/MOVIMENTO-SEGURO.md).

O analógico direito continua movendo a mira. O ataque comum com A/Cruz usa Shift
no overworld; coleta e ataque a destrutíveis selecionados usam os comandos nativos
descritos acima.
X/Quadrado usa a habilidade do clique direito. Menus suspendem a caminhada.

### Cursor / menus

Pressione Back/Create/Select para entrar no modo cursor. Os dois analógicos
podem movimentar a seta e A/X funcionam como os dois botões do mouse.
Use esse modo no inventário, árvore de habilidades, lojas e diálogos. Pressione
Back/Create/Select novamente para retornar ao movimento direto.

## Calibrar o centro do personagem

O herói normalmente fica próximo ao centro da tela. Caso o movimento pareça
deslocado:

1. coloque o cursor do mouse exatamente sobre o personagem;
2. segure **Back/Create + Start/Options** por 0,8 segundo;
3. aguarde a mensagem `Centro do personagem calibrado`.

O ponto é salvo no perfil e continuará válido nas próximas execuções. Repita a
calibração se mudar resolução, proporção de tela ou escala da interface.

## Controle genérico

Primeiro teste sem calibrar: o SDL já normaliza a maioria dos controles atuais.
Se os eixos ou botões estiverem trocados:

1. feche o TorchBridge;
2. execute `CALIBRAR_CONTROLE_GENERICO.bat`;
3. siga as instruções, mexendo somente no comando solicitado;
4. abra novamente pelo `INICIAR_TORCHBRIDGE.bat`.

A calibração grava o GUID do dispositivo, portanto outro controle conectado não
deve tomar o lugar daquele que foi configurado.

## Personalizar sensibilidade e botões

Clique com o botão direito no ícone **TB** e escolha **Abrir perfil de
controles**. O arquivo fica, por padrão, em:

```text
%APPDATA%\TorchBridge\perfil.json
```

Os campos mais úteis são:

```json
{
  "input": {
    "poll_hz": 120,
    "deadzone": 0.18,
    "response_curve": 1.6
  },
  "movement": {
    "anchor_x": 0.5,
    "anchor_y": 0.47,
    "movement_radius_percent": 0.16,
    "click_center_fraction": 0.15
  },
  "cursor": {
    "speed_pixels_per_second": 1450
  }
}
```

- `deadzone`: aumente se o personagem andar sozinho; reduza para maior resposta.
- `response_curve`: maior deixa o começo do analógico mais preciso.
- `movement_radius_percent`: raio da mira e do cursor durante a caminhada, em fração da altura da janela.
- `click_center_fraction`: alcance inicial da mira e do cursor ao sair da deadzone; não gera cliques nem determina o destino nativo.
- `speed_pixels_per_second`: velocidade do cursor analógico.
- `bindings`: troca as teclas ligadas aos botões e à roda 1–6.
- `overlay.enabled`: use `false` para desligar somente os elementos visuais.

O perfil é verificado a cada segundo. Salve o JSON e aguarde a mensagem de
recarregamento. Se o JSON estiver inválido, a última configuração válida
continua ativa. O log técnico fica em `%APPDATA%\TorchBridge\torchbridge.log`.

## Gerar um executável

Em um computador Windows, execute `GERAR_EXE.bat`. O resultado será criado em:

```text
dist\TorchBridge\TorchBridge.exe
```

O formato de pasta inicia mais rápido que um executável único e mantém juntos
os componentes do SDL e do Qt. Distribua a pasta `dist\TorchBridge` inteira.
Gere o módulo com `GERAR_OVERLAY_FULLSCREEN.bat` antes de empacotar para incluir
o suporte a fullscreen exclusivo. O empacotamento sem a DLL continua disponível
para o overlay externo.

## Verificação para uma primeira versão pública

Antes de distribuir, faça uma rodada real nas combinações abaixo:

- Steam + Windows 11 + controle Xbox via XInput;
- Steam + Windows 11 + DualSense USB e Bluetooth;
- GOG + Windows 10 + controle DirectInput genérico calibrado;
- 1920×1080, 2560×1440 e monitor com escala do Windows em 125%/150%;
- jogo em janela, janela sem bordas e tela cheia;
- inventário, lojas, pesca, portais, pet e combate com muita movimentação.

Os testes automatizados validam deadzone, curva, setores da roda, normalização de
gatilhos e persistência do perfil. No diretório do projeto:

```text
python scripts/run_tests.py -v
```

Esse comando funciona no Windows e Linux, simulando as fronteiras de entrada nos
testes do motor e forçando Qt offscreen. Ele não envia entrada ao desktop nem
executa o jogo. O smoke test opt-in Linux e a validação de integração estão em
[docs/LINUX.md](docs/LINUX.md).

A suíte também verifica sinais Qt e o encerramento normal de um subprocesso:
uma extensão pode abortar depois de todos os testes terem passado. No Python
3.11, o projeto exclui PySide6 6.12.0 devido ao
[erro de referências PYSIDE-3474](https://qt-project.atlassian.net/browse/PYSIDE-3474).
Instale as dependências com `python -m pip install -e .` para aplicar essa restrição.

## Limite técnico honesto

A edição de PC do Torchlight foi desenhada para apontar e clicar; a edição de
Xbox recebeu uma interface própria. Uma camada externa consegue deixar o
controle fluido e consistente, mas não substitui todos os menus do jogo por uma
UI de console. Fazer isso exigiria portar a interface da edição de Xbox ou
alterar profundamente o executável, o que seria frágil e incompatível entre
versões. O TorchBridge concentra o ganho onde ele é maior: movimento, combate,
habilidades e navegação sem abandonar o controle.

## Referências técnicas

- Microsoft `SendInput`: <https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendinput>
- pygame-ce Controller/SDL: <https://pyga.me/docs/ref/sdl2_controller.html>
- pygame-ce Joystick: <https://pyga.me/docs/ref/joystick.html>
- Guia interno: [docs/PYGAME.md](docs/PYGAME.md) — como o TorchBridge usa pygame/SDL2.
- Torchlight no Steam: <https://store.steampowered.com/app/41500/Torchlight/>

Torchlight é marca de seus respectivos proprietários. Este projeto é uma
ferramenta independente e não afiliada ao desenvolvedor ou à publicadora.

