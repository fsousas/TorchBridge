# Implementação Teclado Virtual
## TELA
    Estado = Criar personagem
    Menus = Criar personagem
## Cores
    Amarelo - #F4DC2A - nó inicial do cursor ao abrir o teclado
    Verde - #09B200 - nó de navegação do cursor
    Rosa - #B2007C - nó de retorno do cursor quando fechar o teclado

## Elementos
- background - O background nada mais é do que o fundo do teclado e também é o limitador de largura e altura onde as teclas serão dispostas
- as teclas estao separadas por maiúsculas e minúsculas
- cada tecla tem no seu nome a posição que deve ficar no grid ex:
    1x1 significa que essa tecla fica na posicao linha 1 coluna 1
    3x1 significa que a tecla fica na linha 3 coluna 1
    quando a tecla tem 4x1-e-4x2 significa que ela ocupa na linha 4 a coluna 1 e a coluna 2
    quando a tecla tem 5x1-a-5x10 significa que ela ocupa na linha 5, as colunas de 1 a 10

- O grid será disposto na seguinte exibição:
    assets\keyboard\grid-teclado.jpeg
    com linhas que vao de 1 á 5
    com colunas que vao de 1 á 13
    conforme a imagem a cima mostra

## Comportamento
- Na tela de criação de personagem existem 2 campos de texto
    Nome do personagem
    Nome do pet
- Ao clicar em um campo de texto nome do personagem  o teclado deve aparecer logo a cima do campo de nome conforme o exemplo:
    assets\keyboard\teclado-nome-personagem.png
    - Centralizado horizontalmente
    - Fundo do teclado ancorado ao topo da caixa de nome, reservando o rótulo Character Name e um vão de 8 pixels na base de 768p.
- Ao clicar no campo de texto de nome do pet o teclado deve aparecer ao lado do campo conforme exemplo:
    assets\keyboard\teclado-nome-pet.png
    - Dando o desconto da lateral da tela em que o campo de nome do pet fique visivel
    - Borda direita do teclado ancorada à borda esquerda do painel do pet, com vão de 4 pixels na base de 768p. A largura do painel e o vão escalam pela altura útil da janela, independentemente da largura.
    - Fundo do teclado alinhado ao fundo do painel do pet, preservando o campo à direita.

## Mapeamento do cursor nas teclas
assets\keyboard\exemplo-calibration.jpeg
- ao abrir o teclado, o layout padrão das teclas deverá ser minúscula e o cursor deverá ser deslocado para a tecla com o calibration amarelo
- o cursor pode ser movido pelo d-pad dentro do grid do teclado
- o botão sul do controle de PS e XBOX (PS = X, XBOX = A) executa o disparo da letra selecionada (no controle do NINTENDO é o BOTÃO LESTE = A)
- ao clicar em ok o teclado deve desaparecer e o cursor deve retornar ao nó rosa

### Tecla capslock
default - assets\keyboard\Caps-lock-default-4x1-e-4x2.png
proxima tecla - assets\keyboard\Caps-lock-on-4x1-e-4x2.png
todas as teclas - assets\keyboard\Caps-lock-on-only-next-letter-4x1-e-4x2.png

- ao clicar na teclad de capslock o comportamento deve ser ciclico entre os 3 estados
    default -> next_letter -> all_letters -> default

- o teclado abre com as teclas minusculas (as teclas que tem o nome começando com min-)
- ao clicar a primeira vez no capslock as teclas com o nome min- mudam pras teclas com o nome mai-
- quando o estado do teclado for next_letter e o jogador escolher uma letra, após a insersao desse caracter maiusculo, deve voltar para o estado default(teclas minusculas)
- quando o estado do teclado for all_letters e o jogador selecionar uma teclad o estado do teclado deve ser mantido em all_letters (letras maiusculas)

### tecla backspace
assets\keyboard\Backspace-4x12-e-4x13.png

- deve realizar a ação de apagar o caracter mais recente(funcionar como o backspace do teclado)

### highlights
assets\keyboard\highlight-tecla-dupla.png
assets\keyboard\highlight-tecla-grande.png
assets\keyboard\highlight-tecla-simples.png
assets\keyboard\highlight-tecla-tripla.png
- as teclas quando o cursor ficar em cima delas devem mostrar o highlight, seguindo o esquema de camadas:
[topo]
- cursor
- highlight
- tecla
- background
[fundo]
- as teclas tem tamanhos diferentes:
    as simples tem no nome somente "1 linha e 1 coluna" (3x2)
    as duplas tem no nome "1 linha e 1 coluna e 1 linha e 1 coluna" (3x3-e-3x4) [backspace e capslock]
    as triplas e grandes tem no nome "1 linha e 1 coluna a 1 linha e 1 coluna" (5x1-a-5x10) [as teclas espaço e ok]

### Interação
- quando uma tecla for clicada ela deve diminuir de 1 para 0.97 de escala (para dar uma efeito de afundar) e voltar a escala 1

## Labels
assets\keyboard\info-label-nintendo.png
assets\keyboard\info-label-ps.png
assets\keyboard\info-label-xbox.png
- Ao abrir o teclado deve identificar o controle e mostrar o aviso referente ao controle, logo a cima do bakground do teclado conforme: assets\keyboard\exemplo-calibration.jpeg

## Controles
- d-pad = navega entre os nós
- botao sul(xbox/ps) | botao leste(nintendo) = seleção da tecla
- botao leste (xbox/ps) | botao sul(nintendo) = funciona como backspace
- botao start = fechar teclado(mesma ação do botao OK do teclado virtual)
- botao de gatilho = (ps[L2],xbox[LT],nintendo[ZL]) = alterna o clico entre os 3 estados do teclado no modo capslock
- botoes de ombro (ps[L1,R1],xbox[LB,RB],nintendo[L,R]) = movendo das setas esquerda e direita respectivamente para cada tipo de controle

