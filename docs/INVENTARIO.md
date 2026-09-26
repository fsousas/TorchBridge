## Mapeamento de Pontos navegáveis no inventário do jogador no ESTADO = In-game
#### Meta - conseguir rastrear a aba ativa no momento pra conseguirmos apresentar mensagens futuras, se possíve quando abrirmos o inventario armazenar o valor tab-1 em uma variavel para controle, pois sempre abre na aba 1 e ao fechar o inventario zerar essa variavel.

### Cores de referencia
Ciano - #0BE0EF | Demarca o ponto de troca de abas

Verde - #09B200 | Demarca todos os slots navegaveis com o cursor através do dpad

Amarelo - #E6C12A | Demarca o slot inicial do cursor ao:
 - Abrir o inventario
 - Trocar de aba

Laranja - #FD6100 | Demarca os slots de transição/ponte entre menus opostos (Pet e Inventário)

Rosa - #FD62CE | demarca a posição que o cursor deve ir para trocar de aba quando estivermos interagindo com algum npc de venda te itens.

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

---

## Mapeamento de Pontos Navegáveis no Menu do Baú (Stash) no ESTADO = In-game
#### Meta - Navegação fluida e intuitiva pelo Baú de armazenamento compartilhado/pessoal e pelo Inventário do Pet integrado na metade esquerda da tela (rect.left), com pontes bidirecionais de alta precisão para o Inventário do Jogador na metade direita.

### Imagem de Referência
> `assets\images\inventário\bau-inventario-4x3.png`

```
+-------------------------------------------------------------+-------------------------------------------------------------+
|                      PAINEL ESQUERDO                        |                       PAINEL DIREITO                        |
|                        (Baú + Pet)                          |                    (Inventário do Jogador)                  |
+-------------------------------------------------------------+-------------------------------------------------------------+
|  [BAÚ SUPERIOR: 6 Linhas x 7 Colunas = 42 Slots]            |  [EQUIPAMENTOS E MAGIAS: 16 Slots]                          |
|  L1: [1,1] [1,2] [1,3] [1,4] [1,5] [1,6] [1,7(Ponte)]  ---> |  helmet                                                     |
|  L2: [2,1] [2,2] [2,3] [2,4] [2,5] [2,6] [2,7(Ponte)]  ---> |  gloves                                                     |
|  L3: [3,1] [3,2] [3,3] [3,4] [3,5] [3,6] [3,7(Ponte)]  ---> |  belt                                                       |
|  L4: [4,1] [4,2] [4,3] [4,4] [4,5] [4,6] [4,7(Ponte)]  ---> |  belt                                                       |
|  L5: [5,1] [5,2] [5,3] [5,4] [5,5] [5,6] [5,7(Ponte)]  ---> |  main_hand                                                  |
|  L6: [6,1] [6,2] [6,3] [6,4] [6,5] [6,6] [6,7(Ponte)]  ---> |  spell_1                                                    |
|           ^                   |                             |                                                             |
|   (D-pad Cima)         (D-pad Baixo)                        |                                                             |
|           |                   v                             |                                                             |
|  [PET INFERIOR: 3 Abas + 3 Linhas x 7 Colunas = 21 Slots]   |  [INVENTÁRIO INFERIOR: 3 Abas + 3 Linhas x 7 Colunas]       |
|  Abas: [Equip] [Spells] [Fish]  (L2/R2)                     |  Abas: [Equip] [Spells] [Fish]  (L2/R2)                     |
|  L1: [1,1(Amarelo)] [1,2] ... [1,6] [1,7(Ponte)]       ---> |  L1: [1,1] [1,2] ... [1,6] [1,7(Wrap)]                      |
|  L2: [2,1]          [2,2] ... [2,6] [2,7(Ponte)]       ---> |  L2: [2,1] [2,2] ... [2,6] [2,7(Wrap)]                      |
|  L3: [3,1]          [3,2] ... [3,6] [3,7(Ponte)]       ---> |  L3: [3,1] [3,2] ... [3,6] [3,7(Wrap)]                      |
+-------------------------------------------------------------+-------------------------------------------------------------+
```

---

