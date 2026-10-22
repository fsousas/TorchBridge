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