## Progresso da Implementação

### O que já foi feito
- **Estrutura e Posicionamento Dinâmico:**
  - Posicionamento para `Nome do Personagem`: centralizado sobre a caixa de nome, com espaço para o rótulo e um pequeno vão proporcional.
  - Posicionamento para `Nome do Pet`: junto à esquerda do painel, com fundos alinhados. A distância entre teclado e painel permanece proporcional ao redimensionar.
  - Dimensões calibradas pelas capturas de 1919×1007: background de 568×290 nessa referência. Em janelas estreitas, o conjunto diminui para caber, incluindo a barra de instruções.
  - Renderização, superfície de mouse, navegação e cursor usam a mesma geometria absoluta, incluindo janelas deslocadas e monitores com coordenadas negativas.
- **Abertura e Fechamento:**
  - Abertura ao selecionar o campo e apertar o botão A (Sul no Xbox/PS) ou via clique com o mouse no campo.
  - Fechamento pelo botão Start ou ao clicar com o mouse fora da área do teclado.
  - Retorno do cursor ao campo de texto original (nó rosa `#B2007C`).
- **Renderização Visual Completa:**
  - Background carregado e dimensionado proporcionalmente à resolução.
  - Barra informativa de instruções (`info-label-*.png`) renderizada no topo do teclado conforme o controle conectado (PlayStation, Xbox ou Nintendo).
  - Todas as 52 teclas renderizadas em suas posições exatas no grid 5x13 (letras minúsculas e maiúsculas).
  - Camadas visuais estritamente respeitadas: `Cursor / Nós -> Highlight -> Tecla -> Background`.
  - Highlights correspondentes exibidos na tecla sob foco (`simples`, `dupla`, `tripla` e `grande`).
  - Efeito visual de afundar no clique (escala 0.97).
  - Nó inicial Amarelo (`#F4DC2A`) na tecla `3x1` (tecla 'A') e nós de navegação/calibração.
- **Lógica e Controles:**
  - Navegação do grid pelo D-Pad respeitando as teclas largas (Caps Lock 2 colunas, Backspace 2 colunas, Espaço 10 colunas e OK 3 colunas).
  - Ciclo de Caps Lock nos 3 estados (`default` -> `next_letter` -> `all_letters` -> `default`) acionado pelo gatilho LT/L2/ZL e pela tecla Caps Lock.
  - Botão B (ou Leste) funcionando diretamente como Backspace.
  - Suíte de testes unitários automatizados validando o modelo, cálculo de coordenadas e overlay.

### Pendências corrigidas nesta implementação
- Injeção das letras, números e símbolos conforme as imagens `min-` e `mai-`, usando eventos Unicode UTF-16 do Windows, sem depender do layout físico ou do Caps Lock do sistema.
- Setas `LEFT`/`RIGHT` reconhecidas pelo injetor e enviadas como scancodes estendidos, corrigindo a exceção dos botões de ombro.
- OK pelo controle e pelo mouse fecha o teclado e retorna o cursor ao campo ativo; Start segue a mesma ação, sem enviar Escape ao jogo.
- Abertura foca o campo real antes de mover o cursor ao nó amarelo e reinicia o modo minúsculo.
- Cliques e hover nas teclas são recebidos por uma superfície sem ativação; o campo do jogo mantém foco e posição de edição. As coordenadas consideram pixels físicos e escala de DPI.
- Cliques físicos nos campos abrem/trocam o teclado e cliques externos o fecham.
- Confirmação pelo botão sul em Xbox/PlayStation e leste em Nintendo; o outro botão apaga.
- Os comandos do teclado são consumidos antes dos bindings gerais. Segurar a confirmação após OK não dispara clique residual no jogo.
- Shift de próxima letra só é consumido após enviar uma letra com sucesso; espaço e símbolos preservam esse modo.
- Efeito de pressionamento com duração de 120 ms, inclusive para cliques do mouse.
- Assets do teclado incluídos no pacote PyInstaller, para manter a renderização no executável distribuído.

### Validação
- Testes automatizados de mapeamento dos assets, injeção Unicode, flags das setas, navegação, modos de maiúsculas, mouse, Nintendo, foco, fechamento e consumo dos comandos.
- No ambiente Linux, a execução dos testes exige simular as DLLs e os construtores dependentes de Windows. Isso valida a lógica e os eventos Qt, mas não confirma a recepção de `SendInput` pelo jogo.
- A validação final no Torchlight em Windows continua necessária, incluindo os dois campos, edição no meio do texto, DPI diferente de 100% e fullscreen exclusivo (cuja renderização usa o backend Direct3D 9).

### Âncoras e proporção
- `char_create_pet_panel_rect` e `char_create_text_field_rect` definem os limites da UI em pixels físicos da área cliente. A barra de título não entra na altura usada nos cálculos.
- O painel do pet acompanha a borda direita; a caixa do personagem acompanha o centro. A altura útil determina todos os tamanhos e espaçamentos, conforme `docs/proporcao/solution.md`.
- O hit test dos campos usa esses mesmos retângulos, substituindo a tolerância fixa de 80×30 pixels.
- Testes reproduzem a área cliente de 830×620 das capturas fornecidas, além de redimensionamentos de 4:3 para ultrawide, resoluções de 480p a 2160p e origens deslocadas.

- Os nós de calibração amarelo/verde nas teclas e rosa no campo aparecem somente com `overlay.show_calibration` ativado. No uso normal, o foco da tecla é indicado pelo highlight.
