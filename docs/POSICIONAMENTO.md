# TB-18 — posicionamento e interação por proximidade

Branch: `feature/tb-18`.

O leitor publica a posição do jogador e a lista de elementos interativos ativos
do cenário carregado: NPCs (incluindo mercadores e seus estados de missão),
portais, escadas, fontes de vida/mana/melhoria,
portas, alavancas e locais de pesca. Baús também são reconhecidos. Cada elemento
contém endereço da instância, categoria, nome, identificador e posição X/Y/altura.
Props sem nome reconhecido permanecem como `interactive`, sem inventar categoria.

## Uso no controle

Em movimento direto, o elemento utilizável mais próximo recebe o highlight do
próprio jogo sem deslocar o cursor. O overlay mostra seu nome, distância e uma
imagem do botão para Xbox, PlayStation ou Nintendo. Itens, equipamentos e ouro
no chão (`loot`/`gold`) usam **A no Xbox/Nintendo** e **× no PlayStation**, com
`interact-*.png`. NPCs, baús, portas, escadas e outros objetos usam **D-pad ↑**,
com `dpad-up-*.png`. As seis imagens ficam em `assets/hud/general` e substituem
somente a indicação do botão; os demais textos permanecem no aviso.

A família visual segue `overlay.controller_layout` ou o controle detectado,
como o restante da HUD. No Nintendo, o A físico é o botão lógico `b` do SDL;
a coleta o consome antes da habilidade comum. A coleta não envia ataque,
Shift ou clique no chão, e exige liberação do botão antes de uma nova ação.
O módulo nativo confere também a família da ação: se o alvo mais próximo mudar
entre item, NPC/prop e destrutível, a ordem é recusada sem usar outro tipo de
objeto. A seleção continua estritamente por proximidade. Segurar não repete.

CBreakable e subclasses (barris comuns/explosivos e outros destrutíveis) usam
**A no Xbox/Nintendo** e **× no PlayStation**, com o ícone `interact-*.png`,
e recebem um ataque básico mantendo posição. O D-pad não aciona destrutíveis.
O módulo cancela o caminho e preserva o estado parado; não entra no estado de
aproximar/coletar. Alcance da arma, obstáculos e disponibilidade do ataque são
verificados pelo jogo. Fora de alcance, o personagem permanece parado.

A caminhada é independente de cliques. O módulo confere novamente jogador,
cenário, disponibilidade e distância ao executar; projeção, categoria ou
posição na tela não fazem um objeto mais distante tomar o lugar do mais próximo.
Os métodos originais preservam requisitos de missão, chaves, colisões e serviços.
Menus, combos, dados incompletos, carregamento e perda de foco suspendem a ação.

Instalação, famílias adicionais e proteção de ativação/transições:
[MOVIMENTO-SEGURO.md](MOVIMENTO-SEGURO.md).

## Configuração

Perfis antigos recebem os padrões automaticamente. A seção no `perfil.json` é:

```json
{
  "interaction": {
    "enabled": true,
    "button": "dpad_up",
    "radius": 4.5,
    "show_prompt": true,
    "show_positions": false
  }
}
```

`button` aceita `dpad_up`, `dpad_down` ou `l3`, reservados ao uso de NPCs/props no
overworld; a coleta usa o A/× físico. Um botão alternativo usa indicação textual
no aviso, para não exibir um D-pad ↑ incorreto. Destrutíveis e coleta continuam
usando A/× mesmo com um botão alternativo de uso. O perfil limita `radius` a
0,5–8 unidades e rejeita números não
finitos. O padrão 4,5 inclui a borda de colisão de escadas grandes, observada
perto de 3,9 unidades no teste real. `show_positions` mostra coordenadas do jogador, contagem do cenário
e até cinco elementos próximos. `show_prompt` controla apenas o aviso visual.
As mudanças são recarregadas com o restante do perfil.

### Modo de calibração

Ativar **Modo de calibração** no menu do ícone TB também ativa automaticamente
a visualização de posicionamento, sem precisar habilitar `show_positions`:

- coordenadas X/Y e altura do jogador, cenário e contagem de elementos;
- marcadores no jogador e em todos os elementos interativos projetados na tela,
  com nome, categoria, coordenadas e distância;
- contorno do raio de interação: verde para elementos próximos, azul para
  distantes e amarelo para o alvo selecionado; o jogador aparece em rosa;
- painel com até cinco elementos mais próximos, incluindo os que estão fora
  do raio ou da tela, e aviso quando faltam dados ou a câmera.

