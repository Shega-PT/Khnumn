# Changelog

Todas as mudanças relevantes do Khnumn são registadas neste ficheiro.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-PT/1.1.0/),
e o projecto usa [Versionamento Semântico](https://semver.org/lang/pt-PT/).

**A versão do projecto é 0.1.0 e mantém-se até haver instrução em
contrário.** O trabalho em curso é registado em `Unreleased`, e uma
alteração não incrementa a versão por si só. O registo de revisões da
especificação, em `docs/Khnumn.md` §29, é o registo histórico do documento;
este ficheiro é o registo do projecto.

**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

---

## [Unreleased]

### Adicionado

- **Núcleo Rust** (`crates/khnumn-core`): modelo de dados, validação contra
  esquemas JSON Schema 2020-12 versionados, hashing canónico, catálogo SQLite,
  contrato de tarefa, grafo acíclico dirigido com cache em memória por hash,
  proveniência, logs estruturados e medição de memória de processos
  externos.
- **CLI `khnumn`** (`crates/khnumn-cli`): `init`, `ingest`, `report`,
  `validate`, `run` e `info`, com saída legível por máquina e códigos de
  saída significativos.
- **Camada científica Python** (`python/khnumn`): leitura de EXIF e XMP em
  Python puro, quality gate de imagem, geodesia por PROJ, e a fronteira
  `khnumn-tarefa-v1` entre o núcleo e a camada.
- **Esquemas versionados** (`schemas/`): `activo-v1`, `controlo-v1`,
  `projecto-v1` e `produto-v1`, embutidos no binário e com resolução de
  referências por registo de recursos. O `produto-v1` foi revisto para incluir
  o formato em disco, o nome do campo escalar de um mapa, a sua legenda
  numérica e a declaração de ausência de CRS, seguindo o mesmo idioma que a
  incerteza já usava, e aplicando-se a produtos reais a partir da Fase 9.
- **Fase 0 do roadmap** (`F0.E1` a `F0.E9`): alvo de validação, hardware de
  referência, tolerâncias por classe de projeto, protocolo de checkpoints,
  modelo de metadados versionado, política de falhas, auditoria de licenças,
  manifesto de conjuntos de dados e linha de base manual.
- **Ferramentas** (`scripts/`): `verificar.sh`, `auditar-licencas.py`,
  `gerar-manifesto.py` e `linha-base.py`.
- **Adaptador do motor de SfM** (`python/khnumn/adaptadores/colmap.py`): a
  interface de `docs/Khnumn.md` §18.3 — `run`, `inspect`, `cancel`,
  `collect_metrics` e `export` — com as três fases do motor separadas em
  `extrair`, `corresponder` e `mapear`, para que o pico de memória de cada
  fase seja o seu e não a soma, com o gauge declarado e o diagnóstico do
  modelo.
- **Fase 9 do roadmap** (`F9.E1` a `F9.E4`): registo de produtos no
  catálogo, rasterizador de software em Rust, publicação em COG e renderização
  multivista determinística, com as etapas distribuídas `F3.E13`, `F4.E11`,
  `F4.E12` e `F8.E6`. A numeração das fases é histórica e a ordem de
  execução é a da §3 do roadmap.
- **Fase 2 do roadmap** (`F2.E1` a `F2.E6`): o pipeline de reconstrução
  esparsa, executado pela CLI como três tarefas do grafo, com os parâmetros
  do motor registados, o limite de memória declarado por tarefa, o gauge
  fixado explicitamente, o diagnóstico do modelo, e a exportação das poses,
  da nuvem esparsa e do modelo. A comparação com a linha de base manual
  coincide exactamente em todas as métricas.
- **Contratos** (`schemas/`): o esquema do produto com incerteza declarada
  ou declarada ausente, e o esquema do ponto de controlo com covariância
  3×3 obrigatória.

### Alterado

- `THIRD-PARTY.md`: a §2 passa a distinguir o que está integrado do que está
  apenas aprovado, com versão, licença, data de verificação e hash do
  artefacto; a §3 remete para o SBOM gerado pela auditoria.
- `processos/decisoes-motores.md` §2: a matriz de motores reflecte a
  auditoria de `F0.E7` — extracção de metadados própria sobre `Pillow` e
  `piexif`, `pycolmap` 4.2.1 como via de distribuição do motor, `pyproj` para
  a geodesia, e `PDAL` fora do caminho de código.
- `processos/protocolo-benchmark.md`: §2 preenchida com o hardware medido,
  §4 com o protocolo de checkpoints, e §6 com as três classes de projeto e
  as suas tolerâncias.
- `docs/Khnumn.md` §13.5: distinção entre a ortoimagem e a rasterização;
- `docs/Khnumn.md` §13.6: secção nova, rasterização de superfície e mapas de
  diagnóstico;
- `docs/Khnumn.md` §14.4: ligação entre a rasterização e a evidência por
  célula;
- `docs/Khnumn.md` §15.1: nove métricas derivadas de projecção;
- `docs/Khnumn.md` §18.1: confirmação de que a rasterização em Rust não é
  uma excepção à regra da geodesia;
- `docs/Khnumn.md` §18.2: rectificação do papel do Open3D e do CloudCompare,
  e acrescento do rasterizador e do crate `tiff`;
- `docs/Khnumn.md` §19.1: o visor de superfície e a regra de paridade
  byte a byte;
- `docs/Khnumn.md` §19.2: o par de formatos TIFF intermédio e COG publicado;
- `docs/Khnumn.md` §22: a Fase 9 e os bullets das Fases 3, 4 e 8;
- `docs/Khnumn.md` §23: o risco 13, confusão entre modelo de câmara e
  plausibilidade visual;
- `docs/Khnumn.md` §26: as referências técnicas da técnica e o registo da
  referência funcional externa consultada, com a declaração de que nenhum
  código foi reproduzido;
- `docs/Khnumn.md` §27.1: as decisões 9 e 10, com remissão para ADR-012 e
  ADR-013;
- `docs/Khnumn.md` §29: a entrada do registo de revisões;
- `processos/decisoes-motores.md`: ADR-012 e ADR-013, a matriz de motores
  e o consumo de recursos;
- `processos/protocolo-benchmark.md`: a condição de comparabilidade das
  rasterizações e a cláusula de que a imagem não é um critério de aceitação;
- `processos/hardware-referencia.md`: a linha da rasterização e da
  publicação de rasters;
- `processos/alvo-validacao.md`: a verdade-fundamento da rasterização no
  ETH3D, e o que valida e o que não valida;
- `processos/auditoria-licencas.md`: a regra da árvore transitiva dos wheels;
- `THIRD-PARTY.md`: `rasterio`, o crate `tiff`, e a rectificação do papel
  do Open3D e do CloudCompare.

### Registado

- O ambiente de referência tem 3 826 MiB de RAM e **não tem acelerador**; o
  orçamento de trabalho é de 500 MiB com 300 MiB de folga, medido por
  `VmHWM` com amostragem de 50 ms, e o limite é aplicado por tarefa: a
  tarefa que o excede é interrompida, com a causa no relatório.
- A reconstrução densa em acelerador (`F4.E3`) e a sua validação contra a
  referência (`F4.E10`) **não são executáveis neste ambiente**, com a causa
  registada.
- O conjunto de dados de referência é o ETH3D `terrace`, sob
  CC BY-NC-SA 4.0: a sua redistribuição comercial está excluída, e o estado
  de aceitação dos produtos que dele derivam é `NOT_VALIDATED`.
- **A prévia de focagem do motor não é reconciliada com a redução de
  resolução.** O motor reduz as imagens, mantém a câmara na resolução
  original e a prévia de focagem na resolução original, o que torna o limiar
  epipolar cerca de 3,8× mais apertado do que deveria. A redução tem de ser
  um passo explícito do Khnumn, com imagens próprias e hashes próprios.
- **A memória da extracção de features é quadrática na resolução.** Medido
  em 9 imagens: 1 066 MiB a 1 600 px, 640 MiB a 1 200 px, 472 MiB a 1 000 px.
  A resolução de trabalho é, por isso, uma consequência do orçamento e não
  uma preferência de qualidade.
- **A partição de verificação tem de preservar a conectividade.** Remover
  uma imagem de cada quatro partia o grafo de vistas; a regra adoptada é a
  partição por blocos de quatro, com a primeira imagem de cada bloco
  reservada para verificação.
- **A implementação reproduz exactamente a via manual.** Mesmos ficheiros,
  mesma configuração, mesmo gauge declarado: 4 câmaras, 114 pontos, 320
  observações, 0,868138 px de erro de reprojecção médio e uma componente
  conexa, nos dois caminhos. O estado de aceitação é, ainda assim,
  `NOT_VALIDATED`, porque o conjunto não tem referência geodésica
  independente.

---

## [0.1.0] — 2026-10-20

Semente deste registo. O conteúdo abaixo é o registo de revisões da
especificação, transcrito de `docs/Khnumn.md` §29, e é o estado do projecto
na data em que a proposta foi escrita. **Não existia implementação executável
nesta data.**

### Adicionado

- Revisão inicial do documento de especificação. Validação de conceito contra
  fontes primárias; correcção das licenças dos motores e da tabela de
  `docs/Khnumn.md` §18.2, com a exclusão do copyleft forte do núcleo;
  identificação de que os motores de referência não fornecem fluxo de pontos
  de controlo de primeira classe e definição do modelo observacional do
  controlo em §10.4; introdução de critérios de aceitação normativos em
  §15.5; introdução das limitações da reconstrução aprendida em §11.6;
  introdução das secções de radiometria e de referência temporal;
  reconciliação do DAG fundacional com o faseado; atualização das referências
  com versão e data.

- Nome de trabalho do projecto passa de Mímir para **Khnumn**. A mudança foi
  motivada pelo conflito de uso com o Grafana Mimir e pelo desajuste
  semântico do nome anterior, e foi precedida de verificação em cinco
  índices e na web, sobre 74 candidatos. O ficheiro de especificação passou
  para `docs/Khnumn.md`, o directório de trabalho foi renomeado, e foi criado
  um `NOTICE` com o aviso de copyright, mantendo o texto da licença intacto.
  Registo em ADR-011.

- Reorganização da documentação e politização de licenças. A especificação
  e o roadmap passam para `docs/`, por descrevrem o sistema e a ordem de
  construção; o registo de decisões e o protocolo de benchmark passam para
  `processos/`, por serem registos vivos que crescem com o trabalho. As
  referências entre documentos passaram a usar o caminho relativo à raiz do
  repositório, com a convenção declarada em cada ficheiro. O projecto passa
  a ter uma licença única, a Apache-2.0, com o texto em `LICENSE` na raiz, e
  as licenças dos componentes de terceiros passam a ser declaradas em
  `THIRD-PARTY.md`, que separa o que está aprovado para integração do que
  está efetivamente integrado. Registo em ADR-010. A ortografia foi
  uniformizada pela forma do Acordo Ortográfico de 1990, que estava misturada
  entre formas antigas e actuais ao longo dos cinco documentos.

- Resolução dos três riscos residuais que restavam. Incerteza do controlo: a
  covariância 3×3 passa a ser obrigatória por ponto de controlo, com método,
  instrumento, data e operador, e a propagação passa a existir de fato, por
  ensemble sobre a etapa final, com a similaridade de 7 parâmetros ponderada
  pelas covariâncias; a §15.3 é reescrita porque a incerteza total passa a
  ter duas partes identificáveis. Marcas de controlo: nova §5.7 especifica o
  alvo circular e simétrico, o tamanho em píxeis verificado contra a GSD
  planeada antes do voo, a deteção automática como refinamento local com
  filtro de consistência e revisão humana; a §8.1 e a nova §8.4 passam a
  cobrir a deteção e a verificação de acquisibilidade. Refinamento iterativo:
  a via densa em CPU passa a ser um ciclo com priori da iteração anterior,
  paragem por autoconvergência, orçamento declarado e retenção da melhor
  iteração, o que inverte a prioridade dos caminhos quando o requisito é
  densidade comparável à da via de acelerador. O bloco `control` da
  configuração ganha a covariância obrigatória e o número de amostras, e
  nasce um bloco `dense` com o orçamento de iterações.

- Resolução das duas decisões que estavam em aberto. Caminho da reconstrução
  densa em CPU: três caminhos declarados em §13.1 e em §3.3, com o núcleo
  100% permissivo, o motor de MVS externo como adaptador opcional e
  instalável à parte, e o caminho de acelerador; a escolha passa a ser do
  planeador, segundo a capacidade do host, e a constar da proveniência de cada
  produto. Restrição de pontos de controlo: cadeia concreta sobre as ligações
  Python do motor, com fixação explícita do gauge por três pontos, e a
  limitação de a incerteza de levantamento não entrar como prior ponderado
  passa a ser declarada em §10.4, §11.4 e §15.3. Método de controlo por
  omissão: priors de pose GNSS, com a transformação de similaridade reservada
  ao último recurso e nunca a originar um estado conforme. §27 reestruturada
  em decisões já fixadas e decisões por fixar, com os registos ADR-005 e
  ADR-006 correspondentes.

- **Rasterização de superfície.** A §1.1 prometia mapas de cobertura,
  densidade, qualidade e incerteza, e §22 previa a deteção de zonas com
  cobertura insuficiente; nenhum dos dois tinha produtor, e três das métricas
  de §15.1 — cobertura espacial e zonas sem observações, consistência entre
  vistas, e o desvio introduzido pela simplificação — não tinham instrumento.
  A nova §13.6 especifica a rasterização como instrumento de diagnóstico:
  projeta a geometria medida sobre uma grelha 2D sob um modelo de câmara
  explícito, e devolve um campo quantificado, com classe de ausência
  explícita, determinismo, e a proibição de usar a plausibilidade visual como
  métrica. Registo em ADR-012 e ADR-013.
- **Referência funcional externa.** Um repositório de rasterização de terreno
  procedural foi consultado quanto à funcionalidade necessária — z-buffer,
  corte no plano near, níveis de detalhe, cor por campo escalar — e o seu
  autor declarou autorização de uso e melhoria. Nenhum código, expressão ou
  estrutura de ficheiros desse repositório foi reproduzido, e nenhum dos seus
  ficheiros integra o Khnumn. A implementação deriva das descrições publicadas
  (Heckbert 1984; Ericson), e a procedência está registada em §26 de
  `docs/Khnumn.md` e em ADR-012.
- **A auditoria de licenças cobre a árvore transitiva dos wheels**, e não
  só o requisito declarado, com o `rasterio` como primeiro caso. A regra está
  em `processos/auditoria-licencas.md` §2.5, e o `rasterio` fica na §2.2 de
  `THIRD-PARTY.md` até a verificação estar feita.


[Unreleased]: https://example.invalid/khnumn/compare/v0.1.0...HEAD
[0.1.0]: https://example.invalid/khnumn/releases/tag/v0.1.0
