# [TB-16] - Adicionar informações extras no menu radial.
## Na abertura do menu radial devemos
- Mostrar mais informações sobre qual menu selecionado com o nalogico e tambem como o menu radial funciona

- Serão dois lugares em que as informações deverão aparecer cnetralizados horizontalmente na tela.
- Precisamos criar uma área acima do menu radial onde as informações do menu selecionado irá aparecer com um offset do menu radial de 30px.
`assets\hud\menu radial\raidal-menu-info-A.png`
`assets\hud\menu radial\raidal-menu-info-C.png`
`assets\hud\menu radial\raidal-menu-info-I.png`
`assets\hud\menu radial\raidal-menu-info-J.png`
`assets\hud\menu radial\raidal-menu-info-P-agressive.png`
`assets\hud\menu radial\raidal-menu-info-P-defensive.png`
`assets\hud\menu radial\raidal-menu-info-P-passive.png`
`assets\hud\menu radial\raidal-menu-info-P-sell.png`
`assets\hud\menu radial\raidal-menu-info-P.png`
`assets\hud\menu radial\raidal-menu-info-Q.png`
`assets\hud\menu radial\raidal-menu-info-S.png`
`assets\hud\menu radial\raidal-menu-info-Shortcuts.png`

- Precisamos criar uma área abaixo do menu radial com um offset de 80px, nessa área abaixo vai ser mostrada uma das 3 imagens com base no controle conectado
`assets\hud\menu radial\menu-radial-instructions-nintendo.png`
`assets\hud\menu radial\menu-radial-instructions-ps.png`
`assets\hud\menu radial\menu-radial-instructions-xbox.png`

- Fazer um efeito de animação de entrada e saida com fade e scale

## Fluxo
1 - ao abrir o menu radial deve mostrar o menu radial em tela como sempre fez, eas informações na parte inferior do menu radial(uma das tres imagens de instructions baseada no controle conectado)
2 - ao mover o analogico para alguma opção deve ser mostrada a imagem na area acima do menu radial, correspondente a opção selecionada, co um efeito de entrada com fade e scale
3 - com a imagem na parte superior do menu radial sendo mostrada se eu mudar a opção com o analogico, a imagem da opção correspondente deve ser mostrada fazendo efeito de fade somente sem scale, enquanto a imagem da opção anterior some em fade a nova aparece em fade
4 - caso estejamos com uma opção selecionada com o analogico e pressionemos o botao leste para cancelar a selecao, a animação de saida da imagem que fica na aprte superior do menu radial deve ser realizada com fade e scale

## Exemplos de como imagino que deva ficar em tela:
`assets\hud\menu radial\ex-menu-radial-aberto-default.png`
`assets\hud\menu radial\ex-menu-radial-aberto-opcao-selecionada.png`
`assets\hud\menu radial\ex-menu-radial-aberto-submenu-selecionado.png`