### Estrutura do Painel Esquerdo (Baú)
O menu do Baú é composto por duas seções verticais integradas:
1. **Seção Superior (Grid do Baú de Armazenamento):**
   - Grid de **6 linhas x 7 colunas** (total de **42 slots** de baú).
   - Ancorado à borda esquerda: `x = rect.left + (63.5 + (col - 1) * 40.0) * scale`.
   - Alturas base das 6 linhas (calibradas em 1024x768):
     - Linha 1: `109.5` (Y base)
     - Linha 2: `164.5` (+55.0)
     - Linha 3: `219.5` (+55.0)
     - Linha 4: `277.5` (+58.0 - divisor intermediário)
     - Linha 5: `332.5` (+55.0)
     - Linha 6: `387.5` (+55.0)
2. **Seção Inferior (Pet Inventory integrado):**
   - 3 abas em Ciano (`#0BE0EF`): `Equipment`, `Spells`, `Fish` (controladas por L2/R2 na metade esquerda).
   - Grid de **3 linhas x 7 colunas** (total de **21 slots** do inventário do pet).
   - Posição inicial: Slot `(1, 1)` em Amarelo (`#E6C12A`).

---

### Tabela de Cores e Funções no Overlay
| Cor | Hex | Função / Significado | Quantidade no Baú |
| :--- | :--- | :--- | :--- |
| **Amarelo** | `#E6C12A` | Ponto de foco inicial ao abrir o Baú ou trocar de aba | 1 slot (`('pet', 1, 1)`) |
| **Ciano** | `#0BE0EF` | Abas de navegação clicáveis via L2 / R2 | 3 abas (`pet_tab_1..3`) |
| **Verde** | `#09B200` | Slots de navegação interna regular via D-pad | 53 slots (36 baú + 17 pet) |
| **Laranja** | `#FD6100` | Pontes de transição inter-menus (Coluna 7) | 9 slots (6 baú + 3 pet) |

---

### Regras de Navegação no Baú

#### 1. Navegação Vertical Contínua (Pet $\leftrightarrow$ Baú Superior)
* **Pet para Baú:** Estando na Linha 1 do Pet (`('pet', 1, col)`) e pressionando **D-pad Cima**, o cursor sobe diretamente para a Linha 6 do Baú (`('stash', 6, col)`), preservando a coluna.
* **Baú para Pet:** Estando na Linha 6 do Baú (`('stash', 6, col)`) e pressionando **D-pad Baixo**, o cursor desce diretamente para a Linha 1 do Pet (`('pet', 1, col)`), preservando a coluna.
* **Bloqueio no Topo:** Estando na Linha 1 do Baú Superior e pressionando **D-pad Cima**, o cursor permanece onde está (sem saída de tela).
* **Bloqueio no Fundo:** Estando na Linha 3 do Pet Inferior e pressionando **D-pad Baixo**, o cursor permanece onde está.

#### 2. Tabela Mestra de Pontes Centrais (Coluna 7 $\leftrightarrow$ Inventário)
| Origem (Painel Esquerdo - Col 7) | Ação D-pad | Destino (Inventário Direito) | Retorno (D-pad Esquerda) |
| :--- | :--- | :--- | :--- |
| Baú Superior Linha 1 `('stash', 1, 7)` | **Direita** | `helmet` | Retorna para `('stash', 1, 7)` |
| Baú Superior Linha 2 `('stash', 2, 7)` | **Direita** | `gloves` | Retorna para `('stash', 2, 7)` |
| Baú Superior Linha 3 `('stash', 3, 7)` | **Direita** | `belt` | Retorna para `('stash', 3, 7)` |
| Baú Superior Linha 4 `('stash', 4, 7)` | **Direita** | `belt` | Retorna para `('stash', 3, 7)` |
| Baú Superior Linha 5 `('stash', 5, 7)` | **Direita** | `main_hand` | Retorna para `('stash', 5, 7)` |
| Baú Superior Linha 6 `('stash', 6, 7)` | **Direita** | `spell_1` | Retorna para `('stash', 6, 7)` |
| Pet Inferior Linha 1 `('pet', 1, 7)` | **Direita** | Inventário Grid Linha 1 `(1, 1)` | Retorna para `('pet', 1, 7)` |
| Pet Inferior Linha 2 `('pet', 2, 7)` | **Direita** | Inventário Grid Linha 2 `(2, 1)` | Retorna para `('pet', 2, 7)` |
| Pet Inferior Linha 3 `('pet', 3, 7)` | **Direita** | Inventário Grid Linha 3 `(3, 1)` | Retorna para `('pet', 3, 7)` |

