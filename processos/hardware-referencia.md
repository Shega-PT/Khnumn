# Khnumn — Hardware de referência

**Âmbito:** este registo fixa o ambiente de referência do Khnumn: a máquina
onde as medições são feitas, o orçamento de recursos, e o que esse orçamento
torna impossível. Corresponde a etapa `F0.E2` de `docs/ROADMAP.md`, e
preenche a §2 de `processos/protocolo-benchmark.md`.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Decisão datada de 2026-10-21.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-21 · **Idioma:** Português europeu

---

## 1. A máquina

Não há segunda máquina. A máquina abaixo é, ao mesmo tempo, o **ambiente de
referência** (onde as medições são comparáveis) e o **piso declarado**
(o mínimo que o produto promete).

| Elemento | Valor medido | Data |
|---|---|---|
| CPU | Intel Core i3-5005U, 2 núcleos físicos / 4 threads, 2,00 GHz | 2026-10-21 |
| RAM total | 3 826 MiB (3,7 GiB) | 2026-10-21 |
| RAM disponível em serviço | ~1 500 MiB com o ambiente de desenvolvimento aberto; ~800 MiB com o editor e o agente de terminal abertos | 2026-10-21 |
| Swap | 3 980 MiB | 2026-10-21 |
| Acelerador | **ausente** | 2026-10-21 |
| Armazenamento | Partição única de 109 GB, ~40 GB livres no momento da medição | 2026-10-21 |
| Sistema operativo | Zorin OS 18.1, sobre base Ubuntu 24.04 | 2026-10-21 |
| Kernel | Linux 7.0.0-38-generic, x86_64 | 2026-10-21 |
| Ferramentas | rustc 1.98.1, cargo 1.98.1, Python 3.12.3 em venv própria | 2026-10-21 |

## 2. Orçamento de recursos

O orçamento é declarado por tarefa (`docs/Khnumn.md` §16.3) e é a base de
todas as medições de recurso.

| Parâmetro | Valor | Significado |
|---|---|---|
| **Orçamento de trabalho** | **500 MiB** | Memória de trabalho que uma tarefa pode usar sem ser considerada uma excepção |
| **Folga** | **300 MiB** | Margem até ao pico admissível, para accommodating picos transitórios dentro da mesma tarefa |
| **Pico admissível** | **800 MiB** | Acima deste valor, a tarefa é interrompida e marcada como falhada, com a causa. É o que o código impõe: o limite declarado é o orçamento mais a folga, e é ele que interrompe |
| Uso de swap | **falha de orçamento** | Uma tarefa que usa swap excedeu o orçamento. O swap não é folga: é sinal de que a folga já foi consumida |
| Threads | 2 | Metade dos threads físicos; a contenção de memória é uma limitação mais apertada do que a de CPU neste perfil |
| Disco temporário | limitado à partição do projecto | Espaço temporário é orçamento, e é removido com a política de retenção declarada |

### 2.1 Como o orçamento é medido

O pico de memória residente é lido de `/proc/<pid>/status` (`VmHWM`), com
amostragem de 50 ms, no processo filho que executa a tarefa. O valor
observado é um **limite inferior** do pico real, e a resolução da
amostragem acompanha o valor em cada relatório.

A medição não usa ferramentas externas: `intel-rapl` e `powercap` não estão
acessíveis, e a medição de energia é tratada como proxy, conforme
`processos/protocolo-benchmark.md` §2.2.

O número de ambiente é verificável a qualquer momento:

```
grep VmHWM /proc/<pid>/status
free -m
```

## 3. O que este orçamento torna impossível

Esta é a parte da decisão que tem mais consequências, e por isso é escrita
com a mesma clareza que as decisões que habilitam.

