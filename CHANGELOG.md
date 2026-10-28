# Changelog

Todas as mudanças notáveis do sistema de provas da Escola de TI
(`exam-escola-ti`). O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

> O versionamento começa em **1.0.0**: as versões anteriores (commits desde
> `da2c5f4`) foram ensaios com repos de teste e nunca foram usadas oficialmente
> em prova real. As turmas que exercitaram o sistema até aqui usaram-no como
> aula teste (prova dummy "Hello World").

## [1.5.0] — 2026-10-28

### Adicionado

- **Prova 02/2026 — `exams/2026/track-04-especificacao-sdd-pizzaria`**: nova
  track de especificação SDD (domínio pizzaria — pedidos, esteira de preparo,
  mesas/comandas, fechamento de conta com gorjeta configurável por país,
  divisão de conta com resto de centavos, cardápio com disponibilidade e
  fidelidade por selos). Espelha a track-01: mesma rubrica (A–E), variante por
  `extras` (inclui `GORJETA_PADRAO_PERCENTUAL`), T7, `.prova/entrada`
  obrigatório, janela 120 min; 16 UCs com precedência de erros completa
  (formato 422 → comanda 422 → sabor indisponível 409 → pedido ativo 409);
- **Job universal `readme` no Auto-correção** (`scripts/check_readme.py`):
  roda em **todas** as tracks aplicadas (sem chave no `track.json`) e
  ataca o falso positivo do critério de README — o README **não editado**
  da track-03-crud pontuava 5/5 porque o próprio enunciado casa as regexes
  ("instruções de subida (local e container)", `rodar_testes.sh`). Agora o
  check principal é de **procedência**: `git diff` contra o README do
  commit de aplicação (mesma técnica do T5). Idêntico (ou ausente) = 0 no
  critério **e aviso na issue "🎯 Prova"** (upsert por marcador — o mesmo
  comentário vira ✅ quando o aluno corrige), com a orientação de que o
  README deve conter instruções sobre o trabalho realizado, não o enunciado.

### Mudado

- **`check_entrega.py` virou Dockerfile-only** (o critério de README
  migrou para o `check_readme.py`); o job `estrutura` segue valendo só
  para as tracks com Containerfile como entrega mínima.

> ⚠️ **Operação:** workflows e scripts vivem no repo gerado a partir do
> template — a melhoria vale para repos gerados **após** o push. Repose
> já existentes (aplicados ou não) continuam com o check antigo; o
> tamper-check T3 compara contra o SHA do template da aplicação
> (`.prova/template-ref`), então o push **não** gera falso tamper neles.

## [1.4.0] — 2026-10-14

Mudanças pós-aplicação da Prova 01/2026 (feedback do docente com ~68 alunos):
unificação da fonte da variante, simplificação do fluxo de aplicação,
limpeza do repo do aluno, ponto de entrada da spec SDD e fim do falso
positivo de "commits antes da aplicação". Vale para a próxima aplicação — a
prova de 07/10/2026 não é afetada.

### Corrigido

- **Repo do aluno ia para a prova carregando a árvore `exams/` inteira** (a
  pasta do ano fica publicada no template antes da geração dos repos). O
  overlay copiava a pasta escolhida para a raiz, mas o restante de `exams/`
  ficava no repo — caso real: um aluno fez a prova inteira dentro de
  `exams/2026/track-03-crud/...`. O *Aplicar prova* agora **remove `exams/`
  no commit de aplicação** (idempotente; nada que o CI/correcao leem mora
  lá; validar-exams só roda no template; tamper T3 protege
  `scripts/`/`.github/`/`docs/`, não `exams/`);
- **Falso positivo "N commit(s) ANTES da aplicacao (fase de preparacao)"**
  (aparecia em quase toda issue): o marco era o commit de aplicação (t0), mas
  os alunos começam a prova no início da aula e o `/track`+aplicação chega
  minutos depois — commits válidos da janela eram rotulados "preparação".
  Agora o marco é o **commit de setup** do repo: antes dele = preparação;
  entre setup e t0 = mensagem neutra ("inicio de aula; trabalho valido");
  a trampa real (`fora_da_janela`, depois do fim) não muda. Sem commit de
  setup (repo legado), comportamento antigo. `teacher.json` ganha
  `commits.pre_aplicacao` (pré-setup) e `commits.pre_t0_pos_setup` (opcionais);