#### 3. Regra da Opção 3 — Extremidades Externas Isoladas
* **Coluna 1 do Baú Superior (Esquerda):** Pressionar **D-pad Esquerda** realiza quebra de linha interna dentro do Baú:
  - `(1, 1) + Esquerda` $\to$ `(6, 7)`
  - `(row, 1) + Esquerda` $\to$ `(row - 1, 7)`
* **Coluna 1 do Pet Inferior (Esquerda):** Pressionar **D-pad Esquerda** realiza quebra de linha interna dentro do Pet:
  - `(1, 1) + Esquerda` $\to$ `(3, 7)`
  - `(row, 1) + Esquerda` $\to$ `(row - 1, 7)`
* **Coluna 7 do Inventário (Direita):** Pressionar **D-pad Direita** continua dando quebra de linha interna dentro do próprio Inventário (`(row, 7) + Direita` $\to$ `(row + 1, 1)`), mantendo a borda externa da direita 100% isolada e protegida contra pulos acidentais para a outra ponta da tela.

---

### Mapeamento de Comandos no Gamepad com o Baú Aberto
* **D-pad (Cima / Baixo / Esquerda / Direita):** Navegação slot-a-slot pelos 63 slots do lado esquerdo e 37 posições do lado direito, com travessia suave de tooltips (`_move_cursor_with_leave_step`).
* **L2 / R2 (Gatilhos):** 
  - Com o cursor na **metade esquerda** da tela: Troca entre as abas `Equipment` / `Spells` / `Fish` do Pet.
  - Com o cursor na **metade direita** da tela: Troca entre as abas do Inventário do Jogador.
* **X (A / Cross):** Clica no slot sob o cursor para selecionar / mover o item.
* **Quadrado (X / Square):** Equipa ou transfere o item diretamente entre os inventários.
* **Triângulo (Y / Triangle):** Envia o item para o Pet / Baú dependendo do contexto.
* **Círculo (B / Circle):** Fecha o menu ativo.
* **Analógico Esquerdo / Direito:** Modo mouse livre com sensibilidade acelerada sempre disponível caso o jogador deseje apontar manualmente para qualquer elemento fora do grid.


---

## Mapeamento de Pontos Navegáveis no Menu do Mercador (Vendedores / Lojas) no ESTADO = In-game
#### Meta - Navegação fluida e intuitiva pelas lojas de mercadores/ferreiros (grid 6x7 de 42 slots com 3 abas no topo) e pelo Inventário do Pet integrado na metade esquerda da tela (rect.left), com seleção de abas rosa via D-pad/Ação e pontes bidirecionais para o Inventário do Jogador na metade direita.

### Imagem de Referência
> `assets\images\inventário\mercador-4x3.png`

```
+-------------------------------------------------------------+-------------------------------------------------------------+
|                      PAINEL ESQUERDO                        |                       PAINEL DIREITO                        |
|                     (Mercador + Pet)                        |                    (Inventário do Jogador)                  |
+-------------------------------------------------------------+-------------------------------------------------------------+
|  [MERCADOR SUPERIOR: 3 Abas Rosa + 6 Linhas x 7 Colunas]    |  [EQUIPAMENTOS E MAGIAS: 16 Slots]                          |
|  Abas: [Misc (Rosa)] [Weapon (Rosa)] [Armor (Rosa)]         |  helmet                                                     |
|  L1: [1,1 (Amarelo)] [1,2] ... [1,6] [1,7 (Ponte)]     ---> |  gloves                                                     |
|  L2: [2,1]           [2,2] ... [2,6] [2,7 (Ponte)]     ---> |  belt                                                       |
|  L3: [3,1]           [3,2] ... [3,6] [3,7 (Ponte)]     ---> |  belt                                                       |
|  L4: [4,1]           [4,2] ... [4,6] [4,7 (Ponte)]     ---> |  main_hand                                                  |
|  L5: [5,1]           [5,2] ... [5,6] [5,7 (Ponte)]     ---> |  spell_1                                                    |
|  L6: [6,1]           [6,2] ... [6,6] [6,7 (Ponte)]     ---> |                                                             |
|           ^                   |                             |                                                             |
|   (D-pad Cima)         (D-pad Baixo)                        |                                                             |
|           |                   v                             |                                                             |
|  [PET INFERIOR: 3 Abas Ciano + 3 Linhas x 7 Colunas = 21]   |  [INVENTÁRIO INFERIOR: 3 Abas + 3 Linhas x 7 Colunas]       |
|  Abas: [Equip (Ciano)] [Spells (Ciano)] [Fish (Ciano)]      |  Abas: [Equipment] [Spells] [Fish]  (L2/R2)                 |
|  L1: [1,1] [1,2] ... [1,6] [1,7 (Ponte)]               ---> |  L1: [1,1] [1,2] ... [1,6] [1,7 (Wrap)]                     |
|  L2: [2,1] [2,2] ... [2,6] [2,7 (Ponte)]               ---> |  L2: [2,1] [2,2] ... [2,6] [2,7 (Wrap)]                     |
|  L3: [3,1] [3,2] ... [3,6] [3,7 (Ponte)]               ---> |  L3: [3,1] [3,2] ... [3,6] [3,7 (Wrap)]                     |
+-------------------------------------------------------------+-------------------------------------------------------------+
```

