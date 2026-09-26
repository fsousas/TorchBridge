## Mapeamento de Pontos navegáveis no inventário do jogador no ESTADO = In-game
#### Meta - conseguir rastrear a aba ativa no momento pra conseguirmos apresentar mensagens futuras, se possíve quando abrirmos o inventario armazenar o valor tab-1 em uma variavel para controle, pois sempre abre na aba 1 e ao fechar o inventario zerar essa variavel.

### Cores de referencia
Ciano - #0BE0EF | Demarca o ponto de troca de abas

Verde - #09B200 | Demarca todos os slots navegaveis com o cursor através do dpad

Amarelo - #E6C12A | Demarca o slot inicial do cursor ao:
 - Abrir o inventario
 - Trocar de aba

Laranja - #FD6100 | Demarca os slots de transição/ponte entre menus opostos (Pet e Inventário)

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

---

## Transição entre Menus Opostos (Pet e Inventário Simultâneos)
#### Meta - Permitir que o jogador transite o cursor com o D-pad diretamente de um menu para o outro na costura central da tela, mantendo as bordas externas isoladas com seu wrap-around individual (Opção 3).

### Imagem de referencia
> assets\images\inventário\change-between-pet-inventory.png

### Regras de Transição Central (Ponte Laranja - #FD6100)
1. **Do Menu do Pet (Esquerda) para o Inventário (Direita) via D-pad DIREITA:**
   - Estando no Pet em qualquer slot da coluna da borda direita e pressionando **Direita**:
     - Linha 1 Coluna 7 `(1, 7)` $\to$ Inventário Linha 1 Coluna 1 `(1, 1)`
     - Linha 2 Coluna 7 `(2, 7)` $\to$ Inventário Linha 2 Coluna 1 `(2, 1)`
     - Linha 3 Coluna 7 `(3, 7)` $\to$ Inventário Linha 3 Coluna 1 `(3, 1)`
     - Magia superior `pet_spell_2` $\to$ Magia superior `spell_1` do Inventário

2. **Do Inventário (Direita) para o Menu do Pet (Esquerda) via D-pad ESQUERDA:**
   - Estando no Inventário em qualquer slot da borda esquerda e pressionando **Esquerda**:
     - Linha 1 Coluna 1 `(1, 1)` $\to$ Pet Linha 1 Coluna 7 `(1, 7)`
     - Linha 2 Coluna 1 `(2, 1)` $\to$ Pet Linha 2 Coluna 7 `(2, 7)`
     - Linha 3 Coluna 1 `(3, 1)` $\to$ Pet Linha 3 Coluna 7 `(3, 7)`
     - Equipamentos e magias da coluna esquerda (`spell_1`, `main_hand`, `belt`, `gloves`, `helmet`) $\to$ Pet `pet_spell_2`

### Regra da Opção 3 — Extremidades Externas Isoladas
* **Borda Direita do Inventário (Coluna 7):** Pressionar **Direita** continua dando a quebra de linha interna dentro do próprio Inventário:
  - Linha 1 Col 7 `(1, 7)` + Direita $\to$ Linha 2 Col 1 `(2, 1)` do Inventário.
  - Linha 2 Col 7 `(2, 7)` + Direita $\to$ Linha 3 Col 1 `(3, 1)` do Inventário.
  - Linha 3 Col 7 `(3, 7)` + Direita $\to$ Linha 1 Col 1 `(1, 1)` do Inventário.
* **Borda Esquerda do Pet (Coluna 1):** Pressionar **Esquerda** continua dando a quebra de linha interna dentro do próprio Pet:
  - Linha 1 Col 1 `(1, 1)` + Esquerda $\to$ Linha 3 Col 7 `(3, 7)` do Pet.
  - Linha 2 Col 1 `(2, 1)` + Esquerda $\to$ Linha 1 Col 7 `(1, 7)` do Pet.
  - Linha 3 Col 1 `(3, 1)` + Esquerda $\to$ Linha 2 Col 7 `(2, 7)` do Pet.

---

## Tratamento de Hover Residual e Fechamento Limpo de Tooltips (Spells e Travessias)
#### Causa Raiz
No motor gráfico do Torchlight (CEGUI/Runic UI), os slots de spell (`spell_1..4`, `pet_spell_1..2`) são botões que instanciam janelas de descrição flutuante (`SpellTooltip`) e só as destroem quando recebem um evento `EventMouseLeavesArea` / `OnMouseLeave`.
Ao mover o mouse fisicamente ou pelo analógico, o cursor cruza os pixels do pergaminho neutro fora do botão, acionando o `OnMouseLeave` de forma orgânica. Porém, com o D-pad, o teletransporte instantâneo do cursor (saltando 40px–500px em 0ms via `SendInput`) para outro slot ou para o painel oposto faz com que o Windows coalesce os eventos e o widget do spell nunca receba a saída de mouse — fazendo a descrição do spell ficar presa na tela e seguir o cursor.

#### Solução Implementada (`_move_cursor_with_leave_step`)
1. **Ao sair de qualquer slot de spell (`is_leaving_spell`):**
   - O cursor dá um micro-passo de 35px para baixo (`origin_y + 35 * scale`), caindo exatamente no pergaminho neutro do painel (sem slots nem botões).
   - Pausa calibrada de **25ms** (1–2 frames a 60 FPS) para o message pump do jogo processar o evento de saída e fechar o `SpellTooltip`.
2. **Ao cruzar entre painéis opostos (Pet $\leftrightarrow$ Inventário):**
   - O cursor transita pelo centro da tela (`(mid_x, mid_y)` no mundo 3D aberto) por 25ms para desengajar o foco do painel anterior e fechar quaisquer tooltips de itens.
3. **Navegação comum dentro do Grid:**
   - Movimentação direta instantânea (0ms de atraso), mantendo a resposta rápida e sem impacto na fluidez.



