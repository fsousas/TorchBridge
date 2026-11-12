# Movimento e interação nativos (PE32)

O proxy winmm.dll encaminha os exports WinMM ao runtime do sistema e inicia o
módulo. Não depende de Direct3D, do overlay ou do cursor. O executável original
não é substituído. Executa no Windows x86 e no mesmo processo PE32 sob Proton.

O loader confere o build Steam/GOG, o RTTI e as assinaturas das rotinas antes de
instalar os hooks. A inicialização aguarda CGameClient e CGameUI. Builds sem
layout reconhecido não recebem comandos. A instalação gerenciada recusa outros
proxies WinMM; o runtime do sistema continua responsável por áudio e timers.

O runtime consome intenções na thread de atualização do jogador local. Os
destinos usam o pathfinding do jogo; a posição nunca é escrita. O movimento não
gera botões ou deslocamentos do mouse. Mudanças de cenário, menus, foco e leases
vencidos interrompem a caminhada. Habilidades que assumem o caminho preservam
seu movimento; o analógico retoma quando a habilidade permite.

O alvo mais próximo é escolhido pelas posições atuais, com limite de altura e
desempate pelo endereço. Não há preferência por categoria, nome, direção ou
projeção na tela. O mesmo alvo recebe highlight pelo método virtual do jogo.
Cada interação usa um ID de ação, não um botão mantido: reconexão e repetição de
pacotes não repetem interações. O módulo revalida e escolhe o alvo ao executar.

O aplicativo separa coleta (A físico no Xbox/Nintendo, × no PlayStation) de
uso de NPCs/props (D-pad ↑) e ataque a destrutíveis (A/×). Os flags
`pickup_action`/`world_action`/`attack_action` vinculam
a família ao ID da ação, sem alterar os pacotes v2 de 64 bytes. A seleção
continua pela menor distância; se o tipo mudar, a ação é recusada, em vez de
procurar outro objeto. A capability `typed_interactions` permite ao aplicativo
detectar uma DLL antiga, preparar sua atualização e pedir reinício do jogo.
Clientes v2 anteriores, sem esses flags, continuam compatíveis com o protocolo.
`destructible_actions` identifica a DLL que aceita o ataque por A/× e recusa
trocas de família entre coleta, NPC/prop e destrutível, sem consumir outro alvo.

NPCs recebem MoveTo até sua posição antes do estado 9. A rotina nativa de
conversa (`+0x1B8`) espera um caminho existente; sozinha ela desiste fora de
2--2,75 unidades, embora a seleção aceite o raio configurado (padrão 4,5).
A autorização acompanha o progresso da aproximação, com prazo renovado a
cada avanço de pelo menos 0,1 unidade e cancelamento após 1,5 s sem progresso.
Se a rotina desistir, o NPC desaparecer ou a sessão/contexto ficar indisponível,
o alvo e o caminho pendentes são liberados. Um novo vetor de caminhada cancela
a aproximação antes da IA e é executado na mesma atualização, preservando
habilidades que controlam o caminho. Só a entrada no estado de diálogo/serviço
confirma a execução. `npc_approach` identifica a DLL com essa correção e exige
reinício quando o jogo ainda carrega a versão anterior.

O catálogo aceita os alinhamentos NEUTRAL (0) e GOOD (1), com `IsA(131)`
(`INTERACTIVECHARACTER`) para separar serviços/NPCs de animais e monstros.
ANY (3) não é um alinhamento amigável. Os serviços de cidade usam 0; aceitar
somente 1/3 os excluía da seleção e do overlay. A proteção do setter de alvo
também usa o tipo interativo, sem bloquear alvos comuns de combate. A capability
`neutral_npc_services` exige atualização/reinício de módulos com o filtro antigo.
Essa versão também verifica `CTipMenu` (`CGameUI+0x308`, aberto em `+0x18`),
para não selecionar ou caminhar durante as dicas de primeira utilização de lojas.