---

### Tabela de Cores e Funções no Overlay do Mercador
| Cor | Hex | Função / Significado | Quantidade no Mercador |
| :--- | :--- | :--- | :--- |
| **Rosa** | `#FD62CE` | Posição exata que o cursor navega para trocar de abas da loja (`Misc`, `Weapon`, `Armor`) | 3 abas (`merchant_tab_1..3`) |
| **Amarelo** | `#E6C12A` | Foco inicial ao abrir a loja ou após confirmar a troca de aba | 1 slot (`('merchant', 1, 1)`) |
| **Ciano** | `#0BE0EF` | Abas de navegação do Pet clicáveis via L2 / R2 | 3 abas (`pet_tab_1..3`) |
| **Verde** | `#09B200` | Slots regulares de navegação interna via D-pad | 53 slots (36 loja + 17 pet) |
| **Laranja** | `#FD6100` | Pontes centrais de transição inter-menus (Coluna 7) | 9 slots (6 loja + 3 pet) |

---

### Estrutura do Painel Esquerdo (Mercador)
1. **Seção Superior (Loja do Mercador):**
   - **3 Abas Rosa (`#FD62CE`):**
     - Aba 1 (`Misc`): `(88.0, 78.0)`
     - Aba 2 (`Weapon`): `(183.0, 78.0)`
     - Aba 3 (`Armor`): `(278.0, 78.0)`
   - **Grid de 6 linhas x 7 colunas (42 slots):**
     - Posição inicial (Amarelo): Slot `(1, 1)` em `(63.5, 109.5)`.
     - Colunas 1 a 7: `x = rect.left + (63.5 + (col - 1) * 40.0) * scale`.
     - Alturas base das 6 linhas (calibrado em 1024x768):
       - Linha 1: `109.5`
       - Linha 2: `164.5` (+55.0)
       - Linha 3: `219.5` (+55.0)
       - Linha 4: `277.5` (+58.0 - divisor intermediário)
       - Linha 5: `332.5` (+55.0)
       - Linha 6: `387.5` (+55.0)
2. **Seção Inferior (Pet Inventory integrado):**
   - 3 abas em Ciano (`#0BE0EF`): `Equipment`, `Spells`, `Fish` (controladas por L2/R2 na metade esquerda).
   - Grid de **3 linhas x 7 colunas** (total de **21 slots** do inventário do pet).

---

### Regras de Navegação no Mercador

#### 1. Navegação e Troca de Abas da Loja (Abas Rosa - Opção A)
* **Subir para as Abas:** Estando na **Linha 1 do Mercador** e pressionando **D-pad Cima**, o cursor sobe diretamente para o ponto rosa da **aba atualmente ativa** do mercador (`_merchant_tab`).
* **Navegação Horizontal entre Abas (com Wrap):** Estando sobre as abas rosa:
  - **D-pad Direita:** `Misc` $\to$ `Weapon` $\to$ `Armor` $\to$ `Misc` (wrap cíclico).
  - **D-pad Esquerda:** `Armor` $\to$ `Weapon` $\to$ `Misc` $\to$ `Armor` (wrap cíclico).