Essa visualização funciona também no modo cursor, com painéis abertos, sem
controle conectado e com a interação desativada. Dados antigos não geram
marcadores; durante o carregamento aparece o estado de espera. Desligar a
calibração remove essas marcações e preserva as opções normais de interação.

### Mercadores e NPCs com missão

O tipo interno do NPC identifica mercadores e apostadores, além dos serviços de
encantamento, transmutação e gemas. A classificação não depende do nome ou do
idioma de exibição. Os marcadores, o aviso de interação e a consulta do cenário
mostram essa função, por exemplo `Mercador: Tarn the Merchant`.

Os estados de missão vêm das tags que o próprio gerenciador de missões aplica
ao NPC em tempo real:

| Tag do jogo | `quest_status` | Indicação na tela |
| --- | --- | --- |
| `QUEST GIVING` | `available` | Missão disponível (!) |
| `QUEST INCOMPLETE` | `in_progress` | Missão em andamento (?) |
| `QUEST COMPLETE` | `ready_to_turn_in` | Missão para entregar (?) |
| `QUEST PASSIVE` | `unavailable` | Missão indisponível |

Um NPC pode ser mercador e ter uma missão ao mesmo tempo; ambas as informações
são preservadas. A ausência de marcador deixa `quest_status` vazio. Uma leitura
inválida produz `unknown`/“Missão não verificada”, sem afirmar que não há missão.
Marcadores removidos pelo jogo desaparecem da classificação na próxima leitura.

No JSON, esses NPCs continuam com `kind: "npc"` e acrescentam `npc_role`,
`quest_status` e `label`. Isso mantém a mesma mira e interação de NPCs, inclusive
a validação nativa da instância e do alcance. No modo de calibração, o painel também
conta mercadores e NPCs com missão identificados no cenário.

## Lista completa e coordenadas

Com o ambiente Python do projeto ativado, em Windows ou Omarchy:

```text
python -m torchbridge.world_inspect
python -m torchbridge.world_inspect --json --watch
python -m torchbridge.world_inspect --pid 1234 --json
```

O pacote também instala `torchbridge-cenario`. O comando é somente leitura:
não cria dispositivos de entrada, não move o cursor e não envia comandos ao jogo.
Sem cenário disponível, a consulta única retorna código 1 e dados explicitamente
indisponíveis. Em `--watch`, cada linha JSON é uma fotografia independente.

No Omarchy, a política Yama também se aplica ao processo que executa a consulta:
um terminal separado não herda a permissão de leitura do TorchBridge aberto com
`--launch`. Use `show_positions` no aplicativo que lançou o jogo; uma consulta
externa exige que a política já permita aquele processo. Não é necessário mudar
a política para usar o recurso dentro do aplicativo.

O JSON traz `player_position`, `entities`, `roster_complete`, `camera_available`,
`status` e `sampled_at` (relógio monotônico local). A posição pública **X/Y** usa
o plano **X/Z do Ogre**; a terceira coordenada do Ogre é o Y do mapa e a segunda
é a altura. Assim, altura não é confundida com distância no chão.

## Arquitetura e mapa de memória

`world.py` define fotografias imutáveis, classificação, distância e projeção.
`world_memory.py` percorre apenas as listas do cenário selecionado, usando os
mesmos leitores em Windows e Proton. `engine/interaction.py` administra a
sequência sem bloquear o loop; `overlay/interaction.py` desenha pelo painter
compartilhado do Qt, Wayland e D3D9.

| Dado | Caminho no PE32 |
| --- | --- |
| Jogador / cenário | `CGameClient + 0x2C` / `+ 0x38` |
| Personagens ativos | `CLevel + 0x5C` → lista → nós `{unit*, next*}` |
| Props / itens | `CLevel + 0x68` → lista → nós `{item*, next*}` |
| Nome do cenário | `CLevel + 0x1F0`, `std::wstring` MSVC 2008 |
| Coordenadas locais | `CPositionableObject + 0x70`, três floats X/altura/Y |
| Objetos com pai (`+0x50`) | nó `+0x58` → posição derivada em `+0x10C`; nó pendente de atualização é descartado |
| Nome interno / nome do item / nome do NPC | `+0x30` / `+0x1B0` / `+0x420` |
| Função do NPC | `CBaseUnit + 0x174`, UNITTYPE (41 mercador, 127 apostador) |
| Marcadores de missão | vetores de tags em `CBaseUnit + 0x114` / `+0x124`; nome de cada template em `+0x18` |
| Tipo concreto | RTTI x86: `vtable[-1] → COL + 0xC → TypeDescriptor + 8` |
| Câmera | `CGameClient + 0x10 → controle + 8` |
| Matrizes Ogre | câmera: projeção `+0x21C`, view `+0x25C`; frustum alternativo em `+0x4F0` |
| Hover confirmado pelo jogo | `CGameClient + 0x1BC` (alvo principal), `+0x1C4` (props/itens, incluindo escadas) |