| Capacidade | Estado neste ambiente | Consequência para o roadmap |
|---|---|---|
| Reconstrução densa em acelerador | **Não executável** | `F4.E3` e `F4.E10` não podem ser verificadas aqui. A via densa em CPU (`F4.E9`) é que fica disponível, e ela exige um motor externo com licença AGPL, executado como processo separado |
| Validação da via densa contra a referência de acelerador | **Não executável** | `F4.E10` fica sem verificação local, com a causa registada, e não com um `PASS` |
| Ensemble de propagação da incerteza (`F3.E8`) | **Executável, com N reduzido** | O número de amostras tem de caber no orçamento, e a despesa real tem de ser medida em vez de presumida. O número mínimo declarado por omissão é 20, e o mínimo do protocolo é de 30 pontos de verificação, que são coisas diferentes |
| Ajuste global sobre coleções grandes | **Executável, com poda** | O número de imagens e a resolução de entrada são podados, e a poda é **pré-processamento declarado**, igualado entre comparações |
| Processamento por blocos (`F4.E5`) | **Executável** | A estratégia de blocos é a que este perfil exige, e não a que uma máquina grande tornaria desnecessária |
| Rasterização e publicação de rasters (`F9.E2`, `F9.E3`) | **Executável** | O orçamento de 500 MiB obriga a rasterizar por blocos e a publicar por tiles. O pico a vigiar é o TIFF intermédio descomprimido, e não o raster em si: o framebuffer e o depth buffer de uma saída de 1280×720 ocupam menos de 8 MiB, e o volume está na escrita |

### 3.1 O que isto não é

Não é uma limitação do sistema, e é importante que não seja lida como tal. É
uma limitação do **ambiente em que a medição é feita**. O sistema é
desenhado para correr sem acelerador (`docs/Khnumn.md` §3.3), e este
ambiente é, por isso, uma boa prova de que essa promessa não é retórica: a
Fase 1 e a Fase 2 são inteiramente executáveis aqui, e a Fase 2 tem de
produzir uma reconstrução reprodutível dentro das tolerâncias sem
acelerador nenhum.

### 3.2 O orçamento já Bits a um parâmetro de configuração

A correspondência de descritores por força bruta reserva uma matriz de
distâncias quadrática no número de descritores por imagem. Medido: com 4 096
descritores e 2 threads, a etapa ultrapassou o orçamento de 500 MiB e foi
interrompida; com 2 048, cabe.

O orçamento não é, por isso, apenas um limite de recursos a respeitar: é um
parâmetro que **dimensiona a configuração do motor**. É o que
`docs/Khnumn.md` §16.3 quer dizer com "cada tarefa deve declarar memória
estimada, memória máxima, número de threads".

### 3.3 O que a via densa em acelerador custaria aqui

A etapa densa é a mais exigente em recursos de todo o sistema, e a
documentação do motor mede 1,12 milhões de pontos e 2,9 GB de pico de
memória residente para 11 imagens de 63 MP num portátil de 8 GB. Com um
pico admissível de 800 MiB, a via densa em CPU está **fora do orçamento**
nesta máquina, para cenas desta dimensão.

Isto não é uma razão para não a implementar. É uma razão para a declarar
como não executável no ambiente de referência, e para que a fase 4 meça o
custo real antes de afirmar seja o que for sobre a via densa.

## 4. Consequências para a reprodutibilidade

| Fonte de não determinismo | Estado neste ambiente |
|---|---|
| Ordem de redução numérica em somas paralelas | Presente, com 4 threads; a tolerância entre execuções é declarada por comparação |
| Versões de bibliotecas | Fixadas em `requirements.lock` e em `Cargo.lock`; o `Cargo.lock` é versionado de propósito, segundo a política do `.gitignore` |
| Semente aleatória | Declarada por tarefa, quando a tarefa usa aleatoriedade |
| Versão do ambiente | Entra na identidade da tarefa, e por isso invalida a cache quando muda |
| Affinamento de processador | Registado como fonte a monitorizar nas execuções repetidas |
| Ordem de leitura de ficheiros | Determinística: os ficheiros são ordenados antes do processamento |

## 5. Regra de comparação

Qualquer execução feita noutra máquina é comparável **apenas** em métricas
geométricas, e nunca em tempo ou memória. O relatório tem de indicar a
máquina de cada execução, conforme `processos/protocolo-benchmark.md` §2.1.

## 6. Registo

| Item | Valor |
|---|---|
| Decisão | A máquina de §1 é o ambiente de referência e o piso declarado; o orçamento é 500 MiB com 300 MiB de folga |
| Data | 2026-10-21 |
| Etapa | `F0.E2` de `docs/ROADMAP.md` |
| Referência | `docs/Khnumn.md` §27.2 item 2, §16.3, §16.6; `processos/protocolo-benchmark.md` §2 |
| Consequência registada | `F4.E3` e `F4.E10` ficam sem execução local, com causa declarada |
| Efeito no roadmap | Nenhum na ordem; muda o que é verificável neste ambiente |

---

**Nota de âmbito:** o hardware de referência não é uma promessa de desempenho.
É a condição em que as medições são comparáveis e em que a
reprodutibilidade pode ser exigida.