* **Descer das Abas sem Trocar:** Pressionar **D-pad Baixo** a partir de uma aba rosa desce o cursor para a Linha 1 do grid na respectiva coluna (Aba 1 $\to$ Col 1, Aba 2 $\to$ Col 4, Aba 3 $\to$ Col 7).
* **Confirmar Troca de Aba (Botão X / A):**
  - O cursor executa o clique com botão esquerdo sobre o ponto rosa da aba selecionada.
  - Atualiza a variável de controle `merchant_tab`.
  - **Teleporta o cursor imediatamente para o ponto amarelo (Linha 1, Coluna 1)** do grid do mercador.

#### 2. Navegação Vertical Contínua (Pet $\leftrightarrow$ Mercador Superior)
* **Pet para Mercador:** Estando na Linha 1 do Pet (`('pet', 1, col)`) e pressionando **D-pad Cima**, o cursor sobe para a Linha 6 do Mercador (`('merchant', 6, col)`), preservando a coluna.
* **Mercador para Pet:** Estando na Linha 6 do Mercador (`('merchant', 6, col)`) e pressionando **D-pad Baixo**, o cursor desce para a Linha 1 do Pet (`('pet', 1, col)`), preservando a coluna.
* **Bloqueio no Fundo:** Estando na Linha 3 do Pet Inferior e pressionando **D-pad Baixo**, o cursor permanece onde está.

#### 3. Tabela Mestra de Pontes Centrais (Coluna 7 $\leftrightarrow$ Inventário)
| Origem (Painel Esquerdo - Col 7) | Ação D-pad | Destino (Inventário Direito) | Retorno (D-pad Esquerda) |
| :--- | :--- | :--- | :--- |
| Mercador Superior Linha 1 `('merchant', 1, 7)` | **Direita** | `helmet` | Retorna para `('merchant', 1, 7)` |
| Mercador Superior Linha 2 `('merchant', 2, 7)` | **Direita** | `gloves` | Retorna para `('merchant', 2, 7)` |
| Mercador Superior Linha 3 `('merchant', 3, 7)` | **Direita** | `belt` | Retorna para `('merchant', 3, 7)` |
| Mercador Superior Linha 4 `('merchant', 4, 7)` | **Direita** | `belt` | Retorna para `('merchant', 3, 7)` |
| Mercador Superior Linha 5 `('merchant', 5, 7)` | **Direita** | `main_hand` | Retorna para `('merchant', 5, 7)` |
| Mercador Superior Linha 6 `('merchant', 6, 7)` | **Direita** | `spell_1` | Retorna para `('merchant', 6, 7)` |
| Pet Inferior Linha 1 `('pet', 1, 7)` | **Direita** | Inventário Grid Linha 1 `(1, 1)` | Retorna para `('pet', 1, 7)` |
| Pet Inferior Linha 2 `('pet', 2, 7)` | **Direita** | Inventário Grid Linha 2 `(2, 1)` | Retorna para `('pet', 2, 7)` |
| Pet Inferior Linha 3 `('pet', 3, 7)` | **Direita** | Inventário Grid Linha 3 `(3, 1)` | Retorna para `('pet', 3, 7)` |

#### 4. Regra da Opção 3 — Extremidades Externas Isoladas
* **Coluna 1 do Mercador Superior (Esquerda):** Pressionar **D-pad Esquerda** realiza quebra de linha interna dentro do Mercador:
  - `(1, 1) + Esquerda` $\to$ `(6, 7)`
  - `(row, 1) + Esquerda` $\to$ `(row - 1, 7)`
* **Coluna 1 do Pet Inferior (Esquerda):** Pressionar **D-pad Esquerda** realiza quebra de linha interna dentro do Pet:
  - `(1, 1) + Esquerda` $\to$ `(3, 7)`
  - `(row, 1) + Esquerda` $\to$ `(row - 1, 7)`
* **Coluna 7 do Inventário (Direita):** Pressionar **D-pad Direita** continua dando quebra de linha interna dentro do próprio Inventário (`(row, 7) + Direita` $\to$ `(row + 1, 1)`), mantendo a borda externa da direita 100% isolada.

---

### NPCs Mercadores com Interface Padrão de Loja (6x7 + 3 Abas Rosa + Pet)
O TorchBridge lê o nome do NPC ativo em tempo real diretamente da memória interna do jogo (`p_merchant + 0x28` $\to$ `+0x34` da janela CEGUI), definindo automaticamente a aba padrão ao abrir a loja:

