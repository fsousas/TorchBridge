# Mapeamento de abas dos menus

## Existem 3 menus que quando abertos mostram abas: 

- ### menu de inventario
    Equipment  |  Spells  |  Fish
    > assets\menus\Inventario-player.png
- ### menu de pet
    Equipment  |  Spells  |  Fish
    > assets\menus\pet-player.png
    
## importante
> As abas de Equipment, Spells e Fish do menu de inventario e pet tem a mesma quantidade de slots na mesma disposiçao
7x3 - totalizando 21 slots por aba

> Ja o menu de habilidades sempre terá 6 linhas em cada aba, poré a disposiçao das habilidades muda dependendo da classe e da aba de habilidade selecionada

> quando um desses menus estiver aberto quero poder navegar entre as abas usando o L2 e R2 no menu em que o mouse estiver navegando, ao abrir um menu o mouse sempre vai pro primeiro slot do ultimo menu aberto. Vamos trabalhar com sistema de pseudo foco, no caso sempre que um menu que tenha slots para ser selecionado for aberto,o jogador consegue usar o dpad para navegar entre os slots do inventario, se ele estiver no limite da linha do inventario de pet e o inventario do player estiver aberto, ao pressionar mais uma vez para a direita ele deve mudar para o primeiro slot do inventario do player.

 [pet aberto]                 |  [inventario aberto]
 Equipment | spells | Fish    |  Equipment | spells | Fish   
 [ ] [ ] [ ] [ ] [ ] [ ] [x]  |  [ ] [ ] [ ] [ ] [ ] [ ] [ ] 
 [ ] [ ] [ ] [ ] [ ] [ ] [ ]  |  [ ] [ ] [ ] [ ] [ ] [ ] [ ] 
 [ ] [ ] [ ] [ ] [ ] [ ] [ ]  |  [ ] [ ] [ ] [ ] [ ] [ ] [ ]

OBS o x marca o local do mouse
se eu pressionar R2 ou L2 com o mouse on de marca na representaçao acima as abas de Equipment, spells e fish do lado do pet devem ser alternadas, o mouse permanece no mesmo local, o mesmo vale para o lado do inventario

> Ex: abri o menu de inventario, o mouse vai pro primeiro slot do Equipment, se eu abrir o menu de pet estando com o menu de inventario aberto, o mouse vai pro primeiro slot do pet que também é da aba de Equipment mas do lado do pet.

> Ex: se o inventario(I) estiver aberto, ao apressionar o R2 o menu deve mudar para a aba "Spells", ao apressionar L2 deve voltar para a aba "Equipment". o mesmo vale para a aba de pet


- ### menu de skills
    >varia de acordo com o personagem que o jogador estiver usando
    
    ```
    [Destroyer]:
    1 - assets\menus\skilltrees\destroyer\1-Berserker.png
    2 - assets\menus\skilltrees\destroyer\2-Titan.png
    3 - assets\menus\skilltrees\destroyer\3-Spectral.png
    ```
    ```
    [Vanquisher]:
    1 - assets\menus\skilltrees\vanquisher\1-Marksman.png
    2 - assets\menus\skilltrees\vanquisher\2-Rogue.png
    3 - assets\menus\skilltrees\vanquisher\3-Arbitrer.png
    ```
    ```
    [Alchemist]:
    1 - assets\menus\skilltrees\anchemist\1-Arcane.png
    2 - assets\menus\skilltrees\anchemist\2-Lore.png
    3 - assets\menus\skilltrees\anchemist\3-Battle.png
    ```
## importante
Existe um padrao nas abas de habilidades, em todas elas sempre existe uma abilidade na primeira linha que fica no meio
o grid das habilidades se resume nessa representaçao:

[aba 1] [aba 2] [aba 3]
[ ] [X] [ ]
[ ] [ ] [ ]
[ ] [ ] [ ]
[ ] [ ] [ ]
[ ] [ ] [ ]
[ ] [ ] [ ]
OBS o x marca a posiçao inicial do mouse sempre que o  menu de habilidades for aberto ou for trocada a aba de habilidades

> O jogador só pode navegar para um slot que seja possível acessar.

Ex: abri o menu de habilidades
Legenda
X - posiçao inicial do mouse (sempre tem uma skill onde o mouse é posicionado no primeiro momento)
S - slot de skill
[aba 1] [aba 2] [aba 3]
[S] [X] [ ]
[ ] [S] [S]
[S] [S] [S]
[ ] [S] [ ]
[ ] [ ] [S]
[ ] [S] [ ]
NO exemplo acima, se o jogador pressionar o dpad para a direita nao o mouse nao vai se mover pois para a rideira nao tem uma habilidade naquele slot ele está vazio
vamos chamar de L pra linha e C pra coluna
se ele estiver na L4C1 ou L4C2 e pressionar para baixo ele vai ser posicionado na L5C3 pois na linha 5 a unica coluna que tem skill é a 3

Nos prints das paginas de skill tree é possível ver a disposiçao de cada askill em cada aba de cada personagem assim a gente consegue rastrear melhor como posicionar o mouse no local correto

se eu estiver no L3C1 estando na primeira aba e pressionar  L2 eu quero mudar para a ultima aba e o mouse vai para L1C2, sempre que eu trocar de aba com o foco no menu de habilidades,o mouse deve para L1C2