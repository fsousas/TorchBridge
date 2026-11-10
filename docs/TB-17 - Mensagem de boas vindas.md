# [TB-17] - Mensagem de Boas-Vindas (Tutorial / Onboarding)

Especificação da tela de boas-vindas e tutorial introdutório do TorchBridge, apresentando o funcionamento do overlay ao usuário.

---

## 1. Visão Geral e Comportamento Inicial

Ao abrir o jogo pela primeira vez na tela inicial (ou caso o jogo já esteja em execução e o jogador instale e abra o TorchBridge):

1. **Disparo Automático:** A tela de boas-vindas deve ser exibida automaticamente.
2. **Persistência (`perfil.json`):**
   - Adicionar a propriedade `"show-welcome"` nas configurações do `perfil.json`.
   - Valor inicial pós-instalação: `1`.
   - Quando `show-welcome == 1`, a mensagem é exibida obrigatoriamente.
   - Ao alcançar a última página e clicar no botão **Fechar**, o valor de `"show-welcome"` deve ser atualizado para `0`.
3. **Obrigatoriedade na 1ª Execução:**
   - O jogador **não pode** fechar ou pular o tutorial na primeira vez. Ele é obrigado a passar por todas as páginas para entender o funcionamento do overlay.

---

## 2. Exibição e Carrossel de Imagens

- **Carregamento Dinâmico:** As telas são sequenciais e baseadas nos arquivos presentes em:
  `assets\hud\boas-vindas\Telas\` (ex: `1.png`, `2.png`, `3.png`, ...).
  - O total de páginas deve ser detectado dinamicamente pela quantidade de imagens na pasta.
- **Posicionamento:** A imagem de cada tela deve ser renderizada estritamente centralizada na tela (horizontal e verticalmente).
- **Área de Ações:** O rodapé da imagem (cantos inferiores esquerdo e direito) é reservado para os botões de ação e navegação.

---

## 3. Botões e Regras de Navegação

### 3.1. Distribuição dos Botões por Página
- **Primeira página:**
  - Apenas o botão **Próximo** no canto inferior direito.
- **Páginas intermediárias:**
  - Botão **Anterior** no canto inferior esquerdo.
  - Botão **Próximo** no canto inferior direito.
- **Última página:**
  - Botão **Anterior** no canto inferior esquerdo.
  - Botão **Fechar** no canto inferior direito.

### 3.2. Variação por Controle e Estados Visuais
Os botões devem refletir os glifos do controle atualmente conectado:
- `assets\hud\boas-vindas\bototes\Nintendo\`
- `assets\hud\boas-vindas\bototes\Playstation\`
- `assets\hud\boas-vindas\bototes\XBox\`

Cada botão possui duas variações de textura:
- **Normal:** exibido por padrão (ex: `btn-proximo.png`).
- **Ativo:** exibido quando o cursor/foco do D-pad estiver sobre ele (ex: `btn-proximo-ativo.png`).

---

## 4. Reabertura Manual (Menu Radial)

Quando o jogador já tiver concluído o tutorial inicial (`show-welcome == 0`), a mensagem pode ser consultada novamente a qualquer momento:

1. **Banner Informativo:**
   - Ao segurar o botão do Menu Radial (`L1` no PlayStation, `LB` no Xbox ou `L` no Nintendo Switch), exibe-se no topo central da tela (sem offset vertical) a imagem correspondente ao controle:
     - `assets\hud\boas-vindas\radial-info-nintendo.png`
     - `assets\hud\boas-vindas\radial-info-playstation.png`
     - `assets\hud\boas-vindas\radial-info-xbox.png`
   - O banner deve conter animação de **slide-in** ao segurar o botão do radial e **slide-out** ao soltá-lo.
2. **Disparo da Tela:**
   - Ao pressionar o **Botão Norte** do controle ($\Delta$ no PS, `Y` no Xbox, `X` no Switch) enquanto segura o menu radial, o tutorial é reaberto.
3. **Modo Opcional (Permissão para Fechar):**
   - Ao ser reaberto pelo menu radial, surge um botão de **Fechar ("X")** no canto superior direito da janela:
     - `assets\hud\boas-vindas\bototes\btn-x.png`
     - `assets\hud\boas-vindas\bototes\btn-x-ativo.png`
   - Pode ser fechado a qualquer momento:
     - Navegando com o D-pad até o "X" e confirmando.
     - Pressionando o botão de cancelamento/voltar (Botão Leste no PS e Xbox / Botão Sul no Switch).
     - Pressionando o botão **Start**.

---

## 5. Controle de Inputs e Bloqueio de Comandos (Modal Lock)

> [!IMPORTANT]
> **Isolamento de Entrada:** Enquanto a tela de boas-vindas estiver aberta, **nenhum comando deve vazar** para as camadas de baixo (jogo, HUD de fundo ou menus). 

Apenas os seguintes inputs devem ser aceitos e processados pela tela:
- **D-Pad (Direcional):** Navegação entre as ações/botões da página.
- **Botão Sul:** Ação / Confirmação (interage com o botão que estiver em foco).
- **Botão Leste:** Voltar / Cancelar (fecha a tela de boas-vindas se já não for a primeira execução obrigatória).
- **Start:** Mesmo efeito do Botão Leste (fecha a tela de boas-vindas quando o fechamento for permitido, ou seja, da segunda vez em diante).
- **Todos os demais botões e eixos analógicos:** Devem ser completamente bloqueados e consumidos, garantindo que nada ocorra em background.

---

## 6. Referências e Exemplos de Layout

Mockups visuais de referência estão disponíveis em:
- `assets\hud\boas-vindas\exemplo pagina 1.png`
- `assets\hud\boas-vindas\exemplo pagina 2.png`
- `assets\hud\boas-vindas\exemplo pagina 3.png`