| NPC | Nome na Memória | Aba Default ao Abrir | Índice da Aba |
| :--- | :--- | :--- | :--- |
| **KOLOS BLACKSMITH** | `"Kolos the Smith"` | `WEAPONS` | Aba 2 |
| **DUROS THE BLADE** | `"Duros the Blade"` | `WEAPONS` | Aba 2 |
| **TARN THE MERCHANT** | `"Tarn the Merchant"` | `MISC` | Aba 1 |
| **TRIYA** | `"Triya the Gem Seller"` / `"Triya"` | `MISC` | Aba 1 |

---

## Interfaces de Crafting (Painel Esquerdo Suspenso)

Ao interagir com NPCs de crafting, o jogo abre um painel de madeira suspenso à esquerda e o Inventário do Jogador à direita. Diferente dos mercadores e do baú, essas interfaces não possuem abas no painel esquerdo nem o grid do Pet na parte inferior.

```
+-----------------------------------------------------------------------------------+
|               PAINEL ESQUERDO                     |      INVENTÁRIO DO JOGADOR    |
|                                                   |                               |
|   [ GOREN / GORN / FURL ]    [ DURAN THE TRANSMUTER ]    [ Equipamentos / Spells ]|
|                                                   |                               |
|         +-----------+          +-----+ +-----+    |    [Cap] [Arm] [Luvas] [Bota] |
|         |  SLOT 1   |          | S 1 | | S 2 |    |    [Colar] [Anel1] [Anel2]    |
|         |  (Ciano)  |          +-----+ +-----+    |    [Arma 1] [Arma 2]          |
|         +-----------+          | S 3 | | S 4 |    |                               |
|                                +-----+ +-----+    |    [========================] |
|         +-----------+          +-----------+      |    |        GRID 3x7        | |
|         |  FECHAR   |          |  FECHAR   |      |    |  (Item Slots 1 a 21)   | |
|         +-----------+          +-----------+      |    +------------------------+ |
|         | AÇÃO NPC  |          | TRANSMUTAR|      |                               |
|         +-----------+          +-----------+      |                               |
+-----------------------------------------------------------------------------------+
```

---

### 1. GOREN (Encantador), GORN e FURL (Sockets)

Compartilham a mesma interface de slot único central para inserir o item (`CEnchantMenu` em `p_ui + 0x02DC`):
* **GOREN THE ENCHANTER:** Modo `0x15` / `0x16` na memória $\to$ botão de ação `"ENCANTAR"`.
* **GORN e FURL (Sockets):** Modos `0x19`, `0x1A`, `0x1B` na memória $\to$ botão de ação `"RECUPERAR"`.

#### Coordenadas dos Elementos (Base 1024x768)
| Elemento | Identificador | Coordenadas (X, Y) | Dimensões no Overlay | Cor Padrão |
| :--- | :--- | :--- | :--- | :--- |
| **Slot de Item** | `slot_0` | `(240.0, 314.0)` | `96x96` | Ciano (`#6FD2EB`), Amarelo quando focado |
| **Botão Fechar** | `decline` | `(240.0, 402.0)` | `128x24` | Laranja (`#FF9F43`), Amarelo quando focado |
| **Botão de Ação** | `action` | `(240.0, 447.0)` | `128x24` | Laranja (`#FF9F43`), Amarelo quando focado |

#### Esquema de Navegação via D-pad
* **Foco Inicial:** Abre automaticamente sobre o **Slot de Item** `slot_0`.
* **Navegação Vertical:**
  - `slot_0 + Baixo` $\to$ Botão `decline` ("FECHAR")
  - `decline + Baixo` $\to$ Botão `action` ("ENCANTAR" / "RECUPERAR")
  - `action + Cima` $\to$ Botão `decline` ("FECHAR")
  - `decline + Cima` $\to$ `slot_0`
* **Ponte para o Inventário (Direita):**
  - `slot_0 + Direita` $\to$ Inventário Grid Linha 1 `(1, 1)`
  - `decline + Direita` $\to$ Inventário Grid Linha 2 `(2, 1)`
  - `action + Direita` $\to$ Inventário Grid Linha 3 `(3, 1)`
