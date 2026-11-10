# Movimento seguro e interação explícita — TB-18

O analógico esquerdo usa destinos e parada na navegação do próprio Torchlight.
Ele não mantém clique esquerdo nem desloca o cursor. A câmera orienta a direção,
e o jogo continua responsável por caminhos, obstáculos e habilidades.

## Ativação

O módulo Windows x86 necessário já está incluído em assets/native/x86/winmm.dll.
Ele funciona no Windows e no processo PE32 do jogo sob Proton. Não é necessário
instalar compilador para usar o aplicativo.

1. Feche o Torchlight.
2. No menu do ícone TB, escolha **Instalar movimento seguro...** e selecione
   Torchlight.exe. Também é possível usar o comando abaixo.
3. Reinicie o jogo. No Omarchy, inicie pelo modo **--launch** do TorchBridge,
   como descrito em [LINUX.md](LINUX.md). O launcher preserva os overrides Wine
   existentes e acrescenta winmm=n,b ao ambiente somente desse lançamento.

~~~sh
python -m torchbridge.native_input_setup install "/caminho/Torchlight.exe"
~~~

O instalador acrescenta winmm.dll e .torchbridge-input.json. Não altera o arquivo
Torchlight.exe, saves ou configurações do desktop. Recusa substituir proxies de
outros mods. A remoção pelo mesmo menu ou pelo comando abaixo confere o hash da
instalação antes de remover arquivos.

~~~sh
python -m torchbridge.native_input_setup remove "/caminho/Torchlight.exe"
~~~

Sem o módulo reconhecido, a caminhada fica suspensa e a calibração informa o
motivo. Não existe retorno automático ao clique de caminhada. O módulo D3D9 de
fullscreen continua independente e opcional.

## Controle e alvo

- O analógico esquerdo anda; voltar ao centro pede parada.
- O alvo é o elemento utilizável mais próximo dentro do raio configurado,
  respeitando a diferença de altura de até 2,5 unidades. Empates usam endereço
  estável. Categoria, câmera, direção e posição na tela não favorecem outro alvo.
- O método de highlight do próprio jogo destaca esse alvo sem mover o cursor.
  O aviso do overlay acompanha o alvo reconhecido pelo módulo.
- **D-pad ↑** envia uma ação explícita. O módulo escolhe novamente pelas posições
  atuais e valida jogador, cenário, alcance e disponibilidade ao executar.
  Segurar o botão ou reconectar o canal não repete uma ação antiga.
- A/Cruz mantém o modificador de ataque no overworld, inclusive sobre NPCs.
  Um ataque explícito pode posicionar a mira na direção da caminhada; a
  caminhada sozinha não o faz. O analógico direito continua permitindo mira livre.
- Menus suspendem caminhada e highlight. O modo cursor mantém seus cliques
  explícitos; eles não são gerados pela aproximação do personagem.

## Famílias de interação

O mapeamento usa UNITTYPE, RTTI e o dispatch virtual do jogo. O nome serve para
apresentação e refinamento de categorias; um nome desconhecido não exclui uma
classe interativa reconhecida.

| Família | Identificação | Execução |
| --- | --- | --- |
| NPCs e missões | Personagem interativo vivo, tags de missão | Estado nativo de conversar |
| Mercadores e apostadores | UNITTYPE 41 / 127 | Conversa/serviço original |
| Encantador, transmutador e gemas | 130 / 134 / 132 / 133 | Serviço original |
| Baú pessoal e compartilhado | 128 / 170 | Serviço original |
| Aposentadoria | 175 | Conversa original |
| Portas, alavancas e baús de cenário | CTriggerUnit, inclusive subclasses | Uso original e requisitos do objeto |
| Pesca | UNITTYPE 122 | Interface original de pesca |
| Fontes e santuários | 157 / 158 / 159 e props reconhecidos | Efeito original |
| Portais e waypoints | 43 / 165 / 173 / 171 e props reconhecidos | Uso original com transição autorizada |
| Itens, equipamentos e ouro | CItem e subclasses; ouro 34 | Coleta original |
| Destrutíveis | CBreakable e subclasses | Dispatch original; combate continua disponível |
| Outros objetos utilizáveis | Subclasse interativa com dispatch reconhecido | Categoria genérica e método original |

A seleção não ativa objetos. Os limites de alvo/uso e a ativação direta de props
são protegidos para impedir que uma rotina de proximidade contorne o D-pad no
modo direto. A ação lógica CWarper exige um dispatch autorizado de interação.
Volumes de spawn, dano e objetivos não são desativados globalmente: eles fazem
parte do funcionamento do cenário, e não da escolha de um objeto para usar.

## Calibração e diagnóstico

O modo de calibração mostra os marcadores e coordenadas da TB-18 e acrescenta:

- estado do movimento seguro e disponibilidade do módulo;
- direção e destino em coordenadas do mundo;
- estado do highlight;
- contadores de usos e transições bloqueados.

O leitor/CLI de cenário continua somente leitura. O JSON acrescenta unit_type e
interaction_method a cada elemento. O controlador usa um canal local separado,
com token descoberto na memória do processo selecionado, versão, sequência e
validade curta. Mudança de foco/processo/cenário, desconexão ou falta de renovação
cancela o movimento e remove o destaque. Um catálogo nativo incompleto não autoriza uso. O catálogo externo é telemetria;
a seleção e a validação autoritativas são feitas na thread do jogo.

## Build, testes e limites de validação

As rotinas têm perfis Steam/GOG e checagens de layout. Executáveis ou métodos de
mods sem assinatura reconhecida são recusados; não são chamados endereços por
suposição. As implementações de terceiros foram usadas como referência de fatos
de engenharia reversa; o controlador foi implementado no projeto. MinHook é uma
dependência BSD-2-Clause, com licença incluída no repositório e no pacote.

O CI compila o módulo com MSVC x86, testa protocolo/seleção/reconexão e verifica
carregamento e forwarding tanto do binário gerado quanto do distribuído. A suíte
Python valida o transporte TCP real, cancelamentos, seleção, classes derivadas,
instalação/remoção e renderização em Windows/Linux com Python 3.11/3.13.

No Omarchy/GE-Proton11-12, uma cópia isolada do jogo confirmou o carregamento do
módulo, a descoberta por ASLR, a seleção de um portal mais próximo que os NPCs,
o highlight e dois segundos sem interação por presença. O portal só iniciou a
transição após a ordem explícita. Esses ensaios não equivalem a percorrer todas
as categorias com controle físico. A cobertura de código e a recusa de layouts
não reconhecidos são distintas da homologação manual de cada build/mod.

Detalhes do módulo e build: [native/input/README.md](../native/input/README.md).
Histórico de pesquisa: [CONCEITO-MOVIMENTO-CONSOLE.md](CONCEITO-MOVIMENTO-CONSOLE.md).