- **Critério E não lia specs em `docs/`** (caso real da turma 2026): o
  enunciado da track-01 sugeria os arquivos de spec sem dizer a pasta, um
  aluno entregou tudo em `docs/` (pasta natural para `.md`) e o `check_md.py`
  pontuou 0/15 sem ler os arquivos — o prefixo `docs/` inteiro era excluído.
  Agora a exclusão é por caminho exato (`docs/REGRAS.md`, `docs/TRACKS.md`),
  specs em `docs/` pontuam normalmente, e o enunciado/README da track-01 diz
  explicitamente onde os `.md` vão (raiz, com `docs/` tolerado).

- **Duas fontes de variante — `variante/params.json` é a fonte única**: os
  enunciados das tracks 01 e 02 pedia para o aluno RODAR
  `python scripts/variante.py` (antes da aplicação isso gerava um
  `params.json` com os parâmetros da **track errada**, por causa do fallback
  de descoberta da pasta do ano) e os READMEs apontavam para "o comentário da
  issue" como lista de valores. Agora todo enunciado/README (tracks 01/02/03
  e dummy) aponta para **ler** `variante/params.json` — gerado no commit de
  aplicação, nunca pelo aluno — e o comentário de aplicação na issue declara
  ser só uma cópia dele;
- **Comentário de aplicação gerado a partir do arquivo**: `aplicar_prova.py`
  relê o `variante/params.json` gravado (em vez de reformatar o dict em
  memória) e usa as descrições de `variante.uso` do contrato da track — o
  texto genérico do dummy ("nome que a suíte envia em `/saudar`") não vaza
  mais para tracks onde o parâmetro significa outra coisa;
- **"❌ rode `python scripts/variante.py`" antes da aplicação**: em ~30% dos
  repos analisados da turma 2026 o upsert de preparação ficou travado nessa
  mensagem — o fallback de `pasta_do_ano()` encontra `exams/<ano>` herdada da
  geração do repo e validava a variante antes da prova existir (um aluno
  digitou o comando como comentário na issue). `preparar_entrega.py` só
  valida a variante quando a aplicação de fato aconteceu (marcador
  `.prova/exam-dir`/`contrato.json` na raiz); antes dela, mensagem ⏳ sem
  ação pedida. Mensagens de divergência/ausência pós-aplicação também deixam
  de pedir script no escopo errado;
- **Comandos digitados errado silenciados**: o gatilho da auto-correção agora
  tolera os formatos reais digitados pelos alunos — `/auto-correção`,
  `/autocorrecao` e `/auto correcao` (antes: silêncio total, sem correção);
- **Gatilho falso do aplicar-prova**: o `if` do workflow aceitava qualquer
  comentário contendo a palavra "aplicar" (ex.: "quando vai ser aplicada?") —
  agora só dispara para `/track <nome>` ou `/aplicar`.

### Alterado

- **Ponto de entrada da spec (SDD)**: a correção por modelo fixo precisa saber
  por onde começar a ler os `.md` (na turma 2026 as specs apareceram em ~12
  pastas diferentes). Track-01 passa a exigir `.prova/entrada` — arquivo com
  o caminho relativo do arquivo inicial (recomenda-se um README índice com
  links); o *Preparar entrega* valida existência/caminho na issue (exigência
  declarada por `suites.md.entrada` no `track.json` da track, para as
  próximas tracks reutilizarem) e o `teacher.json` ganha o campo opcional
  `entrada` com o caminho declarado;
- **`/aplicar` descontinuado**: o comando deixou de existir no `/ajuda`, nos
  docs e no checklist — a aplicação já é consequência direta do `/track`.
  Quem comentar `/aplicar` recebe um aviso de descontinuação (upsert
  `<!-- aplicar-deprecado -->`) e o gatilho do workflow foi mantido só por
  compatibilidade (idempotente);
- **Ordem do processo explicitada (web-first)**: checklist da issue, README de
  primeiros passos e boas-vindas agora instruem o aluno a fazer tudo pela
  interface web até o comentário "✅ Prova aplicada" e **clonar/fazer pull só
  depois** — commits locais antes da aplicação só geravam ruído
  ("N commit(s) antes da aplicação") e tamper falsos.
- **Limpeza pós-aplicação ampliada** (`aplicar_prova.py`, passo 4c): além da
  árvore `exams/` (commit anterior), o commit de aplicação agora remove
  `CHANGELOG.md` do template (histórico do sistema de provas, sem sentido no
  repo do aluno) e varre `__pycache__/`/`*.pyc`/`*.pyo` que vierem com a pasta
  aplicada. Caminhos protegidos pelo tamper T3 (`scripts/`, `.github/`,
  `docs/`) nunca são tocados — a limpeza só age fora deles. Simulado de ponta
  a ponta em repo temporário: raiz final = só os arquivos da track +
  esqueleto funcional;