* **Ponte do Inventário de Volta para o Crafting (Esquerda):**
  - Pressionar **D-pad Esquerda** na Coluna 1 do inventário ou nos equipamentos da borda esquerda (`helmet`, `gloves`, `belt`, `main_hand`, `spell_1`) retorna o cursor para o elemento de crafting na mesma altura.

---

### 2. DURAN (The Transmuter / Transmutador)

Interface de combinação de 4 itens (`CCombineMenu` em `p_ui + 0x02E0`), estruturada em um **Grid 2x2** com dois botões abaixo:

#### Coordenadas dos Elementos (Base 1024x768)
| Elemento | Posição no Grid 2x2 | Identificador | Coordenadas (X, Y) | Dimensões | Cor Padrão |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Slot 1** | Topo - Esquerda | `slot_0` | `(216.0, 266.0)` | `48x68` | Ciano, Amarelo quando focado |
| **Slot 2** | Topo - Direita | `slot_1` | `(268.0, 266.0)` | `48x68` | Ciano, Amarelo quando focado |
| **Slot 3** | Baixo - Esquerda | `slot_2` | `(216.0, 339.0)` | `48x68` | Ciano, Amarelo quando focado |
| **Slot 4** | Baixo - Direita | `slot_3` | `(268.0, 339.0)` | `48x68` | Ciano, Amarelo quando focado |
| **Botão Fechar** | Abaixo dos slots | `decline` | `(240.0, 405.0)` | `128x24` | Laranja, Amarelo quando focado |
| **Botão Transmutar** | Inferior | `action` | `(240.0, 450.0)` | `128x24` | Laranja, Amarelo quando focado |

#### Esquema de Navegação via D-pad
* **Foco Inicial:** Abre automaticamente sobre o **Slot 1** (`slot_0`, topo-esquerda).
* **Navegação no Grid 2x2:**
  - `slot_0 + Direita` $\to$ `slot_1` | `slot_0 + Baixo` $\to$ `slot_2`
  - `slot_1 + Esquerda` $\to$ `slot_0` | `slot_1 + Baixo` $\to$ `slot_3`
  - `slot_2 + Cima` $\to$ `slot_0` | `slot_2 + Direita` $\to$ `slot_3` | `slot_2 + Baixo` $\to$ `decline`
  - `slot_3 + Cima` $\to$ `slot_1` | `slot_3 + Esquerda` $\to$ `slot_2` | `slot_3 + Baixo` $\to$ `decline`
* **Navegação nos Botões:**
  - `decline + Cima` $\to$ Retorna para `slot_2`
  - `decline + Baixo` $\to$ Botão `action` ("TRANSMUTAR")
  - `action + Cima` $\to$ Botão `decline` ("FECHAR")
* **Ponte para o Inventário (Direita):**
  - Pressionar **D-pad Direita** na coluna direita do crafting (`slot_1`, `slot_3`, `decline`, `action`) pula diretamente para o Inventário do Jogador:
    - `slot_1 + Direita` $\to$ Inventário Grid Linha 1 `(1, 1)`
    - `slot_3 + Direita` $\to$ Inventário Grid Linha 2 `(2, 1)`
    - `decline + Direita` $\to$ Inventário Grid Linha 2 `(2, 1)`
    - `action + Direita` $\to$ Inventário Grid Linha 3 `(3, 1)`
* **Ponte do Inventário para o Transmutador (Esquerda):**
  - `(1, 1) + Esquerda` ou `helmet / gloves + Esquerda` $\to$ `slot_1` (topo-direita)
  - `(2, 1) + Esquerda` ou `belt + Esquerda` $\to$ `slot_3` (baixo-direita)
  - `(3, 1) + Esquerda` ou `main_hand / spell_1 + Esquerda` $\to$ `decline` / `action`

---

### 3. Atalhos L2 e R2 nas Telas de Crafting
Como os painéis de crafting não possuem abas próprias:
* Pressionar **L2** ou **R2** em qualquer momento enquanto a tela de crafting estiver aberta **troca automaticamente as abas do Inventário do Jogador à direita** (`Misc` $\leftrightarrow$ `Weapons` $\leftrightarrow$ `Armor`), clicando na aba e devolvendo o cursor instantaneamente para o elemento de crafting ativo.
* **Gatilhos e Combos Suprimidos:** Combos de habilidades (como RT/LT tocando skills de combate) ficam 100% bloqueados no painel esquerdo para evitar acionamentos acidentais.
