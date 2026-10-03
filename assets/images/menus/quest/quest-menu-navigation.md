# Implementação da navegação do menu de quest via dpad e pontes
## Cores
> Amarelo -  #E6C12A - Slot inicial quando o menu é aberto
> Laranja - #FD6100 - Slots de ponte quando há outro menu no lado oposto da tela (lateral esquerda) aberto
> Verde - #09B200 - Slots de navegaçao normal

## Imagens referencia
- Menu de quests:
    assets/images/menus/quest/Quest-menu-open.png
- Menu de quests + outro menu do lado esquerdo da tela aberto:
    assets/images/menus/quest/Quest-menu-plus-other-menus-open.png

### Instruções
Ao abrir o menu de Quests (tecla Q) quando nao houver nenhum menu aberto o primeiro slot (amarelo) será o slot inicial.
Caso haja algum menu aberto no lado oposto do menu de Quests, ex.: menu de Pet (tecla P) os slots do menu de quest serão laranja interpretando que qualquer movimento para a extremidade esquerda do menu de quest será tratado como ação de ponte para o menu do outro lado, no caso o Pet mas tambem temos o menu de Character (tecla C) 

## Atenção
- Ao realizar a implementaçao cuidar para que:
    - Os slots na parte superior do menu de Quests referente a lista de quests os 6 slots, sendo o primeiro amarelo(ponto inicial do cursor) e os outros 5 logo abaixo, pode haver rolagem dependendo se houver mais de 6 missoes em andamento
    - Quando abrimos o menu de quests a primeira vez o jogo mostra a primeira missao(slot amarelo) quando pressionar o d-pad para baixo deve mover o cursor para o segundo slot e realizar o clique simples, assim o conteudo da missao será mostrado na sessao Description, e assim os demais slots seguindo essa logica
    - Caso eu selecione por exemplo a terceira missão, e depois feche o menu de quests, ao reabrir o jogo armazena que eu tinha aberto a missao 3, o cursor deve saber qual foi a ultima missao selecionada para quando eu abrir o menu novamente.

- Leitura da memoria interna do jogo:
    - Precisamos saber se a missao selecionada tem recompensa e pode ser abandonada pois existem mais 2 slots na parte inferior do menu de quests
    - o primeiro slot é referente se a missao vai ter recompensa ao ser completada
    - o segundo slot é referente se a missao pode ser abandonada
    OBS: esses slots variam conforme o tipo de missao por isso precisamos saber quando habilitar o slot em questao ou nao ao selecionar uma missao