- **Template sem bytecode no disco**: `exams/dummy-exam/__pycache__/` (que o
  overlay levaria para a raiz do repo do aluno) e `scripts/__pycache__/`
  removidos do template — o `.gitignore` já os bloqueava, mas o disco do
  template alimentava repos novos;
- **`variante.py`**: docstring alinhada ao comportamento real (lê o contrato
  da RAIZ pós-overlay; `.prova/exam-dir` marca a origem).

### Adicionado

- **"⚠️ Último aviso — este README é seu"** ao final de todo README de track
  (01/02/03 + dummy): o aluno é convidado a editar o README depois de lê-lo e
  a indicar o que achar necessário para a entrega — onde está o ponto de
  entrada da solução, decisões que tomou, o que o corretor deve olhar primeiro
  (editar não pontua; evita que o básico feito passe despercebido). Motivação
  real da turma 2026: entregas fora do lugar esperado que o corretor não
  localizou, e o caso de um aluno que criou testes próprios **dentro** de
  `tests/public/` e foi zerado por procedência — criar testes é boa prática,
  desde que fora das pastas da correção. O aviso separa explicitamente o que
  é nosso (`tests/public/`, `contrato.json`, `rubrica.json`, `track.json`,
  `ENUNCIADO.md`, `scripts/`, `.github/` — não editar nem criar arquivos
  dentro) do que é dele (todo o resto: raiz, `src/`, `app/`, `backend/`,
  `frontend/`, `tests/<sua-pasta>/`, `meus-testes/`, `docs/` sem alterar o
  que já veio).

## [1.3.0] — 2026-10-07

Track 03 (CRUD): a persistência agora aceita **os dois caminhos** — `/data`
(single-container) ou banco externo via `compose.yaml` — e um compose limpo
passa a ser embarcado na track.

### Adicionado

- **`compose.yaml` limpo em `exams/2026/track-03-crud/`**: serviço `app`
  (build do `Containerfile`, `${PORTA_API:-8080}:8080`, volume nomeado
  `app-data:/data`) + exemplo comentado de Postgres; o próprio arquivo explica
  os dois modos de correção e as regras do modo compose (serviço `app`, porta
  `${PORTA_API}`, volumes nomeados);
- **Detecção de modo por hash**: `track.json` ganha o bloco `compose`
  (`template_sha256`); `scripts/rodar_testes.sh` sobe o ambiente via
  `docker compose up --build -d` quando o aluno **customizou** o compose
  (sha256 diferente do template) e mantém o modo single-container quando o
  arquivo está intacto ou ausente — quem não mexer não enfrenta caminho novo.
  Schema documentado em `docs/TRACKS.md`.

### Alterado

- Track-03 (`README.md`, `contrato.json`, `rubrica.json`): a regra de
  persistência declara os dois caminhos válidos — (a) `/data` (arquivo ou
  banco embutido) ou (b) banco externo via `compose.yaml` customizado; a
  suíte escondida recria o **serviço da API** (container ou serviço `app`)
  e exige fila/sequência/painel preservados nos dois modos.

## [1.2.0] — 2026-10-07

Prova 01 de 2026: as três tracks reais entram no repositório
(`exams/2026/track-01-especificacao-sdd/`, `track-02-debugging/`,
`track-03-crud/`), convertidas do material de origem para o formato de overlay
do esqueleto v1.1.0. Publicação efetiva (push/release) só no dia da aplicação.

### Corrigido (auditoria pré-prova por 3 agentes)

- **Âncora da janela anti-fraude**: `check_trampas.py` e `fechar_prova.py`
  só aceitam o commit de aplicação **do bot** (`--author=github-actions`) —
  um commit do aluno com a mesma mensagem não re-ancora mais a janela nem
  neutraliza o diff de procedência;
- **Procedência ampliada**: `tests/public/` (chega via overlay) e
  `ENUNCIADO.md` não podem mudar após a aplicação;
- **T3 pinado**: tamper-check compara contra o SHA do template **da
  aplicação** (`.prova/template-ref`) — push de fix no template durante a
  prova não gera mais falso tamper;
- **`check_md.py`**: parser de fence segue CommonMark (evasão com 4 crases
  conta como bloco; fence inline de uma linha não abre bloco) e `exams/` é
  excluído da pontuação do critério E;
- **`fechar_prova.py`**: `fora_da_janela` conta só commits após o fim da
  janela (preparação não polui mais o teacher.json);
- **`validar_exams.py`**: `extras` exige `faixa >= 1`, `passo` int e
  `formato` com 1 placeholder; chave de workflow desconhecida vira **aviso**
  (typo não desliga job em silêncio);