Cada atualização percorre no máximo 4.096 nós, detecta ciclos e distingue uma
lista vazia de uma leitura incompleta. Campos fixos são lidos em blocos para
reduzir chamadas a `ReadProcessMemory`/`pread` no caminho de 50 Hz. Strings têm
comprimento limitado, com suporte ao buffer curto e ao buffer alocado do MSVC.
Coordenadas não finitas e projeções atrás da câmera são rejeitadas. Somente os
nomes imutáveis de classes por vtable e dos templates de tags ficam em cache;
posições, instâncias e a lista de tags ativas de cada NPC são relidas.
Trocas de processo/cenário/jogador invalidam o cache. Dados com mais de 200 ms
não autorizam interação.

NPCs são personagens neutros/amigáveis vivos, excluindo jogador, pet, summons
e inimigos. A lista também inclui CItem e subclasses: props CTriggerUnit,
equipamentos, ouro e destrutíveis. RTTI inclui as classes base, permitindo
reconhecer subclasses sem depender de nomes fixos. UNITTYPE classifica serviços
e tipos de props; nomes refinam categorias como porta e alavanca. Posições
ilegíveis tornam a fotografia incompleta, sem selecionar outro alvo por engano.

O leitor e o CLI permanecem somente leitura. Movimento, highlight e uso de
objetos são executados pelo módulo nativo separado na thread do jogo. O Windows usa a projeção no retângulo físico do cliente; o Omarchy usa
o retângulo lógico recebido do backend existente. Isso mantém a mesma proporção
da projeção em escala fracionária e em monitores com origem negativa.

### Evidência do layout

