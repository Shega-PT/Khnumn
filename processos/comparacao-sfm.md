# Khnumn — Comparação da reconstrução esparsa

**Âmbito:** este registo compara o resultado obtido pela via manual do motor
com o resultado obtido pela implementação do Khnumn, sobre os mesmos
ficheiros, com a mesma configuração, e regista o que a comparação mostra.
Corresponde a etapa `F2.E6` de `docs/ROADMAP.md`.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Execução datada de 2026-10-21.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-21 · **Idioma:** Português europeu

---

## 1. A pergunta

A implementação do Khnumn reproduz o resultado que o motor produz, quando
chamado directamente, sobre os mesmos ficheiros e com a mesma configuração?

Esta é a pergunta de `F2.E6`, e a razão de ela existir é que um benchmark
contra a própria implementação não prova nada: as duas partilham a mesma
configuração e o mesmo motor, e a diferença mediria apenas a diferença
entre dois caminhos de invocação.

Por isso a comparação é contra a **via manual**, obtida por
`scripts/linha-base.py`, que chama o motor sem o Khnumn no meio.

## 2. Configuração, comum às duas execuções

| Parâmetro | Valor |
|---|---|
| Conjunto | `eth3d-terrace`, partição `ajuste`, 9 imagens |
| Conjunto de trabalho | 1 000 px de lado maior, JPEG qualidade 92, preparado fora do motor |
| Descritores | SIFT, máximo 2 048 por imagem |
| Correspondência | Exaustiva, força bruta, verificação cruzada |
| Mapeador | Incremental |
| **Gauge** | **Par inicial declarado** (`DSC_0259.JPG`, `DSC_0261.JPG`) e **primeira câmara mantida constante** |
| Semente | 0 |
| Threads | 2 |
| Acelerador | nenhum |
| Máquina | Intel Core i3-5005U, 4 threads, 3 826 MiB RAM |

O gauge é declarado nas duas execuções, e não escolhido pelo motor. Sem
isso, a comparação mediria a escolha interna do motor em vez da
implementação.

## 3. Resultados

| Métrica | Via manual | Pelo Khnumn | Diferença | Tolerância |
|---|---|---|---|---|
| Câmaras registadas | 4 | 4 | 0 | coincidência exacta |
| Pontos 3D | 114 | 114 | 0 | 1 % |
| Observações | 320 | 320 | 0 | 1 % |
| Erro de reprojecção médio | 0,868138 px | 0,868138 px | 0 | 1 × 10⁻³ px |
| Comprimento médio de rasto | 2,899 | 2,899 | 0 | 1 % |
| Componentes conexas | 1 | 1 | 0 | coincidência exacta |
| Imagens na componente | as mesmas 4 | as mesmas 4 | — | coincidência exacta |
| Observações rejeitadas | 2 539 | 2 539 | 0 | 1 % |
| Estado | `SUCCEEDED` | `SUCCEEDED` | — | — |

A coincidência é exacta em todas as métricas, e não aproximada: as duas
execuções produzem o mesmo modelo.

Os valores exactos estão no relatório de execução,
[`processos/execucoes/sfm-eth3d-terrace.json`](execucoes/sfm-eth3d-terrace.json),
e na linha de base, em
[`processos/execucoes/linha-base-eth3d-terrace.json`](execucoes/linha-base-eth3d-terrace.json).

## 4. Tolerância

A tolerância de comparabilidade, declarada em
`processos/protocolo-benchmark.md` §8.1, é de **equivalência numérica** com
valores escritos:

| Métrica | Tolerância |
|---|---|
| Erro de reprojecção médio | 1 × 10⁻³ px |
| Número de câmaras registadas | coincidência exacta |
| Número de pontos 3D | 1 % |
| Componentes conexas | coincidência exacta |
| Conjunto de imagens da componente | coincidência exacta |

O número de execuções repetidas é **1** por execução, e a dispersão entre
execuções não foi medida. Esta é uma limitação declarada, e não uma
dispersão nula: o mapeador incremental é determinístico com a semente fixada
e o gauge declarado, e a medição da dispersão fica por fazer quando houver
tempo de execução para as repetições.

## 5. Limitações declaradas

Estas limitações são a parte do registo que mais importa, porque é por elas
que o resultado **não** pode ser lido como uma afirmação mais forte do que é.

| Limitação | Efeito |
|---|---|
| **Não há referência geodésica independente** | O estado de aceitação do produto é `NOT_VALIDATED`. A consistência interna e a forma da superfície são o que foi medido; a exactidão posicional absoluta não foi |
| A cena é pequena, de arquitectura, com vegetação | O desempenho em campo aberto, e com textura fraca, não é medido |
| Só se usaram 9 das 17 imagens da partição de ajuste | A poda é declarada, e é a razão de a execução caber no orçamento de tempo e memória do ambiente |
| A correspondência consumiu ~90 s sobre uma máquina carregada | O custo em tempo é um proxy, comparável apenas na mesma máquina |
| A dispersão entre execuções repetidas não foi medida | A reprodutibilidade é demonstrada por coincidência numa execução, e não por distribuição |
| O gauge foi fixado por um par inicial e uma câmara constante | É uma declaração explícita, e não a fixação por três pontos de levantamento, que é a via do fluxo de controlo da Fase 3 |

## 6. O que a comparação mostra, e o que não mostra

**Mostra** que a implementação não altera o resultado: as mesmas câmaras, os
mesmos pontos, o mesmo erro, a mesma componente. A camada de orquestração —
grafo de tarefas, cache por hash, limite de memória por tarefa, registo de
proveniência — é transparente para a geometria.

**Não mostra** que a reconstrução é boa. Um erro de reprojecção de 0,87 px
com 80 observações por imagem é um resultado modesto, e o modelo cobre 4 das
9 imagens, com 2 539 das 2 859 correspondências verificadas rejeitadas. A cena, com a partição declarada, não dá mais do que isso neste
ambiente.

A distinção entre as duas afirmações é o que separa uma medição de uma
demonstração, e é a razão de o estado ser `NOT_VALIDATED` e não `PASS`.

## 7. Registo

| Item | Valor |
|---|---|
| Decisão | Comparação feita, com tolerância escrita e limitações declaradas |
| Data | 2026-10-21 |
| Etapa | `F2.E6` de `docs/ROADMAP.md` |
| Referência | `docs/Khnumn.md` §21.1, §21.3, §15.4; `processos/protocolo-benchmark.md` §8 |
| Estado do produto | `NOT_VALIDATED` |
| Efeito no roadmap | Nenhum na ordem; a medição da dispersão entre execuções fica por fazer |

---

**Nota de âmbito:** uma reconstrução reprodutível não é uma reconstrução
correcta. A correcção é uma afirmação sobre o mundo, e o checkpoint
independente é o que a sustenta.
