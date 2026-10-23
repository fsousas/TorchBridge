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

## FASE 2
- Os nós devem respeitar o redimencionamento e posicao da hud 

### Mapeamento dos nós de navegação no modo de configuração de atalhos ativado
- Os slots de skill e itens na hud inferior da tela devem ser acessados e navegaveispelo d-pad do controle sempre respeitando os nós na imagem:
- `assets\hud\inferior\nodes.png` imagem em 1280 x 960
- Nessa imagem existem 2 tipos de quadrados:
- Amarelo #E6C12A - Onde o cursor deve ser posicionado ao ativar o modo de configuração
- Verde #09B200 - Nós navegaveis pelo D-pad

- Ao estar em um nó amarelo ou verde e:
    - Pressionarmos o botao norte do controle (Triangulo no ps ou Y no xbox ou X no nintendo ) deve ser disparado o ctrl+clique esquerdo
    - Precssionarmos o botao sul do controle (X no ps ou A no xbox ou leste no nintendo A) deve ser disparado o botao esquerdo para abrir o grid de opções


## FASE 3

### Mapear o grid de opções
- Ao clicar em um slot, um grid com opções aparecem como nas imagens:
- `assets\hud\inferior\abrir-grid-skill-spell-4.png`
- `assets\hud\inferior\abrir-grid-skill-spell-3.png`
- `assets\hud\inferior\abrir-grid-skill-spell-2.png`
- `assets\hud\inferior\abrir-grid-skill-spell.png`
- `assets\hud\inferior\abrir-grid.png`
- OBS: parece que o limite do grid é 7 colunas mas a quantidade maxima de linhas ainda nao consegui mapear, seria ideal se conseguissemos ler da memoria do jogo a posicao de cada item no grid ao abrir pois parece que existe alguma organização no que esse grid mostra, possivelmente skills da primeira linha e spells ficam no topo do grid, cada linha do grid parece respeitar o nivel 