Foram consultados os mapas públicos de
[TorchlightMultiplayer, engine.h](https://github.com/mentalfoundry/TorchlightMultiplayer/blob/6d9b3bf1ca49f7638b99413cc65586347936c6ab/src/game/engine.h)
e a análise de listas/portabilidade de
[torchlight-xbox-ui-pc](https://github.com/YaPeL/torchlight-xbox-ui-pc/blob/3bd5c54023249f87564173c9da73be834e748beb/docs/xbox-ui-on-pc.md).
Os fatos de layout foram implementados em Python na arquitetura do TorchBridge;
nenhum código dessas implementações foi incorporado.

A análise offline do Steam instalado confirmou os getters de posição em
`0x0050E3F0` (posição derivada/local), `0x00422C60`, `0x00422CB0`, `0x00422CF0`
(componentes locais), RTTI de CPlayer/CMonster/CTriggerUnit e os getters Ogre
`getViewMatrix`/`getProjectionMatrix`/`_getDerivedPosition`.

Para destrutíveis, a desmontagem do mesmo Steam confirmou o ramo de ataque em
`CCharacter::MoveTo` (chamada em `0x004930ED`): ataque básico `0x0048FBD0`.
O ramo de destrutíveis em `Pickup` (virtual `+0x1B4`, `0x00498B00`) verifica
alcance em `0x00490180` e visibilidade em `0x0048B060`, antes de atacar.
O módulo resolve essas chamadas relativas e confere assinaturas, reutilizando
as verificações sem executar Pickup/MoveTo nem escrever posições ou dano.

A inspeção do fluxo de escadas/entradas confirmou que
`CTriggerUnit::Activate` (`0x004DE6C0`) muda o estado em `+0x1EC` e agenda
saídas em `+0x201`. `CTriggerUnit::Update` (`0x004DE0D0`) emite primeiro o evento
0 (Triggered), seguido de 46/47 (estados 0/1), no frame seguinte.
Na Mine Entrance, o warper está ligado ao evento 0. O rastreamento real confirmou
`Interact → Activate → evento 29 → retorno → evento 0 → CWarper → evento 46`.
`CPositionableObject::Signal`, virtual
`+0x14` (`0x00453F80` no Steam), encaminha esses eventos ao grupo lógico em
`+0x2C`. O módulo preserva uma autorização de uso apenas para essas saídas;
encerrar a autorização junto com `Interact` bloquearia o CWarper da escada.

SHA-256 dos binários inspecionados:

```text
Torchlight.exe a783a60725abd20ba0b5cd64f210f9b5baa08f07a0222a56c8f1e5e182b3eec6
OgreMain.dll   73af58808f0b536614dcbbbf283c4e0ff7e15ab6707c3d674b8ba4a350a68bdc
```

Endereços absolutos acima documentam a inspeção offline; o leitor usa as bases
e os ponteiros do processo corrente, incluindo ASLR/relocação do Proton.

## Validação

Comando: `python scripts/run_tests.py`. A suíte cobre o leitor, o controlador
nativo, o transporte local e o overlay. Os testes novos exercitam os dois
transportes de leitura (Win32 simulado e Proton simulado), bases diferentes,
todos os tipos pedidos, objetos com pai, atualização de posições, leitura parcial,
ciclos, strings inválidas, câmera, projeção, dados antigos, seleção nativa,
ausência de repetição/replay na reconexão e cancelamento durante
menus/perda de foco. O aviso é renderizado offscreen em várias resoluções e
escalas e pelo mesmo renderer do fullscreen nativo. O workflow existente executa
a suíte em Windows/Linux e Python 3.11/3.13.

Também passaram 38 testes de overlay com `QT_SCALE_FACTOR=1.5`, `compileall`
e `git diff --check`. O wheel Linux foi gerado, instalado em ambiente virtual
isolado fora do checkout e verificado quanto aos imports do motor/overlay,
carregamento do transporte nativo e comando `torchbridge-cenario`.

### Regressão de Mine Entrance e Stairs Up (10/11/2026)

Uma cópia isolada do jogo e do prefixo/saves reproduziu a falha usando o mesmo
handler de D-pad do aplicativo, com pressionamentos simulados e comandos nativos
reais. O rastreamento confirmou que o botão era recebido e Interact/Activate
retornavam sucesso, mas a Mine Entrance chamava CWarper pelo evento 0, fora da
autorização. O contador de transições bloqueadas aumentava e o cenário não mudava.
Os testes anteriores simulavam o warper em 46/47 e não reproduziam essa ligação.

Com a autorização do evento 0 e das saídas de estado, o ensaio confirmou:

- Mine Entrance: `TOWN → MAIN`, estado do trigger `1 → 0`, eventos `0 → 46`;
- Stairs Up: `MAIN → TOWN`, estado do trigger `0 → 1`, eventos `0 → 47`;
- CWarper executado com autorização nos dois casos, sem bloqueios das transições;
- permanecer junto à escada não repetiu a ação sem um novo pressionamento.

A regressão nativa agora usa a ordem real `0 → 46/47` e testa o warper ligado
a qualquer uma dessas saídas, incluindo repetição, objeto incorreto e cancelamento.
O ensaio não usou controle físico nem executou Windows/GOG.

### Ensaio inicial de hover no Omarchy (09/11/2026, anterior ao módulo nativo)

Em 2026-11-09, foi executado Torchlight Steam PE32 com GE-Proton11-12, usando
cópias temporárias do jogo e do prefixo (incluindo saves). O harness manteve
a ancestralidade dos processos com subreaper local, sem alterar Yama, permissões
globais ou os arquivos originais. Toda entrada Wayland foi condicionada ao
foco e ao PID da janela desse jogo de teste. As cópias foram removidas ao terminar.

Resultados observados:

- PE relocado para `0x7B240000`; raiz CGame resolvida como Steam;
- tela inicial: posição `(1,86; 0,00; altura 0,30)`, câmera válida e listas legíveis;
- personagem carregado na mina: posição inicial `(87,86; 162,05; altura 0,30)`;
- escada `Stairs Down` listada em `(108,00; 156,50; altura 0,00)`, a 20,90 unidades;
- deslocamento de aproximadamente 16,86 unidades acompanhado pela memória;
- a 4,03 unidades, o mesmo handler da aplicação recebeu um pressionamento
  simulado de D-pad ↑ e emitiu entrada Wayland real;
- sequência observada `hover → click → liberação → Carregando`, iniciando a
  transição pelas escadas;
- a inspeção confirmou que escadas usam o hover de item em `+0x1C4`, enquanto
  `+0x1BC` estava vazio; a correção está coberta pela regressão de memória.

O aviso foi renderizado offscreen, inclusive no caminho de rasterização do
fullscreen. Esse ensaio não usou controle físico e não percorreu todas as
categorias. Windows nativo e GOG não foram executados neste host Linux.

Testes isolados e inspeção estática não substituem a homologação com cada edição
do jogo. Antes de publicar, verificar Windows Steam/GOG e Omarchy/Proton em um
personagem de teste: cada categoria, fontes já usadas, porta fechada/trancada,
NPC sobreposto, duas alturas próximas, portal/escadas e troca de andar, combate
ao lado de NPC, perda de foco durante o clique, desconexão do controle e troca
de resolução/monitor. O backend atende a edição Windows x86 via Proton;
a edição Linux ELF não compartilha esse layout.
