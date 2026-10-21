# Khnumn — Linha de base manual

**Âmbito:** este registo fixa o resultado de referência obtido pela via
directa do motor, contra o qual a implementação do Khnumn é comparada.
Corresponde a etapa `F0.E9` de `docs/ROADMAP.md`.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Execução datada de 2026-10-21.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-21 · **Idioma:** Português europeu

**Relatório da execução:** [`processos/execucoes/linha-base-eth3d-terrace.json`](execucoes/linha-base-eth3d-terrace.json)

---

## 1. Porque a linha de base é obtida sem o Khnumn

A linha de base é o resultado de referência. Se fosse produzida pelo próprio
código que se está a validar, uma falha comum aos dois seria invisível: os
dois números concordariam, e o concordar não diria nada.

A via é, por isso, a mais directa que existe: o motor é chamado
directamente, por `scripts/linha-base.py`, sem o Khnumn no meio. A
implementação tem de reproduzir estes números, não-os bater.

## 2. A execução

| Campo | Valor |
|---|---|
| Identificador | `linha-base-eth3d-terrace` |
| Data | 2026-10-21 |
| Questão | A reconstrução esparsa pela via directa do motor é reprodutível dentro das tolerâncias? |
| Hipótese | A cena, com boa sobreposição e textura, reconstroi-se de forma consistente |
| Variável alterada | Nenhuma: esta é a execução de referência |
| Conjunto | `eth3d-terrace`, partição `ajuste` |
| Motor | COLMAP 4.2.1, via `pycolmap` 4.2.1 |
| Máquina | Intel Core i3-5005U, 4 threads, 3 826 MiB RAM, sem acelerador |
| Mapeador | Incremental |
| Semente | N/A (o mapeador incremental não é aleatório) |

### 2.1 Pré-processamento declarado

O pré-processamento é declarado e é igualado entre comparações, conforme
`processos/protocolo-benchmark.md` §1.2.

| Parâmetro | Valor | Razão |
|---|---|---|
| Conjunto de trabalho | 9 imagens da partição `ajuste`, reduzidas a 1600 px de lado maior | O orçamento de 500 MiB não comporta a correspondência exaustiva sobre as 17 imagens de 24 MP |
| Método de redução | Redução no domínio DCT do JPEG, seguida de reamostragem bilinear | A redução DCT é rápida e usa pouca memória; a reamostragem é determinística |
| Formato de trabalho | JPEG, qualidade 92 | Declarado, e o hash de cada imagem derivada está em `manifests/hashes.yaml` |
| `max_num_features` | 4 096 | Reduz o custo da correspondência por força bruta |
| `max_image_size` no motor | 1 600 | Coincide com o conjunto de trabalho; a redução dentro do motor manteria a câmara na resolução original e a prévia de focagem ficaria errada |
| `num_threads` | 2 | Metade dos threads físicos, para não disputar memória com o resto |
| `use_gpu` | `false` | Não há acelerador |

### 2.2 Resultados

| Métrica | Valor |
|---|---|
| Câmaras registadas | **4** de 9 |
| Pontos 3D | 277 |
| Observações | 803 |
| Erro de reprojecção médio | **0,597 px** |
| Comprimento médio de rasto | 2,90 imagens por ponto |
| Observações por imagem (média) | 200,75 |
| Componentes conexas do modelo | **1**, com as 4 imagens registadas |
| Tempo de extracção de features | 37,8 s |
| Tempo de correspondência | 330,6 s |
| Tempo de mapeamento | 1,4 s |
| Pico de memória do processo | dentro do orçamento de 500 MiB |

### 2.3 Estado

**`NOT_VALIDATED`**, com a causa declarada: *sem referência geodésica
independente; este conjunto valida a consistência interna e a forma da
superfície, não a exactidão posicional absoluta* (`docs/Khnumn.md` §15.2,
§15.4).

## 3. Os dois achados

A execução não é só um número de referência. Produziu dois achados que mudam
o que a Fase 2 tem de fazer.

### 3.1 A prévia de focagem é um efeito de escala, e o motor não a corrige

A primeira tentativa passou `max_image_size=1600` ao motor, deixando as
imagens no formato original. O resultado foi uma reconstrução de 4 imagens,
com o grafo de correspondências fragmentado: 17 pares verificados em 36.

A causa está no que o motor faz com a redução: as observações são
reescaladas para as coordenadas da imagem original e a câmara é mantida em
6048 × 4032, mas a prévia de focagem continua a ser a da resolução
original (3 359 px) enquanto os descritores vivem numa imagem de 1 600 px. O
limiar epipolar de 4 px, aplicado com uma focagem 3,8× grande demais, torna-se
um limiar de cerca de 1 px na imagem reduzida, e a correspondência é
rejeitada.