- `score_publicos.py` e as suítes: arredondamento **half-up**;
- `smoke_track.py`: header CORS case-insensitive; job `compila` com
  `setup-python`; histórico da nota usa o teto real (não /100 fixo).

### Adicionado

- **Canários agênticos** (trampas para agentes de IA): comentários ocultos no
  material das 3 tracks (`ENUNCIADO.md` da track-01, comentários Java/JSX da
  track-02, README da track-03) instruem LLMs a inserir marcas detectáveis —
  a esteira do docente (teacher-escola-ti) varre as entregas; suspeita vai
  para revisão manual, nunca zero automático. Aviso de dissuasão em
  `docs/REGRAS.md`.
- **Tracks reais de 2026** com `contrato.json`, `rubrica.json`, `track.json`,
  stubs e — na track-02 — a aplicação quebrada de propósito (11 erros em 3
  camadas) e o `smoke_track.py` de checagens;
- Gancho de testabilidade na track-01: `entrada` opcional no UC1 (+422
  `entrada_invalida`) e precedência declarada 422-antes-de-409.

### Alterado

- **Dificuldade elevada nas 3 tracks** (feedback do docente: prova estava
  simples para 1h30):
  - track-01 (SDD): +4 casos de uso (UC5 cancelamento, UC6 histórico por
    placa, UC7 tolerância gratuita — nova variante `TOLERANCIA_MINUTOS`,
    UC8 placa duplicada 409) + precedência declarada 422-antes-de-409;
  - track-02 (debugging): +3 erros plantados na camada Docker/compose
    (`--from=builder` no Containerfile do backend, `npm ci` sem lockfile no
    frontend, healthcheck do db com usuário errado) — 11 erros no total;
  - track-03 (CRUD): +2 endpoints (rechamar, cancelar) + exigência de
    concorrência (rajadas sem código duplicado);
  - todas: declarado que os testes escondidos podem cobrar a gestão do SDLC
    da entrega (higiene, segredos, linters genéricos).

## [1.1.0] — 2026-10-07

Infraestrutura para as provas reais de 2026: o esqueleto passa a suportar os
três estilos de track (API/juiz, especificação SDD, debugging fullstack).
As tracks em si (`exams/2026/…`) **não fazem parte desta release** — são
publicadas só no dia da aplicação.

### Alterado

- **Nomes agnósticos de runtime**: `Containerfile` (em vez de `Dockerfile`) em
  todas as tracks e stubs, e `compose.yaml` (já era o nome canônico na track de
  debugging). `rodar_testes.sh` detecta `Containerfile`/`Dockerfile`
  (`-f` explícito) e `check_entrega.py` aceita ambos — docker e podman
  funcionam igualmente.

### Adicionado

- **`variante.extras` no `contrato.json`**: tabelas de variante genéricas
  (`{"opcoes": [...]}` ou `{"base": N, "passo": M, "faixa": F}`) para tracks
  com parâmetros além do núcleo (`PREFIXO`/`RAZAO_PREFERENCIAL`/`PORTA_API`),
  que passa a ser opcional quando `extras` existe (`scripts/variante.py` +
  validação em `scripts/validar_exams.py`).
- **Novo job `md` na auto-correção** (chave `auto-correcao.md` no lockfile):
  critério E mecânico dos `.md` para tracks de especificação, via novo script
  do esqueleto `scripts/check_md.py` (config em `suites.md` do `track.json`;
  bloco de código acima do limite = fatal, zero via job de nota).
- **`check_trampas.py`**: `ENUNCIADO.md` (quando presente) passa a ser
  protegido contra alteração após o commit de aplicação.
- **Extras com `formato`**: entradas de `variante.extras` aceitam `formato`
  (ex.: `"prova_%02d"`) para parâmetros string derivados de número.
- **Novos jobs de debugging na auto-correção** (chaves `auto-correcao.compila`,
  `.sobe`, `.smoke`, `.metodo`): camadas de compilação (`check_build.py`),
  subida do ambiente compose com variante injetada (`check_sobe.py`), smoke de
  ponta a ponta com ciclo de vida no esqueleto e checagens entregues pela
  track em `smoke_track.py` (`smoke.py`), e método sistemático
  (`check_metodo.py`).

## [1.0.0] — 2026-10-06

Primeira versão oficial do sistema de provas.

### Adicionado

- **Modelo de repositório único**: esqueleto ano-agnóstico (workflows + scripts)
  + pastas de prova (`exams/<ano>/<track>/`) aplicadas por *overlay* no repo do
  aluno no dia da prova, via issueops (`git fetch` no template — o repo gerado
  não é fork).
