# Khnumn — Alvo de validacao

**Âmbito:** este registo fixa o primeiro alvo de validacao do Khnumn, os alvos
secundarios por funcao, e o que cada um deles serve e o que **nao** serve.
Corresponde a etapa `F0.E1` de `docs/ROADMAP.md`.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Decisão datada de 2026-10-21, à luz de
`docs/Khnumn.md` §27.2 item 1 e §21.2; revisto em 2026-10-22.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-22 · **Idioma:** Português europeu

---

## 1. Como este alvo foi escolhido

O critério de selecção não é a notoriedade do conjunto de dados. O critério é
a existência de **referência independente com exatidão documentada**, porque
é essa referência que permite distinguir uma afirmação de exatidão de uma
imagem visualmente convincente (`docs/Khnumn.md` §21.2).

Três condições foram impostas, e elas retiram a maior parte das opções:

| Condição | Consequência |
|---|---|
| A referência tem de medir **exatidão absoluta** | Só um levantamento com pontos medidos por topografia valida a georreferenciação. Nenhum conjunto público de SfM valida isso |
| A execução tem de caber no ambiente de referência | O orçamento de 500 MiB com 300 MiB de folga, em CPU, sem acelerador, limita o número de imagens e a sua resolução |
| A cadeia tem de ser executável de ponta a ponta | A fase de controlo com pontos de controlo medidos é fase 3, e o alvo tem de a suportar quando ela chegar |

## 2. Alvo primário — levantamento de drone RGB com controlo no terreno

**Escolha:** levantamento aéreo por drone, com imagens RGB de seguimento
nadirais e oblíquos sobre um terreno com pontos de controlo e pontos de
verificação independentes, medidos por topografia de alta precisão.

É o único tipo de conjunto que valida simultaneamente a reconstrução, a
georreferenciação e a exatidão absoluta, e por isso é o alvo primário.

### 2.1 Características exigidas

| Característica | Exigência | Razão |
|---|---|---|
| Número de imagens | 80 a 150 | A cobertura tem de permitir a ligação de vistas; acima de ~150 o ajuste global e a correspondência saem do orçamento de memória |
| Sobreposição frontal | 70 % a 80 % | Abaixo de 60 % o grafo de vistas fragmenta-se; o valor é o usual em levantamento de drone |
| Sobreposição lateral | 50 % a 60 % | Complementa a frontal; a oblique acrescenta a coverage lateral |
| GSD no terreno | 2 cm a 3 cm | Define a classe de projeto `levantamento_agricola_rtk` (`F0.E3`) |
| Marcas de controlo | Alvos circulares simétricos, 20 a 30 px de diagonal na imagem | `docs/Khnumn.md` §5.7 e ADR-008: abaixo de ~20 px o erro de deteção cresce depressa; a verificação da GSD contra o tamanho do alvo é feita **antes** do voo |
| Pontos de controlo | 8 a 15, espalhados, com covariância 3×3 declarada | O número tem de permitir a fixação do gauge por três pontos e a ponderação por variância |
| Pontos de verificação | **30 ou mais**, independentes, medidos com instrumento diferente | `docs/Khnumn.md` §15.5: abaixo de trinta, a avaliação é exploratória e o estado não pode ser `PASS` |
| Datum e CRS de destino | ETRS89 e EPSG respetivo, ou outro datum com transformação validada | `docs/Khnumn.md` §10.3: uma transformação de datum sem verificar a área, a época e a grelha é uma suposição |

### 2.2 Estado da aquisição

A aquisição do alvo primário **ainda não está realizada**. Enquanto não
estiver, as Fases 1 e 2 são executadas e verificadas com os conjuntos
públicos de §3, e o alvo primário entra no momento em que a cadeia de
controlo da Fase 3 precisar de ele.

**Informação a fornecer pelo responsável do levantamento, para fechar `F0.E1`:**

- data e hora da aquisição, e a hora real por voo;
- número de imagens por tipo (nadir, oblíquo);
- GSD real medido no terreno;
- ficha das marcas de controlo: número, coordenadas, datum, método, instrumento, data, operador e covariância 3×3;
- ficha dos pontos de verificação, com a mesma informação e a garantia de que não entraram no ajuste;
- CRS de destino e a razão de datum.

### 2.3 Por que a ordem é a que é

O alvo primário não é o primeiro a ser executado. Executá-lo primeiro exigiria
construir georreferenciação antes de haver instrumentação, e a primeira
medição seria uma medição de um sistema por calibrar. A ordem adotada é
inverter: primeiro uma cadeia verificável sobre dados com referência
conhecida, depois o alvo que exige a cadeia completa.

## 3. Alvos secundários, por função

Cada conjunto cobre uma pergunta diferente. A correspondência entre
pergunta e conjunto é a que permite decidir o que uma execução está a
responder (`processos/protocolo-benchmark.md` §3.2).

