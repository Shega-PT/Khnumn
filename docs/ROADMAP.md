# Khnumn — Roadmap

**Âmbito:** este documento fixa a **ordem de execução** da implementação do Khnumn. Não contém datas, nem durações, nem estimativas de esforço. A ordem é determinada por dependências técnicas, e cada etapa declara as suas.

**Estado do projeto:** em desenvolvimento. A Fase 0 está fechada e a Fase 2 está concluída: existe um núcleo executável, com ingestão e inventário por hash, leitura de metadados, quality gate, grafo de tarefas com cache por hash, e reconstrução esparsa pelo motor de SfM com o gauge declarado. O estado de cada etapa está em §4, e o registo de progresso em §7.

**Versão do roadmap:** 0.1.0 · **Data:** 2026-10-20 · **Idioma:** Português europeu

---

## Índice

1. [Como ler este roadmap](#1-como-ler-este-roadmap)
2. [Estados e regras de transição](#2-estados-e-regras-de-transição)
3. [Ordem de execução canónica](#3-ordem-de-execução-canónica)
4. [Fases e etapas](#4-fases-e-etapas)
5. [Temas transversais](#5-temas-transversais)
6. [Itens deliberadamente adiados](#6-itens-deliberadamente-adiados)
7. [Registo de progresso](#7-registo-de-progresso)

---

## 1. Como ler este roadmap

### 1.1 O que este roadmap é

Uma sequência ordenada de trabalho, dividida em fases e decomposta em etapas. Cada etapa é pequena o suficiente para ter um critério de aceitação verificável, e depende apenas de etapas anteriores.

O roadmap **não** é um plano de recursos. Não diz quando, nem com que equipas, nem quanto custa. Quem o lê deve conseguir responder a uma única pergunta por etapa: *isto pode começar já?*

### 1.2 O que este roadmap não é

- Não é um substituto da especificação. As decisões técnicas estão em `docs/Khnumn.md`; o roadmap apenas as ordena no tempo de execução.
- Não é um contrato de API. As interfaces entre módulos estão descritas em `docs/Khnumn.md` §6 e §18.3.
- Não fixa prioridades de negócio. A ordem aqui é a ordem *técnicamente possível*: uma etapa cujas dependências não estão implementadas não pode ser executada com rigor.

### 1.3 Convenções

| Elemento | Convenção |
|---|---|
| Identificador de fase | `F<n>` — corresponde a `docs/Khnumn.md` §22 |
| Identificador de etapa | `F<n>.E<m>` — única em todo o roadmap |
| Estado | `planeado`, `em desenvolvimento` ou `implementado` |
| Dependências | Lista de etapas que têm de estar `implementado` antes de esta começar |
| Critério de aceitação | Condição observável que decide a passagem a `implementado` |
| Referência | Secção de `docs/Khnumn.md`, ou de um dos anexos, que fundamenta a etapa |
| Caminho de referência | Caminho relativo à raiz do repositório, e não ao ficheiro que referencia |

A nomenclatura das fases é partilhada com `docs/Khnumn.md` §22, de propósito: há uma única taxonomia, não duas.

---

## 2. Estados e regras de transição

### 2.1 Os três estados

| Estado | Significado |
|---|---|
| `planeado` | A etapa está especificada e ordenada. Não foi iniciada. |
| `em desenvolvimento` | A implementação está em curso. A etapa não está concluída e os seus produtos não são considerados utilizáveis. |
| `implementado` | A etapa está concluída **e** o seu critério de aceitação foi verificado no ambiente de referência. |

### 2.2 Regras de transição

1. **Entrada em `em desenvolvimento`.** Todas as dependências declaradas estão `implementado`. Não há exceção: uma dependência não satisfeita invalida a ordem, porque o resultado seria construído sobre uma base instável.
2. **Passagem a `implementado`.** O critério de aceitação da etapa foi cumprido e verificado no ambiente de referência definido em `F0.E2`. Uma etapa cujo código compila mas cujo critério não foi verificado permanece `em desenvolvimento`.
3. **Sem saltos.** Uma etapa não pode passar diretamente de `planeado` a `implementado`.
4. **Regressão permitida.** Uma etapa pode regressar de `implementado` para `em desenvolvimento` se uma alteração posterior quebrar o seu critério de aceitação. A regressão e a sua causa ficam registadas em §7.
5. **Estado inicial.** Todas as etapas nascem em `planeado`, sem exceção, porque ainda não existe implementação.

### 2.3 O que conta como dependência

Uma dependência é uma relação técnica, não de conveniência. "Preciso do resultado de X" é uma dependência; "convém fazer X antes" não é. Quando uma dependência é apenas de conveniência, não é declarada, e as etapas ficam livremente ordenáveis entre si dentro da mesma fase.

---

## 3. Ordem de execução canónica

A lista plana e numerada de todas as etapas, pela ordem em que devem ser executadas. Nenhuma etapa da lista pode começar antes de as suas dependências estarem `implementado`.

| # | Etapa | Título | Depende de |
|---|---|---|---|
| 1 | `F0.E1` | Primeiro alvo de validação | — |
| 2 | `F0.E2` | Hardware de referência | `F0.E1` |
| 3 | `F0.E3` | Tolerâncias por classe de projeto | `F0.E1`, `F0.E2` |
| 4 | `F0.E4` | Protocolo de checkpoints | `F0.E1`, `F0.E3` |
| 5 | `F0.E5` | Modelo de metadados versionado | `F0.E1` |
| 6 | `F0.E6` | Política de falhas | — |
| 7 | `F0.E7` | Revisão de licenças e matriz de motores | — |
| 8 | `F0.E8` | Selecção e preparação do conjunto de dados | `F0.E1` |
| 9 | `F0.E9` | Linha de base manual | `F0.E3`, `F0.E7`, `F0.E8` |
| 10 | `F1.E1` | Esquema de metadados e validação | `F0.E5` |
| 11 | `F1.E2` | Estrutura de projeto e armazenamento local | `F0.E5` |
| 12 | `F1.E3` | CLI mínima | `F1.E2` |
| 13 | `F1.E4` | Inventário com hash | `F1.E1`, `F1.E3` |
| 14 | `F1.E5` | EXIF/XMP e campos ausentes | `F1.E1`, `F1.E4` |
| 15 | `F1.E6` | Normalização de datas, unidades e CRS | `F1.E1`, `F1.E5` |
| 16 | `F1.E7` | Quality gate de imagem | `F1.E4` |
| 17 | `F1.E8` | Relatório de lacunas e advertências | `F1.E6`, `F1.E7` |
| 18 | `F1.E9` | DAG in-memory com cache por hash | `F1.E2`, `F1.E4` |
| 19 | `F2.E1` | Adaptador do motor de SfM | `F1.E9`, `F0.E7` |
| 20 | `F2.E2` | Descritores e correspondências | `F2.E1` |
| 21 | `F2.E3` | Mapeamento esparso | `F2.E2` |
| 22 | `F2.E4` | Diagnóstico do modelo | `F2.E3` |
| 23 | `F2.E5` | Exportação de poses e nuvem esparsa | `F2.E3` |
| 24 | `F2.E6` | Testes com imagens de referência | `F2.E4`, `F0.E8` |
| 25 | `F3.E1` | Detecção de marcas: projeção inicial e refinamento | `F2.E5` |
| 26 | `F3.E2` | Filtro de consistência multivista | `F3.E1` |
| 27 | `F3.E3` | Revisão humana das deteções | `F3.E2` |
| 28 | `F3.E4` | Verificação de acquisibilidade do controlo | `F3.E1` |
| 29 | `F3.E5` | Ingestão de pontos de controlo com covariância | `F1.E1`, `F0.E4` |
| 30 | `F3.E6` | Similaridade de 7 parâmetros ponderada | `F3.E5`, `F2.E5` |
| 31 | `F3.E7` | Ajuste constrangido com pontos constantes | `F3.E6`, `F2.E3` |
| 32 | `F3.E8` | Propagação da incerteza por ensemble | `F3.E7` |
| 33 | `F3.E9` | Priors de pose GNSS | `F2.E1` |
| 34 | `F3.E10` | Ingestão e exclusão de checkpoints | `F3.E5`, `F0.E4` |
| 35 | `F3.E11` | Métricas de exatidão e estado de aceitação | `F3.E7`, `F3.E10` |
| 36 | `F3.E12` | Relatório de incerteza com decomposição | `F3.E8`, `F3.E11` |
| 37 | `F4.E1` | Adaptador do motor de MVS externo | `F2.E1`, `F0.E7` |
| 38 | `F4.E2` | Via de superfície esparsa e permissiva | `F2.E5` |
| 39 | `F4.E3` | Via de superfície densa em acelerador | `F2.E1` |
| 40 | `F4.E4` | Fusão de nuvens e filtragem | `F4.E3` |
| 41 | `F4.E5` | Processamento por blocos e controlo de RAM | `F4.E3` |
| 42 | `F4.E6` | Malha e texturização | `F4.E4` |
| 43 | `F4.E7` | Ortoimagem e ortorretificação | `F4.E2`, `F3.E11` |
| 44 | `F4.E8` | DTM e filtragem de solo | `F4.E4` |
| 45 | `F4.E9` | Refinamento iterativo da via densa em CPU | `F4.E1`, `F4.E3` |
| 46 | `F4.E10` | Validação contra a referência de acelerador | `F4.E9`, `F4.E3` |
| 47 | `F5.E1` | Classificador de cenário | `F1.E7` |
| 48 | `F5.E2` | Confiança e razões explicáveis | `F5.E1` |
| 49 | `F5.E3` | Correcção manual e registo | `F5.E2` |
| 50 | `F5.E4` | Planeador de pipeline com fallback | `F5.E3`, `F2.E1` |
| 51 | `F5.E5` | Escolha do caminho de superfície e orçamento | `F5.E4`, `F3.E8`, `F4.E2`, `F4.E3` |
| 52 | `F5.E6` | Função multiobjetivo e registo de decisões | `F5.E5` |
| 53 | `F6.E1` | Referência temporal e reconciliação de relógios | `F1.E6` |
| 54 | `F6.E2` | Extracção adaptativa de fotogramas | `F1.E4`, `F6.E1` |
| 55 | `F6.E3` | Convenção de instante de captura | `F6.E1` |
| 56 | `F6.E4` | Modelação de rolling shutter | `F6.E3`, `F2.E3` |
| 57 | `F6.E5` | Adaptador LiDAR e calibração entre sensores | `F1.E1`, `F2.E1` |
| 58 | `F6.E6` | Cor e calibração radiométrica | `F1.E6` |
| 59 | `F6.E7` | Adaptador de satélite | `F1.E6`, `F2.E1` |
| 60 | `F6.E8` | GNSS/IMU e sincronização | `F6.E1`, `F3.E9` |
| 61 | `F7.E1` | Persistência do DAG e recuperação | `F1.E9` |
| 62 | `F7.E2` | Scheduler CPU-first com backpressure | `F7.E1` |
| 63 | `F7.E3` | Workers remotos com capacidade anunciada | `F7.E2` |
| 64 | `F7.E4` | Retry, checkpoints e cache | `F7.E2` |
| 65 | `F7.E5` | Consistência numérica e tolerâncias | `F7.E2` |
| 66 | `F7.E6` | Autenticação e proteção do transporte | `F7.E3` |
| 67 | `F8.E1` | Representação de evidência por célula | `F3.E12` |
| 68 | `F8.E2` | Alinhamento de fontes | `F8.E1`, `F3.E7` |
| 69 | `F8.E3` | Compatibilidade temporal | `F8.E1` |
| 70 | `F8.E4` | Regra de decisão sobre evidência | `F8.E2`, `F8.E3` |
| 71 | `F8.E5` | Benchmarks contra baselines | `F8.E4` |

---

## 4. Fases e etapas

### Fase 0 — Definição experimental

Não produz código. Produz as decisões sem as quais nenhuma medição é interpretável, e o protocolo com que as medições se fazem.

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F0.E1` | Primeiro alvo de validação | — | implementado | Alvo escolhido e justificado: levantamento de drone RGB, com pontos de controlo e pontos de verificação independentes conhecidos | `docs/Khnumn.md` §27.2 |
| `F0.E2` | Hardware de referência | `F0.E1` | implementado | CPU, RAM, armazenamento, sistema operativo e acelerador especificados; se o acelerador for opcional, a sua ausência está definida | `docs/Khnumn.md` §27.2, `processos/protocolo-benchmark.md` §2 |
| `F0.E3` | Tolerâncias por classe de projeto | `F0.E1`, `F0.E2` | implementado | Tabela de tolerâncias preenchida, com a referência normativa aplicável a cada classe | `docs/Khnumn.md` §15.5, `processos/protocolo-benchmark.md` §6 |
| `F0.E4` | Protocolo de checkpoints | `F0.E1`, `F0.E3` | implementado | Método de medição, distribuição e critério de exclusão do ajuste definidos; número mínimo declarado | `docs/Khnumn.md` §15.2, `processos/protocolo-benchmark.md` §4 |
| `F0.E5` | Modelo de metadados versionado | `F0.E1` | implementado | CRS, unidades, convenções de eixos, timestamps, convenção de instante de captura e representação da incerteza fixados | `docs/Khnumn.md` §7, `docs/Khnumn.md` §5.6 |
| `F0.E6` | Política de falhas | — | implementado | Critérios de `PASS`, `PASS_WITH_WARNINGS`, `FAIL` e `NOT_VALIDATED` fixados, com as causas que os disparam | `docs/Khnumn.md` §15.4, §24.4 |
| `F0.E7` | Revisão de licenças e matriz de motores | — | implementado | Matriz de §18.2 revista, com auditoria de dependências transitivas por build e a política de núcleo livre de copyleft confirmada | `docs/Khnumn.md` §18.2, `processos/decisoes-motores.md` §1 |
| `F0.E8` | Selecção e preparação do conjunto de dados | `F0.E1` | implementado | Conjunto escolhido, com licença verificada, partições fixadas e hashes registados | `processos/protocolo-benchmark.md` §3 |
| `F0.E9` | Linha de base manual | `F0.E3`, `F0.E7`, `F0.E8` | implementado | Resultado de referência obtido por via manual, para servir de comparação com a implementação | `processos/protocolo-benchmark.md` §1.2 |
### Fase 1 — MVP de ingestão e inventário

Primeira fase com código. Constrói a cadeia de dados e a estrutura de controlo que todas as fases seguintes reutilizam.

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F1.E1` | Esquema de metadados e validação | `F0.E5` | implementado | Esquema versionado, validação implementada e rejeição de registos inválidos com mensagem accionável | `docs/Khnumn.md` §7.1, §7.2 |
| `F1.E2` | Estrutura de projeto e armazenamento local | `F0.E5` | implementado | Projecto persistido, com catálogo de activos e estado recuperável entre execuções | `docs/Khnumn.md` §7.1 |
| `F1.E3` | CLI mínima | `F1.E2` | implementado | Comando de ingestão executável, com código de saída significativo e saída legível por máquina | `docs/Khnumn.md` §19.1 |
| `F1.E4` | Inventário com hash | `F1.E1`, `F1.E3` | implementado | Descoberta, hash criptográfico, formato, tamanho e data registados, com os originais preservados | `docs/Khnumn.md` §8.1, §7.3 |
| `F1.E5` | EXIF/XMP e campos ausentes | `F1.E1`, `F1.E4` | implementado | Metadados do fornecedor lidos sem lhes atribuir verdade automática; ausências registadas | `docs/Khnumn.md` §8.1, §8.2 |
| `F1.E6` | Normalização de datas, unidades e CRS | `F1.E1`, `F1.E5` | implementado | Valores normalizados, valores de origem preservados, convenção de instante de captura declarada | `docs/Khnumn.md` §5.6, §8.1 |
| `F1.E7` | Quality gate de imagem | `F1.E4` | implementado | Nitidez, exposição, saturação, ruído, duplicados e quase-duplicados avaliados, com a advertência de que nenhuma métrica isolada decide a usabilidade | `docs/Khnumn.md` §8.3 |
| `F1.E8` | Relatório de lacunas e advertências | `F1.E6`, `F1.E7` | implementado | Relatório emitido com todas as lacunas, e sem omissão silenciosa de campos ausentes | `docs/Khnumn.md` §8.1, §19.2 |
| `F1.E9` | DAG in-memory com cache por hash | `F1.E2`, `F1.E4` | implementado | Tarefas versionadas e reexecutáveis, cache por hash de entradas, parâmetros e versões, e invalidação correta | `docs/Khnumn.md` §6.2, §16.4 |
### Fase 2 — Primeiro pipeline SfM

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F2.E1` | Adaptador do motor de SfM | `F1.E9`, `F0.E7` | implementado | Interface `run`, `inspect`, `cancel`, `collect_metrics`, `export` implementada; versão do motor e parâmetros registados em cada tarefa | `docs/Khnumn.md` §18.3, `processos/decisoes-motores.md` ADR-001 |
| `F2.E2` | Descritores e correspondências | `F2.E1` | implementado | Extracção e correspondência executadas pelo motor, com as opções de descritor e de correspondente registadas | `docs/Khnumn.md` §11.1, §11.2 |
| `F2.E3` | Mapeamento esparso | `F2.E2` | implementado | Poses e nuvem esparsa estimadas, com o gauge fixado explicitamente na parametrização | `docs/Khnumn.md` §11.3, §11.4 |
| `F2.E4` | Diagnóstico do modelo | `F2.E3` | implementado | Relatório com câmaras, pontos, reprojeção, componentes desconexos, observações rejeitadas e indicadores de degenerescência | `docs/Khnumn.md` §11.5 |
| `F2.E5` | Exportação de poses e nuvem esparsa | `F2.E3` | implementado | Formatos exportados com CRS, unidades e proveniência preservados | `docs/Khnumn.md` §19.2 |
| `F2.E6` | Testes com imagens de referência | `F2.E4`, `F0.E8` | implementado | Reconstrução reproduzível dentro das tolerâncias estabelecidas, com as limitações explicitadas | `docs/Khnumn.md` §21.1, §22 Fase 2 |
### Fase 3 — Controlo, georreferenciação e validação

A fase mais densa do roadmap, e a que decide se o sistema pode fazer afirmações de exatidão. A ordem interna reflecte uma dependência técnica real: a deteção de marcas precede o controlo, o controlo precede a propagação, e a propagação precede o relatório de incerteza.

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F3.E1` | Detecção de marcas: projeção inicial e refinamento | `F2.E5` | planeado | Marcas circulares detectadas por refinamento local em sub-píxel, a partir da projeção das coordenadas de terreno; erro medido em píxeis | `docs/Khnumn.md` §5.7, `processos/decisoes-motores.md` ADR-008 |
| `F3.E2` | Filtro de consistência multivista | `F3.E1` | planeado | Detecções rejeitadas quando inconsistentes com a reprojeção noutra imagem; falsos positivos medidos | `docs/Khnumn.md` §5.7 |
| `F3.E3` | Revisão humana das deteções | `F3.E2` | planeado | Detecções sobrepostas à imagem e confirmáveis; aceitações e rejeições registadas | `docs/Khnumn.md` §5.7, §2.1 |
| `F3.E4` | Verificação de acquisibilidade do controlo | `F3.E1` | planeado | Dimensão aparente, contraste, obstrução e número de imagens por marca verificados antes do processamento, com a falha comunicada com a causa | `docs/Khnumn.md` §8.4 |
| `F3.E5` | Ingestão de pontos de controlo com covariância | `F1.E1`, `F0.E4` | planeado | Covariância 3×3, método, instrumento, data e operador obrigatórios; ausência de covariância tratada como erro de configuração | `docs/Khnumn.md` §7.1, §7.2, §10.4 |
| `F3.E6` | Similaridade de 7 parâmetros ponderada | `F3.E5`, `F2.E5` | planeado | Transformação estimada com pesos inversos à variância e limiar do estimador robusto escalado pela incerteza | `docs/Khnumn.md` §10.4, `processos/decisoes-motores.md` ADR-007 |
| `F3.E7` | Ajuste constrangido com pontos constantes | `F3.E6`, `F2.E3` | planeado | Posições de levantamento fixadas como pontos constantes, gauge fixado por três pontos, ajuste executado com os pontos fixos | `docs/Khnumn.md` §10.4, `processos/decisoes-motores.md` ADR-006 |
| `F3.E8` | Propagação da incerteza por ensemble | `F3.E7` | planeado | Etapa final executada N vezes com perturbação das coordenadas pela covariância; dispersão obtida e número de amostras registado | `docs/Khnumn.md` §10.4, `processos/decisoes-motores.md` ADR-007 |
| `F3.E9` | Priors de pose GNSS | `F2.E1` | planeado | Priors de posição extraídos dos metadados e aplicados no ajuste, com a covariância declarada e sobreponível | `docs/Khnumn.md` §10.4 |
| `F3.E10` | Ingestão e exclusão de checkpoints | `F3.E5`, `F0.E4` | planeado | Pontos de verificação lidos apenas pelo validador, depois do modelo congelado; a exclusão é imposta pelo carregamento e não por convenção | `docs/Khnumn.md` §15.2, `processos/protocolo-benchmark.md` §4.1 |
| `F3.E11` | Métricas de exatidão e estado de aceitação | `F3.E7`, `F3.E10` | planeado | RMSE horizontal, vertical e tridimensional, erro médio, percentis e regra do *blunder* calculados; estado emitido com a causa | `docs/Khnumn.md` §15.1, §15.4, §15.5 |
| `F3.E12` | Relatório de incerteza com decomposição | `F3.E8`, `F3.E11` | planeado | Incerteza total decomposta nas parcelas de controlo e de cena, com a fração de controlo declarada | `docs/Khnumn.md` §15.3, `processos/protocolo-benchmark.md` §4.7 |
### Fase 4 — Reconstrução densa e produtos 3D

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F4.E1` | Adaptador do motor de MVS externo | `F2.E1`, `F0.E7` | planeado | Processo externo invocado pela interface de adaptador, com aviso de licença no primeiro uso e formatos trocados documentados | `docs/Khnumn.md` §18.3, `processos/decisoes-motores.md` ADR-002 |
| `F4.E2` | Via de superfície esparsa e permissiva | `F2.E5` | planeado | Triangulação sobre a nuvem esparsa executada, sem dependências com copyleft, e origem declarada no produto | `docs/Khnumn.md` §13.1, `processos/decisoes-motores.md` ADR-005 |
| `F4.E3` | Via de superfície densa em acelerador | `F2.E1` | planeado | Mapas de profundidade e fusão executados no motor de referência, com a consistência geométrica multivista activa | `docs/Khnumn.md` §13.1 |
| `F4.E4` | Fusão de nuvens e filtragem | `F4.E3` | planeado | Nuvem densa filtrada por consistência entre vistas, ângulo de observação, textura, oclusão e incerteza | `docs/Khnumn.md` §13.1 |
| `F4.E5` | Processamento por blocos e controlo de RAM | `F4.E3` | planeado | Processamento por blocos com margem de contexto e fusão de fronteiras determinística, dentro do orçamento de memória declarado | `docs/Khnumn.md` §16.1, §16.3 |
| `F4.E6` | Malha e texturização | `F4.E4` | planeado | Malha e textura geradas com unidades, orientação, escala e origem preservadas; a simplificação declara se alterou medidas | `docs/Khnumn.md` §13.4 |
| `F4.E7` | Ortoimagem e ortorretificação | `F4.E2`, `F3.E11` | planeado | Ortoimagem produzida com o modelo de superfície, o CRS de destino e o método de reamostragem registados; descontinuidade de costura verificada | `docs/Khnumn.md` §13.5, §15.5 |
| `F4.E8` | DTM e filtragem de solo | `F4.E4` | planeado | Classificação de solo executada como etapa autónoma, com as zonas medidas, interpoladas e desconhecidas distinguidas | `docs/Khnumn.md` §13.3 |
| `F4.E9` | Refinamento iterativo da via densa em CPU | `F4.E1`, `F4.E3` | planeado | Ciclo com priori da iteração anterior, paragem por autoconvergência, orçamento declarado e retenção da melhor iteração | `docs/Khnumn.md` §13.1, `processos/decisoes-motores.md` ADR-009 |
| `F4.E10` | Validação contra a referência de acelerador | `F4.E9`, `F4.E3` | planeado | Densidade, completude, distância ponto-superfície e taxa de outliers comparadas por sub-região com a referência, dentro dos limiares declarados | `processos/protocolo-benchmark.md` §6.1 |
### Fase 5 — Planeador e deteção de cenário

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F5.E1` | Classificador de cenário | `F1.E7` | planeado | Classes candidatas e confiança estimada a partir de sinais observáveis, com as razões registadas | `docs/Khnumn.md` §9.1, §9.2 |
| `F5.E2` | Confiança e razões explicáveis | `F5.E1` | planeado | Confiança acompanhada das razões que a supportam, e nenhum indício usado sem calibração conhecida | `docs/Khnumn.md` §9.2, §11.6 |
| `F5.E3` | Correcção manual e registo | `F5.E2` | planeado | Correcção do utilizador com prioridade sobre a sugestão, e a decisão final registada com o seu motivo | `docs/Khnumn.md` §9.2, §2.1 |
| `F5.E4` | Planeador de pipeline com fallback | `F5.E3`, `F2.E1` | planeado | Pipeline escolhido entre candidatos compatíveis, com fallback declarado e a razão de cada alternativa rejeitada | `docs/Khnumn.md` §6.1, §24.2 |
| `F5.E5` | Escolha do caminho de superfície e orçamento | `F5.E4`, `F3.E8`, `F4.E2`, `F4.E3` | planeado | Caminho de superfície escolhido segundo a capacidade do host e o requisito de densidade; orçamento do ensemble e das iterações fixado antes da execução | `docs/Khnumn.md` §13.1, §9.3, §16.3 |
| `F5.E6` | Função multiobjetivo e registo de decisões | `F5.E5` | planeado | Custos estimados, plano materializado em grafo versionado, e todas as decisões registadas com a sua razão | `docs/Khnumn.md` §9.3, §6.2, §24.2 |
### Fase 6 — Vídeo e sensores auxiliares

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F6.E1` | Referência temporal e reconciliação de relógios | `F1.E6` | planeado | Desvio de segundos intercalares aplicado e declarado; convenção de tempo documentada; deriva do relógio da câmara detectada | `docs/Khnumn.md` §5.6 |
| `F6.E2` | Extracção adaptativa de fotogramas | `F1.E4`, `F6.E1` | planeado | Fotogramas seleccionados por deslocamento, nitidez, paralaxe, sobreposição e mudança de perspectiva, com política de memória limitada | `docs/Khnumn.md` §12 |
| `F6.E3` | Convenção de instante de captura | `F6.E1` | planeado | Início, meio ou fim da exposição declarado e aplicado de forma consistente | `docs/Khnumn.md` §5.6 |
| `F6.E4` | Modelação de rolling shutter | `F6.E3`, `F2.E3` | planeado | Modelo por tempo de linha implementado apenas com caso de uso claro e teste de referência; caso contrário, o risco é sinalizado | `docs/Khnumn.md` §10.2 |
| `F6.E5` | Adaptador LiDAR e calibração entre sensores | `F1.E1`, `F2.E1` | planeado | Nuvens de pontos ingeridas com sistema de coordenadas, calibração entre sensores, densidade, padrão de varrimento e incerteza registados | `docs/Khnumn.md` §5.5 |
| `F6.E6` | Cor e calibração radiométrica | `F1.E6` | planeado | Perfis ICC aplicados; vinheta e sombreamento corrigidos quando calibráveis; calibração a reflectância disponível em multibanda | `docs/Khnumn.md` §5.1 |
| `F6.E7` | Adaptador de satélite | `F1.E6`, `F2.E1` | planeado | Modelo geométrico identificado; viés de RPC estimado e corrigido; co-registação, máscara de nuvem e reflectância de superfície tratados | `docs/Khnumn.md` §5.3 |
| `F6.E8` | GNSS/IMU e sincronização | `F6.E1`, `F3.E9` | planeado | Integração de poses GNSS/IMU com a covariância e a sincronização temporal, e os resíduos de alinhamento medidos | `docs/Khnumn.md` §14.1, §21.2 |
### Fase 7 — Distribuição

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F7.E1` | Persistência do DAG e recuperação | `F1.E9` | planeado | Grafo persistido, retomável após interrupção, e os produtos intermediários preservados | `docs/Khnumn.md` §6.2, §22 Fase 7 |
| `F7.E2` | Scheduler CPU-first com backpressure | `F7.E1` | planeado | Limites globais impostos, backpressure aplicado, e tarefas de memória elevada não executadas em excesso | `docs/Khnumn.md` §16.3, §17.1 |
| `F7.E3` | Workers remotos com capacidade anunciada | `F7.E2` | planeado | Capacidade de cada worker anunciada e usada na escolha; a ausência de acelerador não bloqueia tarefas com via em CPU | `docs/Khnumn.md` §17.4 |
| `F7.E4` | Retry, checkpoints e cache | `F7.E2` | planeado | Estratégia de retry com estados legíveis, retomada a partir de checkpoint, e idempotência verificada | `docs/Khnumn.md` §17.2, §17.3 |
| `F7.E5` | Consistência numérica e tolerâncias | `F7.E2` | planeado | Nível de reprodutibilidade exigido declarado, com a tolerância explícita por backend de ajuste | `docs/Khnumn.md` §17.5, `processos/decisoes-motores.md` §3 |
| `F7.E6` | Autenticação e proteção do transporte | `F7.E3` | planeado | Pedidos autenticados, transporte protegido, permissões mínimas nos workers e credenciais separadas dos ficheiros de projeto | `docs/Khnumn.md` §20 |
### Fase 8 — Fusão heterogénea avançada

| ID | Etapa | Depende de | Estado | Critério de aceitação | Referência |
|---|---|---|---|---|---|
| `F8.E1` | Representação de evidência por célula | `F3.E12` | planeado | Estimativa geométrica, covariância, contagem e diversidade de observações, proveniência, época e indicadores de consistência por elemento espacial | `docs/Khnumn.md` §14.4 |
| `F8.E2` | Alinhamento de fontes | `F8.E1`, `F3.E7` | planeado | Fontes alinhadas com modelos geométricos adequados e restrições explícitas, sem transformações não rígidas aplicadas por aparência | `docs/Khnumn.md` §14.1, §13.2 |
| `F8.E3` | Compatibilidade temporal | `F8.E1` | planeado | Janela de compatibilidade calculada ou recebida, e mudanças prováveis marcadas sem fusão silenciosa | `docs/Khnumn.md` §14.2 |
| `F8.E4` | Regra de decisão sobre evidência | `F8.E2`, `F8.E3` | planeado | Regras explícitas de aceitação, rejeição e múltiplas hipóteses, testadas contra conjuntos de referência | `docs/Khnumn.md` §14.4 |
| `F8.E5` | Benchmarks contra baselines | `F8.E4` | planeado | Comparação com baselines estabelecidos em conjuntos públicos e próprios, com o critério de inovação própria aplicado | `docs/Khnumn.md` §21.3, §27.2 |
---

## 5. Temas transversais

Estes temas atravessam todas as fases. Não são etapas, porque não têm um momento único de execução, mas cada fase tem de os tratar.

| Tema | Onde é tratado | Referência |
|---|---|---|
| **Proveniência** | Todas as fases. Cada produto declara a sua origem, as operações que o produziram e as versões que o produziram | `docs/Khnumn.md` §7.3 |
| **Incerteza como dado** | Fases 3, 4 e 8. Nenhum produto é emitido sem a sua incerteza, ou sem a declaração de que a incerteza não foi estimada | `docs/Khnumn.md` §3.2, §15.3 |
| **Separação de controlo e verificação** | Fase 3. Os pontos de verificação nunca entram no ajuste, e a exclusão é imposta pelo carregamento | `docs/Khnumn.md` §15.2 |
| **Reprodutibilidade** | Fases 1, 3 e 7. Sementes, versões, parâmetros e hashes registados; o nível exigido é declarado | `docs/Khnumn.md` §20, `processos/protocolo-benchmark.md` §8 |
| **Orçamento de recursos** | Fases 1, 4, 5 e 7. Nenhuma tarefa executa sem declaração de memória, tempo, threads e espaço temporário | `docs/Khnumn.md` §16.3 |
| **Segurança e integridade** | Fases 1 e 7. Validação de entradas externas, sanitização de caminhos, permissões mínimas e inventário de licenças | `docs/Khnumn.md` §20 |
| **Testabilidade** | Todas as fases. Cada etapa tem critério de aceitação verificável no ambiente de referência | `processos/protocolo-benchmark.md` §1.2 |
| **Observabilidade** | Fases 1 e 7. Logs estruturados, estado e progresso por tarefa, e métricas por etapa | `docs/Khnumn.md` §17.2 |
| **Honestidade do estado** | Todas as fases. `NOT_VALIDATED` é um estado legítimo e preferível a um `PASS` injustificado | `docs/Khnumn.md` §15.4, §27.2 |

---

## 6. Itens deliberadamente adiados

Itens que ficam **fora** do roadmap nesta fase, com o motivo. A listagem é explícita para que a ausência de um item seja uma decisão registada e não um esquecimento.

| Item | Motivo |
|---|---|
| **SAR e InSAR** | Medem retrodispersão coerente e exigem modelos próprios, com decomposição de fase que nada no roadmap aborda. O sistema trata SAR como classe de cenário a ser encaminhada, não como fonte de reconstrução | `docs/Khnumn.md` §2.3, §5.4 |
| **Hiperspectral** |Centenas de bandas com radiometria própria. A calibração radiométrica de `F6.E6` é o pré-requisito, e o caso de uso não está fixado | `docs/Khnumn.md` §5.4 |
| **Reconstrução aprendida na cadeia de produção** | Escala ambígua, confiança não calibrada e alucinação de geometria. Mantida apenas como candidata, sob verificação geométrica clássica | `docs/Khnumn.md` §11.6 |
| **SLAM/VIO integrado** | Útil para a trajetória em tempo real, mas não é reconstrução global. A distinção está conceptualmente resolvida; a integração não | `docs/Khnumn.md` §12 |
| **Motor de MVS próprio em PyTorch** | A completude medida é da ordem de quarenta vezes inferior à da via aceleradora, e é implementação própria contra o princípio de reutilizar. Fica como alternativa a reavaliar se o motor externo não for aceitável | `processos/decisoes-motores.md` §6.1 |
| **Camada de ajuste própria com prior ponderado** | Escalada de `ADR-007`. Só se justifica se uma medição comparativa mostrar que o ensemble é instável ou demasiado caro | `processos/decisoes-motores.md` ADR-007 |
| **3D Tiles e I3S** | Formatos de visualização e distribuição. O núcleo não tem dependência de um formato de exibição | `docs/Khnumn.md` §19.2 |
| **Multi-sessão e incremento de grandes coleções** | A fase 7 trata a distribuição de uma coleção, não o crescimento incremental de um modelo ao longo de campanhas sucessivas | `docs/Khnumn.md` §17.1 |
| **Mosaicos de grandes áreas com reprocessamento** | A composição de mosaicos existe, mas a gestão de sobreposições entre mosaicos de campanhas distintas não está especificada | `docs/Khnumn.md` §13.5 |
| **Contribuição de fluxo de pontos de controlo ao motor de referência** | O mecanismo existe e é usado, mas a manutenção de uma bifurcação do motor seria um custo permanente sem retorno imediato | `processos/decisoes-motores.md` §6.2 |

---

## 7. Registo de progresso

Cada linha regista uma mudança de estado, com a data e a causa. A primeira coluna é a etapa, a segunda o estado atingido, e a terceira o motivo.

| Etapa | Estado | Data | Motivo |
|---|---|---|---|
| `F0.E1` | `implementado` | 2026-10-21 | Alvo de validação fixado: levantamento de drone RGB como alvo primário, ETH3D `terrace` como conjunto verificável, e o que cada um não valida declarado. Registo em `processos/alvo-validacao.md` |
| `F0.E2` | `implementado` | 2026-10-21 | Hardware de referência medido e declarado, com orçamento de 500 MiB e 300 MiB de folga, e as consequências desse orçamento registadas. Registo em `processos/hardware-referencia.md` e §2 do protocolo |
| `F0.E3` | `implementado` | 2026-10-21 | Três classes de projeto com tolerâncias, GSD, completude e referência normativa. §6 do protocolo |
| `F0.E4` | `implementado` | 2026-10-21 | Método de medição, distribuição, exclusão e número mínimo de checkpoints fixados, com esquema de ponto de controlo. §4 do protocolo e `schemas/controlo-v1.schema.json` |
| `F0.E5` | `implementado` | 2026-10-21 | Modelo de metadados versionado: esquema, ausência explícita, unidade explícita, representação da incerteza. `docs/modelo-metadados.md` e `schemas/` |
| `F0.E6` | `implementado` | 2026-10-21 | Política de falhas fixada, com a distinção entre estado de tarefa e estado de produto. `processos/politica-falhas.md` |
| `F0.E7` | `implementado` | 2026-10-21 | Auditoria de licenças feita por build: núcleo livre de copyleft forte, verificado sobre a árvore compilada. `processos/auditoria-licencas.md` e `processos/sbom.json` |
| `F0.E8` | `implementado` | 2026-10-21 | Conjunto escolhido com licença verificada, partições fixadas por regra determinística e hashes registados. `manifests/conjuntos.yaml` e `manifests/hashes.yaml` |
| `F0.E9` | `implementado` | 2026-10-21 | Linha de base obtida pela via directa do motor, com pré-processamento declarado, e dois achados registados: a prévia de focagem não é reconciliada com a redução de resolução, e a partição por índice fragmenta a conectividade. `processos/linha-base.md` |
| `F1.E1` | `implementado` | 2026-10-21 | Esquemas versionados, validação no núcleo e na camada científica, com corpus de casos inválidos partilhado |
| `F1.E2` | `implementado` | 2026-10-21 | Projecto persistido com catálogo SQLite e estado recuperável entre execuções |
| `F1.E3` | `implementado` | 2026-10-21 | CLI executável com saída legível por máquina e códigos de saída significativos |
| `F1.E4` | `implementado` | 2026-10-21 | Inventário com hash SHA-256, formato, tamanho e data, com os originais preservados e os duplicados exactos identificados |
| `F1.E5` | `implementado` | 2026-10-21 | Leitura de EXIF e XMP em Python puro, com os metadados do fornecedor registados como declarados e as ausências contadas |
| `F1.E6` | `implementado` | 2026-10-21 | Datas, unidades e CRS normalizados, com os valores de origem preservados e a convenção de instante de captura declarada |
| `F1.E7` | `implementado` | 2026-10-21 | Quality gate com nitidez, exposição, saturação, ruído, duplicados e quase-duplicados, e a advertência de que nenhuma métrica isolada decide |
| `F1.E8` | `implementado` | 2026-10-21 | Relatório de lacunas e advertências emitido, sem omissão silenciosa |
| `F1.E9` | `implementado` | 2026-10-21 | DAG em memória com cache por hash, com invalidação verificada e tarefa dependente de uma falha marcada `BLOCKED` |
| `F2.E1` | `implementado` | 2026-10-21 | Adaptador do motor implementado com a interface de §18.3, as três fases separadas em tarefas distintas, os parâmetros registados por tarefa e o limite de memória declarado. Verificado de ponta a ponta pela CLI: `processos/execucoes/sfm-eth3d-terrace.json` |
| `F2.E2` | `implementado` | 2026-10-21 | Extracção e correspondência executadas pelo motor, com as opções registadas. Medido: o pico da extracção é quadrático na resolução, e é o que fixa a resolução de trabalho. Os descritores aprendidos ficam de fora, por não haver medição do seu custo em memória |
| `F2.E3` | `implementado` | 2026-10-21 | Mapeamento esparso com o gauge fixado explicitamente na parametrização: par inicial declarado e primeira câmara mantida constante, com o gauge registado no produto |
| `F2.E4` | `implementado` | 2026-10-21 | Diagnóstico do modelo com câmaras, pontos, reprojecção, observações rejeitadas, componentes desconexas e indicadores de degenerescência, com a distinção explícita entre a liberdade de gauge e a observabilidade da cena |
| `F2.E5` | `implementado` | 2026-10-21 | Exportação das poses, da nuvem esparsa e do modelo, com o CRS, as unidades e a proveniência preservados |
| `F2.E6` | `implementado` | 2026-10-21 | Comparação com a linha de base manual: coincidência exacta em todas as métricas, com as limitações declaradas e o estado `NOT_VALIDATED`. Registo em `processos/comparacao-sfm.md` |

O registo é acumulativo e acompanha o projeto. Uma regressão de estado é registada como uma nova linha, com a causa, e não apaga a linha anterior.

---

## Nota de âmbito

Este roadmap não substitui a nota de rigor de `docs/Khnumn.md`. A exatidão alcançável por qualquer implementação que siga esta ordem depende ainda da resolução, calibração, geometria de captura, georreferenciação, qualidade dos dados e de validação independente, e nenhuma ordem de implementação altera isso.