Destrutíveis são candidatos próprios (tipo 4), reconhecidos por CBreakable na
hierarquia RTTI, incluindo barris comuns/explosivos e subclasses de mods. A/×
mantém o jogador no estado parado (0), cancela o caminho e chama o ataque básico
original, com checagens nativas de alcance da arma, visibilidade e cooldown.
Nunca chama o estado de coleta/uso (7), Pickup ou MoveTo para esses objetos.
O ataque não concede autorização de uso/warper. Cada pressionamento tenta um
ataque; fora de alcance, com obstáculo ou indisponível, ele recusa sem aproximar.
A capability `stationary_breakables` exige atualização/reinício se a DLL antiga
ainda usa aproximação. As rotinas são resolvidas das chamadas relativas
verificadas em MoveTo/Pickup, preservando relocação Steam/GOG.

A interação usa os estados nativos de falar/usar item e a implementação virtual
da entidade, preservando requisitos, colisões, lojas, pesca e missões. Os
dispatches de itens sem autorização são bloqueados no modo direto. Destrutíveis
continuam respondendo ao combate. Warpers só executam dentro de um dispatch de
interação autorizado ou das saídas que ele agendou para o próximo frame.
CTriggerUnit emite primeiro Triggered (evento 0), depois o estado (46/47).
Mine Entrance liga seu warper ao evento 0, não ao evento de estado.
Essa autorização adiada vale uma vez por saída, para a mesma instância, jogador, cenário
e conexão, por até 1,5 s. Perda de foco, menus ou sessão vencida cancelam a ação
do D-pad. Assim, escadas e entradas de dungeon completam seu evento nativo sem
liberar transições por mera proximidade. Volumes de spawn/objetivo não são desativados globalmente.
No modo cursor, um clique explícito continua sendo uma interação válida.

O canal TCP é restrito a loopback. Porta e token aleatório são descobertos pelo
export TorchBridgeInputEndpoint na memória do processo selecionado. Isso
evita arquivos globais de descoberta e não confunde o PID Windows com o Unix.
Pacotes fixos de 64 bytes, versão, token, sequência, tamanhos e números finitos
são verificados; o receptor limita a validade a 200 ms pelo próprio relógio.
O loop de rede nunca chama código do jogo e só publica a intenção mais recente.
A idade de uma ação é distinta da renovação do pacote: um jogo congelado não
reativa um pressionamento antigo ao voltar. O receptor drena pacotes acumulados
e verifica o fechamento do canal antes de publicar uma intenção.

## Build e testes

Windows: python scripts/build_native_input.py, com CMake/Visual Studio C++ x86.
Também há GERAR_MOVIMENTO_SEGURO.bat.

Cross build no Linux:

~~~sh
python scripts/build_native_input.py --compiler /caminho/i686-w64-mingw32-clang++
~~~

O binário vai para assets/native/x86/winmm.dll. Os testes CMake incluem protocolo,
seleção, repetição/reconexão de ações, saídas de estado adiadas e
carregamento/forwarding WinMM em um
executável que não é o jogo. Os testes Python usam TCP real de loopback.
O teste de interação executa os hooks reais com objetos simulados, incluindo
o Interact aninhado que consome o alvo e os eventos 0 e 46/47 no frame seguinte;
não abre janela nem envia entrada ao desktop.
O teste de NPC executa o dispatcher e update_hook reais com NPC, navegação e
relógio simulados: bordas de 4,5/8 unidades, aproximação lenta, conversa,
cancelamento pelo analógico na mesma atualização, caminho recusado, inatividade,
desaparecimento do NPC, perda de foco, troca de modo e menus. A mesma regressão
contra o runtime anterior falha por ausência da chamada de navegação.

Dependência vendorizada: MinHook v1.3.4, commit
c3fcafdc10146beb5919319d0683e44e3c30d537, sob BSD-2-Clause. Licença completa em
vendor/minhook/LICENSE.txt, incluindo o disassembler HDE32. O código de outros
projetos de controle de Torchlight não foi incorporado.