| Conjunto | Pergunta que serve | Referência | O que **não** valida | Regime |
|---|---|---|---|---|
| **LaMAR** | Robustez de SfM em grande escala e em sequências | Verdade-fundamento de SfM e marcas | Escala geodésica, datum e exatidão absoluta | Capturas de AR, não de drone; serve de referência de comparacao, não de alvo |
| **Tanks&Temples** | Volume, velocidade e completude em grande escala | Trajectória e avaliação qualitativa | Sem verdade-fundamento densa | Uso interno, conforme licença |
| **ETH3D** | Qualidade da reconstrução densa e da texturização; qualidade da rasterização de superfície | Varrimentos de laser, e mapas de profundidade renderizados a partir deles | Escala e datum | Fase 4 para a superfície; Fase 9 para a rasterização, em parte executável neste ambiente; no conjunto `terrace`, a via densa não é executável no ambiente de referência actual |
| **DTU** | Exactidão densa em cenário controlado | Nuvens de luz estruturada | Escala reduzida, cenário artificial | Fase 4 |
| **ISPRS Vaihingen / Potsdam** | Classificação de solo e produção de DTM | Rótulos de classes | Cobertura aérea, não SfM | Fase 4 |
| **Campo de ensaio próprio** | Georreferenciação e exatidão absoluta da cadeia completa | Pontos medidos por topografia | — | Alvo primário, §2 |

### 3.1 Regra sobre o que um conjunto público não pode concluir

Nenhum conjunto público de SfM permite concluir que o produto é
georreferenciado com exatidão absoluta. Todos eles podem concluir que a
reconstrução é **internamente consistente** e, quando têm verdade-fundamento
de SfM, que a pose está correcta **no referencial da cena**.

Consequência directa: as execuções da Fase 2 sobre conjuntos públicos
terminam em `NOT_VALIDATED`, e não em `PASS`. `NOT_VALIDATED` é um estado
legítimo e preferível a um `PASS` injustificado (`docs/Khnumn.md` §15.4).

### 3.2 A verdade-fundamento da rasterização, no ETH3D

A rasterização de `docs/Khnumn.md` §13.6 introduz uma pergunta que os
conjuntos de SfM não costumam responder: a projecção está correcta? Um raster
pode ser geometricamente errado e parecer razoável, e a plausibilidade visual
não é uma métrica.

O conjunto ETH3D responde a essa pergunta com três ficheiros de
verdade-fundamento da cena `terrace`, que não estão instalados e que passam a
ser declarados em `manifests/conjuntos.yaml`:

| Ficheiro | O que é | O que permite concluir |
|---|---|---|
| `terrace_scan_clean.7z` | Nuvem de varrimento laser, com os outliers removidos | Distância ponto-superfície da superfície reconstruída, e completude |
| `terrace_dslr_scan_eval.7z` | O mesmo varrimento, restrito aos pontos observados por duas ou mais imagens | A comparação justa para avaliação MVS, em que os pontos nunca observados não penalizam a completude |
| `terrace_dslr_depth.7z` | Mapas de profundidade renderizados a partir do varrimento | O campo de profundidade do rasterizador, comparado **pixel a pixel** com a verdade-fundamento |

O terceiro é o mais forte dos três: ele verifica a projecção e o rasterizador
ao mesmo tempo, e não a qualidade da reconstrução. Uma divergência entre o
campo de profundidade rasterizado e o campo de verdade-fundamento é
localizável ao píxel, e distingue um erro de projecção de um erro de
geometria.

O que esta verdade-fundamento **não** valida, e o que se mantém: o `terrace`
não tem datum de levantamento, e portanto o estado de aceitação dos produtos
que dele derivam continua a ser `NOT_VALIDATED`. O que se ganha é a validação
da **projecção**, que é interna, e não da exatidão posicional, que é externa.

## 4. Rastreabilidade

| Item | Valor |
|---|---|
| Decisão | Alvo primário: levantamento de drone RGB com controlo no terreno |
| Data | 2026-10-21; revisto em 2026-10-22 |
| Etapa | `F0.E1` de `docs/ROADMAP.md` |
| Referência | `docs/Khnumn.md` §27.2 item 1, §21.2, §5.7, §13.6 |
| Revisão de 2026-10-22 | Acrescentada a verdade-fundamento da rasterização no ETH3D, e o que ela valida e o que não valida (§3.2) |
| Pendência | Parâmetros de aquisição e fichas de controlo e verificação (§2.2) |
| Efeito no roadmap | Nenhum: a ordem de execução das etapas não muda |

---

**Nota de âmbito:** o alvo de validação fixa o que vai ser medido. Não fixa
o que vai ser acertado. A exatidão alcançável depende ainda da resolução,
calibração, geometria de captura, georreferenciação, qualidade dos dados e
validação independente, e nenhuma ordem de implementação altera isso.
