## Mapeamento de Pontos navegáveis no inventário do jogador no ESTADO = In-game
#### Meta - conseguir rastrear a aba ativa no momento pra conseguirmos apresentar mensagens futuras, se possíve quando abrirmos o inventario armazenar o valor tab-1 em uma variavel para controle, pois sempre abre na aba 1 e ao fechar o inventario zerar essa variavel.

### Cores de referencia
Ciano - #0BE0EF | Demarca o ponto de troca de abas

Verde - #09B200 | Demarca todos os slots navegaveis com o cursor através do dpad

Amarelo - #E6C12A | Demarca o slot inicial do cursor ao:
 - Abrir o inventario
 - Trocar de aba

### Imagens de referencia
> Aba 1 - Slots de equipamentos(Sempre abre nessa aba quando o inventario abre, nao importa a ação que dispare a abertura do inventario)
assets\images\inventário\inventario-4x3-tab-1.png

> Aba 2 - Slots de Spells
assets\images\inventário\inventario-4x3-tab-2.png

> Aba 3 - Slots de Fish
assets\images\inventário\inventario-4x3-tab-3.png

#### IMPORTANTE!
> Todas as 3 abas de slots tem os mesmos pontos de navegação na mesma posição!
21 no total - 3 linhas e 7 colunas

> Estando com o menu de inventario aberto e o cursor estando na metade direita da tela, ao pressionar L2 ou R2 será possivel trocar entre abas. respeitando a aba ativa atualmente, nao importando a posição do cursor desde que esteja na metade direita da tela. ao trocar de aba o cursor deve ser poscionado no slot 1 da aba que sera aberta.

> A navegação entre abas deve clicar entre Aba 1 > Aba 2 > Aba 3 > Aba 1

> Na parte superior do menu de inventario quando aberto existem outros pontos de navegação

> É possivel transitar entre os slots do inventario na parte inferior do menu e a parte superior onde ficam os itens equipados no personagem através do dpad

#### ATENÇÃO!!!
> Funcionalidades que ja existem ao abrir o menu de inventario continuarão existindo, como:
- pressionar Triangulo para jogar o item do inventario do player para o inventario do pet
- pressionar quadrado para equipar o item em que o cursor está sobre ou utilizar como no caso dos mapas ou poções e pergaminhos
- mover o analogico esquerdo com somente o inventario aberto continua movendo o personagem como é atualmente caso somente o inventario esteja identificado como aberto sem nenhum outro menu, como mercador, menu de pet, bau etc.
- abrir o menu radial coninua sendo possível caso somente o inventario esteja identificado como aberto sem nenhum outro menu, como mercador, menu de pet, bau etc.

>Se o cursor estiver nos slots que ficam nas estremidades do grid, e realizar uma ação de mover o cursor com o dpad para fora do grid, o cursor deve mudar de linha e coluna. Exemplo:
cursor na posicao x1 y1 se mover para a esquerda no dpad, faz ele mover o cursor para a posicao x3 y7, se estiver na x2 y7 e mover para a direita, move o cursor para x3 y1

> Caso o Cursor esteja na ultima linha do grid e o jogador mover para baixo do dpad, nada acontece

---

## Mapeamento de Pontos navegáveis no Menu do Pet no ESTADO = In-game
#### Meta - Navegação completa idêntica ao inventário do jogador, com a diferença de estar ancorado à esquerda da tela (rect.left).

### Imagem de referencia
> assets\images\inventário\pet-4x3.png

### Comportamento e Regras
1. **Rastreamento de Abas:**
   - Variável de controle `pet_inventory_tab` inicializada em `tab-1` ao abrir e zerada ao fechar.
   - Posicionamento inicial do cursor sempre no Slot 1 (amarelo) `(1, 1)`.

2. **Troca de Abas (L2 / R2):**
   - Ativa quando o cursor estiver na **metade esquerda da tela** (`cur_x < rect.left + rect.width * 0.5`).
   - R2 avança: Aba 1 > Aba 2 > Aba 3 > Aba 1.
   - L2 recua: Aba 1 > Aba 3 > Aba 2 > Aba 1.
   - Sequência calibrada de cliques: hover 60ms -> hold de clique 40ms -> pós-clique 30ms -> retorno para Slot 1.

3. **Grid 3x7 (21 slots):**
   - Navegação via D-pad idêntica ao inventário do jogador com wrap-around horizontal nas extremidades e bloqueio inferior na linha 3.

4. **Equipamentos e Spells Superiores do Pet (5 slots):**
   - Transição fluida entre Linha 1 do grid e os 5 slots superiores (`pet_spell_1`, `pet_ring_1`, `pet_collar`, `pet_ring_2`, `pet_spell_2`).

5. **Movimento Direto e Menu Radial:**
   - Com apenas o menu de Pet aberto, o analógico esquerdo mantém o movimento direto do personagem (deslocado para a área visível à direita).
   - O menu radial (LB) continua disponível quando apenas o menu de Pet ou Inventário estiverem abertos.
   - Quando ambos estiverem abertos, a metade da tela onde o cursor está determina qual menu o D-pad e os gatilhos L2/R2 controlam.

