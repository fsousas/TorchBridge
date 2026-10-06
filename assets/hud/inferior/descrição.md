# Torchlight HUD Inferior para controles

O hud deve ser mantido sobre o jogo de forma que o ponto referencial seja o ponto centro inferior da janela do jogo.
Dependendo o controle conectado deve ser aplicado o hud referente ao controle.

## O que fazer
1. Detectar o controle conectado
2. Aplicar o hud referente ao controle

## Layouts
### Xbox Controller
assets\hud\inferior\hud-xbox.png
### PlayStation Controller
assets\hud\inferior\hud-playstation.png
### Nintendo Switch Pro Controller
assets\hud\inferior\hud-nitendo.png


## OBS
- Deve-se atentar para o fato de que a imagem da hud deve acompanhar o redimensionamento da janela baseado na altura (com redução de 27% em relação à proporção nativa da imagem para encaixe ideal sobre a barra de habilidades).
- A imagem deve ficar centralizada no eixo X e no eixo Y deve ficar na parte inferior da janela - 1.5% da altura da janela.

## Regras para o HUD
- A HUD deve ser aplicada de forma absoluta enquanto o ESTADO for igual a EM JOGO (inclusive no menu de Pause em jogo)
- A hud nao deve ser aplicada em: DIALOG, QUEST, TITLE MENU, CHARACTER SELECT, CUTSCENES, CHARACTER CREATE, LOADING SCREEN, OPTIONS SCREEN
- obs podemos realizar ajustes em telas especificas conforme a necessidade de mostrar ou nao o hud