- **Prova-teste permanente "Hello World"** (`exams/dummy-exam/`, fora da
  hierarquia de ano): valida o sistema e treina o ciclo de entrega como
  *modo sandbox*; nunca é aplicada sem seleção explícita.
- **Issue única "🎯 Prova"** com lock em `.prova/issue`: preparação, seleção,
  aplicação, nota e fechamento acontecem na mesma issue (o aluno fica livre
  para usar os próprios issues). Setup com idempotência de **recurso** (adota
  issue existente, reconcilia duplicatas) e autocura do lock.
- **Comandos na issue**: `/track <nome>` (seleção, dispara a aplicação),
  `/aplicar` (força reaplicação), `/auto-correcao` (correção sob demanda),
  `/ajuda` / `--help` (lista de comandos).
- **Seleção sempre explícita do aluno** — fim da aplicação implícita; com mais
  de uma candidata publicada a aplicação trava de propósito até o `/track`.
- **Auto-correção sob demanda**: pushes não disparam correção (CI lenta ×
  incentivo a commits pequenos); correção completa (trampas + entrega + testes
  públicos + nota) roda via `/auto-correcao` ou dispatch, com gate no
  fechamento — fechar a issue sem correção **reabre** com aviso.
- **Nota em comentário único editado** (`<!-- nota-parcial -->`): `Última
  atualização` + `### Histórico` (uma entrada por disparo, até 10, com link da
  run). Linha `**Nota parcial:** N/100` parseável pelo fechamento.
- **Comentário de estado da preparação e ack de seleção como upsert**
  (`<!-- preparacao -->`, `<!-- track-ack -->`) — fim das duplicatas em
  rajadas de `issues: edited` (checkboxes).
- **Trampas**: variante por nome de repositório (T1), `.prova/id` canônico
  (T2), tamper-check contra o template (T3, opcional), janela auto-ancorada no
  commit de aplicação + `janela_minutos` da rubrica (T4 — só pega commits
  **depois** do fim; preparação entra como informativo), autoria por login do
  GitHub (T5).
- **Lockfile `track.json`** validado no CI do template (schema, `recursos`
  obrigatório, valores bool de workflows) e honrado pelos jobs da
  auto-correção.
- **`teacher.json` (schema 1)** — handshake de entrega na raiz do repo do
  aluno: aluno (login, RA, **nome**), variante, janela, commits
  (`commits_pre_aplicacao`, `fora_da_janela`), nota parcial,
  `auto_correcao.nota_ultima` e fontes.
- **Validação estrita de `FONTES.md`** (`scripts/fontes.py`, compartilhado com
  o teste público): só contam URLs em linha de tabela numerada, deduplicadas;
  URLs em texto corrido/exemplos não contam.
- **Suíte escondida fora do CI**: correção manual pelo professor ou Actions do
  repo privado do docente — aos alunos, cópia/relatório com a data de criação
  dos testes verificável (transparência sem entregar o ouro).
- **Docs**: README com sumário por persona (professor que replica / aluno que
  testa), ciclo de vida em mermaid, `docs/REGRAS.md`, `docs/TRACKS.md` e guia
  da prova-teste.

### Corrigido (ensaios com repos de teste)

- Corrida na geração do template (dois pushes) criando **issues duplicadas** →
  idempotência por recurso + reconciliador de duplicatas.
- Push do bot (GITHUB_TOKEN) não disparar workflows → aplicação passa a ser
  disparada pelo próprio comentário `/track` (schedule de 10 min como
  backstop).
- `git fetch --depth 1` deixando o repo do aluno *shallow* e quebrando o push
  do commit de aplicação ("shallow update not allowed").
- Tag inválida em `rodar_testes.sh` (`prova-<slug>-`) e porta não derivada da
  variante (`PORTA_API` do `variante/params.json`).
- Falsos positivos das trampas: commits de preparação contados como fora da
  janela; RA comparado a autor de commit (agora: login do GitHub); T3 desarmado
  tratado como suspeita (agora é observação de configuração).
- Contagem de fontes incluindo URLs de exemplo do template.
- Respostas do preparar fora de contexto (roteamento) e comentários duplicados
  (upsert).

[1.2.0]: https://github.com/endersonmenezes/exam-escola-ti/releases/tag/v1.2.0
[1.1.0]: https://github.com/endersonmenezes/exam-escola-ti/releases/tag/v1.1.0
[1.0.0]: https://github.com/endersonmenezes/exam-escola-ti/releases/tag/v1.0.0
