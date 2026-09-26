# Informaçoes de calibration
##### A tela de configuraçoes aparece em dois momentos do jogo, na tela de inicio de jogo e durante a gameplay atraves do menu de pausa mas o ESTADO e o MENUS sao os mesmos nos dois casos
- ESTADO: CONFIGURAÇÕES (SETTINGS)
- MENUS: Configurações

## Tela inicial de configuraçoes
assets\images\sreensXcursor\settings\CONFIGURACOES - settings.png

## Dropdowns abertos
assets\images\sreensXcursor\settings\CONFIGURACOES - shadows.png
assets\images\sreensXcursor\settings\CONFIGURACOES - resolution.png
assets\images\sreensXcursor\settings\CONFIGURACOES - particle deteil.png

## cores

verde: #09B200
amarelo: #E6C12A
rosa: #B2007C
roxo: #5600B2
ciano: #00C7D5

> verde: sao os pontos navegaveis

> amarelo: sao os pontos de deslocamento padrao do cursor

> rosa: sao o pontos de dropdown(em que abre um menu de selecao de lista)

> roxo: sao os sliders de som baseado no nivel de volume salvo

> ciano: sao os limites de deslocamento x que o cursor pode ter quando estiver sobre um ponto roxo

### OBS
O marcador roxo funciona com uma açao de clique um pouco diferente, quando o cursor esta sobre ele e aperto X/A ele deve entender que eu estou segurando o clique esquerdo do mouse, e quando eu aperto O/B ele deve entender que eu estou soltando o clique esquerdo do mouse, e liberando o cursor pra navegar pelos pontos verdes

### OBS2
quando eu abrir um dropdown(rosa)como em:
assets\images\sreensXcursor\settings\CONFIGURACOES - shadows.png
assets\images\sreensXcursor\settings\CONFIGURACOES - resolution.png
assets\images\sreensXcursor\settings\CONFIGURACOES - particle deteil.png
o cursor deve se posicionar o ponto amarelo dessas telas respectivamente, e quando eu pressionar X/A em uma das opcoes, ele deve clicar nela e voltar para a tela de configuracoes na opçao rosa em que ele estava antes de abrir o dropdown, o mesmo vale para quando eu apertar O/B para fechar o dropdown ele deve se posicionar no ponto rosa e realziar o clique, que isso vai fazer o dropdown aberto ser fechado