**Consequência para a implementação:** a redução de resolução tem de ser um
passo explícito do Khnumn, feito antes do motor, com as suas próprias
imagens, os seus próprios hashes e a sua escala declarada. Não pode ser um
parâmetro do motor, porque o motor não reconcilia a prévia com a redução.
Este é um caso concreto da regra de `docs/Khnumn.md` §10.1 sobre a
convenção de coordenadas de píxel: a conversão de meio píxel entre
ferramentas é pequena; uma prévia errada por um factor de escala é um erro
sistemático que o erro de reprojecção não denuncia.

### 3.2 A partição por índice fragmenta a sequência de captura

A regra de partição declarada no manifesto — a imagem de índice múltiplo de 4
vai para `verificacao` — é correcta para uma medida de pose, e é errada para
uma reconstrução: ela remove uma imagem de cada quatro, e a remoção de
imagens intercaladas degrada a conectividade do grafo de vistas.

Medido: com as 9 imagens de primeira linha, o modelo tem uma componente
conexa com 4 imagens. As 5 restantes, que se sobrepõem pouco às registadas,
formam conjuntos isolados.

**Consequência para a implementação:** a partição de verificação tem de
respeitar a conectividade. A regra a fixar é a de *blocos*: a sequência de
captura é dividida em blocos de N imagens, e cada bloco contribui com a
primeira imagem para a verificação e as restantes para o ajuste. A
connectividade local é preservada, e a verificação continua a ser um
conjunto cujas imagens nunca entram no ajuste.

### 3.3 O orçamento de memória é o que dimensiona o número de descritores

A execução do pipeline pela CLI, sobre o mesmo conjunto de trabalho, foi
**interrompida pelo orçamento de 500 MiB**, com a causa registada:

```
orcamento de memoria excedido: processo "…/.venv/bin/python" ultrapassou
500 MiB (pico amostrado: 501 MiB)
```

A causa está na correspondência por força bruta, e é quadrática no número de
descritores: o motor reserva uma matriz de distâncias de
`2 × n × n × 4` bytes por thread, o que com 4 096 descritores e 2 threads dá
cerca de 268 MiB só de buffers.

**Consequência para a implementação:** o número de descritores por imagem não
é um parâmetro de qualidade, é um parâmetro de memória. Com 2 048
descritores, a mesma execução cabe no orçamento declarado. A regra que
resulta é a de `docs/Khnumn.md` §16.3 aplicada ao motor: cada tarefa declara
a sua memória, e o orçamento é o que a limita.

Este é o primeiro caso em que o orçamento fez o que se propõe fazer: não
descrever um limite, mas interromper a tarefa e dizer porquê.

### 3.4 O que a linha de base estabelece

| Para a implementação | Valor a reproduzir |
|---|---|
| Erro de reprojecção médio | 0,597 px, com o mesmo pré-processamento |
| Número de câmaras registadas | 4, com a mesma partição e o mesmo conjunto de trabalho |
| Componentes conexas | 1 |
| Tolerância declarada | `1e-3` px no erro de reprojecção médio, e coincidência exacta no número de câmaras e de componentes |

O erro de reprojecção é um diagnóstico e não um portão de aceitação
(`docs/Khnumn.md` §15.4). Aqui ele serve para comparar duas execuções da
mesma configuração, que é a pergunta do §1.

## 4. Limitações declaradas

| Limitação | Efeito |
|---|---|
| A cena é pequena e de arquitectura, com vegetação | O desempenho em campo aberto não é medido |
| Não há datum de levantamento | A exactidão absoluta não é avaliável, e o estado é `NOT_VALIDATED` |
| O conjunto é não-comercial | Os produtos derivados não podem ser redistribuídos comercialmente |
| A correspondência consumiu 330 s sobre uma máquina carregada | O custo em tempo é um proxy, e o número só é comparável na mesma máquina |

## 5. Como repetir

```
.venv/bin/python scripts/linha-base.py \
    --imagens <directorio de trabalho> \
    --saida <directorio de saida> \
    --mapeador incremental \
    --max-features 4096 \
    --threads 2
```

A preparação do conjunto de trabalho reduzido é um passo explícito e
declarado, e os seus hashes estão em `manifests/hashes.yaml`.

## 6. Registo

| Item | Valor |
|---|---|
| Decisão | Linha de base obtida pela via directa do motor, com pré-processamento declarado |
| Data | 2026-10-21 |
| Etapa | `F0.E9` de `docs/ROADMAP.md` |
| Referência | `docs/Khnumn.md` §21.1, §10.1; `processos/protocolo-benchmark.md` §1.2, §9 |
| Achados | A prévia de focagem não é reconciliada com a redução de resolução; a partição por índice fragmenta a conectividade |
| Efeito no roadmap | Nenhum na ordem; muda a pré-condição de `F2.E2` e `F2.E6` |

---

**Nota de âmbito:** a linha de base é um ponto de comparação, não um
resultado. Serve para responder a uma pergunta por vez, com dados que
permitam respondê-la.
