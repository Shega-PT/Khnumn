# Khnumn

**Plataforma de evidência geométrica rastreável** para transformar conjuntos heterogéneos de imagens e vídeos em representações espaciais coerentes, mensuráveis e auditáveis.

> **Estado:** em desenvolvimento. A Fase 0 do roadmap está fechada e existe um núcleo executável: ingestão com inventário por hash, leitura de metadados, quality gate, grafo de tarefas com cache por hash e reconstrução esparsa pelo motor de SfM. A georreferenciação com pontos de controlo, a propagação da incerteza, a reconstrução densa e a distribuição ainda não existem. O estado de cada etapa está em [`docs/ROADMAP.md`](docs/ROADMAP.md) §4.

**Versão:** 0.1.0 · **Data:** 2026-10-20 · **Idioma:** Português europeu

---

## Índice

- [Khnumn](#khnumn)
  - [Índice](#índice)
  - [1. O que é](#1-o-que-é)
  - [2. O que não é](#2-o-que-não-é)
  - [3. Princípios de engenharia](#3-princípios-de-engenharia)
  - [4. Como funciona](#4-como-funciona)
  - [5. Os três caminhos de superfície](#5-os-três-caminhos-de-superfície)
  - [6. Os três métodos de controlo](#6-os-três-métodos-de-controlo)
  - [7. Incerteza, validação e proveniência](#7-incerteza-validação-e-proveniência)
    - [7.1 Incerteza](#71-incerteza)
    - [7.2 Validação](#72-validação)
    - [7.3 Proveniência](#73-proveniência)
  - [8. Produtos de saída](#8-produtos-de-saída)
  - [9. Requisitos de hardware](#9-requisitos-de-hardware)
  - [10. Mapa do repositório](#10-mapa-do-repositório)
  - [11. Estado atual e limitações](#11-estado-atual-e-limitações)
  - [12. Licenças e software de terceiros](#12-licenças-e-software-de-terceiros)
  - [13. Licença do projeto](#13-licença-do-projeto)

---

## 1. O que é

Khnumn é um **sistema modular e distribuído** que transforma imagens, vídeos e dados de sensores heterogéneos em produtos geoespaciais — nuvem de pontos, malhas, modelos de superfície, ortoimagens e mapas de incerteza — mantendo, em cada produto, a rastreabilidade até aos ficheiros de origem e a incerteza que lhe é aplicável.

A proposta não é substituir indiscriminadamente bibliotecas maduras. O valor próprio está em quatro pontos:

1. **Normalização** de observações heterogéneas num modelo de dados único, versionado e com incerteza declarada.
2. **Encaminhamento automático** para o método adequado a cada sensor e a cada cena, com a decisão explicada.
3. **Gestão explícita de incerteza**, como dado de primeira classe e não como subproduto.
4. **Validação independente**, com pontos de verificação que nunca entram no ajuste.

O sistema foi desenhado para correr **sem acelerador**, e a GPU é uma aceleração opcional, nunca um pressuposto do formato de dados ou da API.

## 2. O que não é

- **Não é um motor de reconstrução.** SfM, MVS, ajuste de feixes e álgebra geoespacial são usados de bibliotecas maduras, comparados em benchmark e substituídos apenas com vantagem demonstrada.
- **Não promete reconstrução 3D a partir de qualquer conjunto de imagens.** Uma superfície sem textura, reflexiva, transparente ou repetitiva impede correspondências fiáveis. O sistema declara essa limitação em vez de inventar profundidade.
- **Não substitui os requisitos normativos do projeto.** A aprovação para uso legal, cadastral, de engenharia ou de segurança segue a norma aplicável à jurisdição e ao domínio.
- **Não é um serviço cloud.** A API de serviço é uma das interfaces possíveis; o núcleo tem de correr localmente.

## 3. Princípios de engenharia

| Princípio | O que significa na prática |
|---|---|
| **Medir antes de optimizar** | Cada melhoria é avaliada em qualidade geométrica, custo de recursos e robustez. Uma melhoria de 30% no tempo que aumente o erro vertical além do limite não é uma melhoria |
| **Incerteza como dado de primeira classe** | As coordenadas nunca são apresentadas como exatas sem a sua incerteza; quando não é estimada, isso é declarado explicitamente |
| **Arquitectura CPU-first** | O sistema base funciona sem GPU. Os caminhos CPU e GPU são testados quanto à consistência e à qualidade |
| **Modularidade com contratos** | Cada módulo recebe dados tipados, parâmetros versionados e limites de recursos, e devolve resultados, métricas e erros estruturados |
| **Reutilizar, medir, só depois substituir** | A implementação própria concentra-se nas lacunas demonstradas |
| **Reconstrução sem falsificação** | A ausência de evidência suficiente produz um estado explícito, não um resultado plausível |

## 4. Como funciona

O projeto é representado como um **grafo acíclico dirigido de tarefas**. Cada tarefa tem entradas imutáveis, parâmetros explícitos, versão do algoritmo, limites de recursos e saídas identificadas por hash. Uma tarefa que falhe produz um estado e um motivo legíveis, e uma falha geométrica nunca é convertida em sucesso parcial sem marcar os produtos afectados.

```text
[Fontes e conectores]
        ↓
[Ingestão + inventário + hashes]
        ↓
[Normalização de metadados e CRS]
        ↓
[Diagnóstico de qualidade e cenário]
        ↓
[Planeador de pipeline e orçamento de recursos]
        ↓
[Calibração / georreferenciação]
        ↓
[Extracção de características]
        ↓
[Correspondências e grafo de vistas]
        ↓
[SfM / poses / ajuste global]
        ↓
[MVS / profundidade / nuvem densa]
        ↓
[Fusão geométrica e classificação]
        ↓
[DSM/DTM]
        ↓
[Malha 3D]
        ↓
[Ortoimagem]
        ↓
[Validação independente + incerteza]
        ↓
[Exportação + relatório + proveniência]
```

A execução **distribuída** não significa que qualquer conjunto de dados possa ser processado rapidamente num equipamento limitado. Significa que a arquitectura controla os recursos, divide o trabalho e permite continuar em máquinas mais capazes **sem mudar o modelo de dados nem a lógica científica**.

## 5. Os três caminhos de superfície

A reconstrução densa é a etapa mais exigente do sistema e a que mais varia entre máquinas. Como não existe hoje um MVS sob licença permissiva com qualidade equivalente em CPU, o Khnumn mantém **três caminhos declarados**, escolhidos pelo planeador segundo a capacidade real do host:

| Caminho | Motor | Requisito | Densidade | Observação |
|---|---|---|---|---|
| **Esparso** | Triangulação de Delaunay sobre a nuvem esparsa | CPU | Baixa | Único caminho totalmente permissivo em CPU |
| **Denso em CPU** | Motor de MVS externo, opcional | CPU | Alta | Executado como processo separado; exige instalação e traz aviso de licença |
| **Denso em acelerador** | Motor de referência | CUDA ou ROCm | Alta, com consistência geométrica multivista | Caminho por omissão quando existe hardware compatível |

O sistema **não promete reconstrução densa em qualquer máquina**: promete a melhor reconstrução que a máquina suporta, e declara em cada produto o caminho de que veio, a densidade efectiva e a sua proveniência. Os três produtos não são equivalentes e não devem ser comparados como se o fossem.

A via densa em CPU é conduzida por um **ciclo de refinação iterativo**, em que cada passagem usa a nuvem anterior como informação de partida. A paragem é por **autoconvergência**, com orçamento declarado, e a **melhor iteração** é a retida, não a última.

## 6. Os três métodos de controlo

Como o controlo entra no sistema determina como os erros se propagam e que afirmações de exatidão são legítimas. A escolha é sempre explícita na configuração e no relatório.

| Método | Como funciona | Quando se aplica |
|---|---|---|
| **Transformação de similaridade** | Similaridade de 7 parâmetros, aplicada depois da reconstrução, a partir de centros de câmara | Último recurso. Não propaga incerteza para a geometria, e um produto assim justificado nunca pode ser declarado conforme |
| **Priors de pose GNSS** | A posição GNSS de cada imagem entra como observação no ajuste, com a sua covariância | **Método por omissão**, por estar disponível sem trabalho adicional e por propagar incerteza para as poses |
| **Pontos de controlo como observações** | Cada ponto de controlo, de coordenadas conhecidas com covariância declarada, entra como ponto fixo no ajuste | Quando o projeto exige exatidão de levantamento |

A cadeia de implementação do terceiro método tem seis passos: **deteção** das marcas, **triangulação** local, **similaridade ponderada** pelas covariâncias, **fixação** do gauge e das posições, **ajuste constrangido**, e **propagação da incerteza por ensemble**.

As marcas de controlo são **alvos circulares e simétricos**, de tamanho especificado em **píxeis** e verificado contra a GSD planeada antes do voo. A deteção é automática e funciona como refinamento local em sub-píxel, a partir da projeção das coordenadas de terreno para cada imagem — o que dispensa alvos codificados — e é filtrada por consistência multivista. O operador **confirma ou rejeita** as deteções; não mede coordenadas de píxel.

## 7. Incerteza, validação e proveniência

### 7.1 Incerteza

A incerteza de um produto com controlo decai em **duas parcelas**: a da cena, que vem da covariância interna do ajuste, e a do controlo, que vem do **ensemble** — a etapa final executada N vezes, com as coordenadas dos pontos de controlo perturbadas pela sua covariância. A combinação das duas só é legítima se forem aproximadamente independentes, o que tem de ser verificado.

A propagação interna é o que permite **prever** a exatidão e **diagnosticar** se o produto está limitado pelo controlo. É o **ponto de verificação independente** que a **demonstra**.

### 7.2 Validação

Os pontos de controlo entram no ajuste. Os **pontos de verificação não entram em nada** — a exclusão é imposta pelo carregamento, não por convenção do operador. Os critérios de aceitação seguem normas públicas, e não valores inventados caso a caso:

- **ASPRS Positional Accuracy Standards, edição 2 (2023):** `RMSE_H`, `RMSE_V` e `RMSE_3D`; mínimo de trinta pontos de verificação; discrepância acima de três vezes o RMSE-alvo tratada como *blunder*; erro médio inferior a 25% do RMSE-alvo; descontinuidade de costura até duas vezes o `RMSE_H`.
- **USGS OFR 2023-1033:** o GSD não é a exatidão posicional, e a exatidão do produto não pode exceder a exatidão dos pontos de controlo.
- **ISO 17123-10 e ISO 19623:** procedimentos de campo para sistemas de medição por fotografia de UAV.

O resultado de uma execução é `PASS`, `PASS_WITH_WARNINGS`, `FAIL` ou `NOT_VALIDATED`. **`NOT_VALIDATED` é um estado legítimo** e preferível a um `PASS` injustificado.

### 7.3 Proveniência

Cada produto conserva a ligação até às fontes e às operações que o produziram: os originais preservados, as transformações de píxel que afectam a geometria registadas, o CRS e as operações de transformação, as versões de software e parâmetros, e a distinção explícita entre dados **medidos**, **estimados**, **interpolados** e **inferidos por modelo**.

## 8. Produtos de saída

Conforme a geometria e a qualidade de entrada:

- nuvem de pontos esparsa e densa;
- malha triangular texturizada;
- modelo digital de superfície (DSM/MDS);
- modelo digital do terreno (DTM/MDT), quando é possível separar terreno e objetos;
- ortomosaico ou ortoimagem;
- **mapas de cobertura, densidade, qualidade e incerteza**, como campos quantificados e não como imagens, conforme `docs/Khnumn.md` §13.6;
- relatórios de calibração, georreferenciação e validação;
- metadados de proveniência, que rastreiam cada produto até às fontes.

Nem todos os dados permitem todos os produtos. Uma imagem de satélite isolada com modelo de elevação produz ortoimagem, **não** geometria 3D: a reconstrução tridimensional exige um par estéreo ou triestéreo.

## 9. Requisitos de hardware

O sistema foi desenhado para funcionar num computador modesto, com CPU e RAM como base. O mínimo concreto ainda não está fixado mas o que já está estabelecido é:

- **Sem acelerador é possível**, com o caminho de superfície esparsa, e com o caminho denso em CPU mediante instalação de um componente externo.
- **A etapa densa em acelerador** exige CUDA ou ROCm, e é a via de maior qualidade.
- **O consumo de RAM** é estrangulamento na via CPU e **a memória do acelerador** é o estrangulamento na via densa acelerada. A estratégia de particionamento difere consoante o caminho.

## 10. Mapa do repositório

```text
/
├── README.md                  este ficheiro — o ponto de entrada
├── CHANGELOG.md               o registo de alterações do projecto
├── LICENSE                    a licença única do projeto
├── NOTICE                     o aviso de copyright do projeto
├── THIRD-PARTY.md             declaração das licenças dos componentes de terceiros
├── .gitignore
├── Cargo.toml                 a raiz do espaço de trabalho Rust
├── crates/                    o núcleo, em Rust
│   ├── khnumn-core/           modelo, esquemas, catálogo, DAG, proveniência
│   ├── khnumn-cli/            o executável `khnumn`
│   └── khnumn-render/         rasterização de superfície (Fase 9, ADR-012)
├── python/khnumn/             a camada científica, em Python
├── schemas/                   os contratos JSON Schema versionados
├── manifests/                 a declaração dos conjuntos de dados e os seus hashes
├── scripts/                   verificação, auditoria de licenças, manifesto e linha de base
├── testes/                    testes da camada científica e as fixtures sintéticas
├── docs/                      referência — descrevem o sistema
│   ├── Khnumn.md              a especificação técnica
│   ├── ROADMAP.md             a ordem de execução
│   └── modelo-metadados.md    o modelo de dados versionado
└── processos/                 registos vivos — crescem com o trabalho
    ├── decisoes-motores.md    o registo de decisões de motores e licenças
    ├── protocolo-benchmark.md o protocolo com que o sistema é medido
    ├── alvo-validacao.md      o primeiro alvo de validação
    ├── hardware-referencia.md a máquina de referência e o orçamento de recursos
    ├── politica-falhas.md     os estados e as regras de falha
    ├── auditoria-licencas.md  a auditoria feita por build
    ├── linha-base.md          o resultado de referência
    ├── sbom.json              o inventário de licenças gerado
    └── execucoes/             os relatórios das execuções de benchmark
```

| Ficheiro | Conteúdo |
|---|---|
| [`docs/Khnumn.md`](docs/Khnumn.md) | A especificação técnica. Objectivo, âmbito, princípios, arquitectura, modelo de dados, algoritmo, incerteza, formatos, plano de testes, plano de fases e referências. É o documento de referência |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | A ordem de execução, decomposta em fases e etapas, com estados e dependências. Sem datas nem estimativas de esforço |
| [`docs/modelo-metadados.md`](docs/modelo-metadados.md) | O modelo de dados versionado: esquema, ausência explícita, unidades, incerteza e proveniência; a revisão do esquema de produto de 2026-10-22 e a regra da declaração de ausência de CRS |
| [`processos/protocolo-benchmark.md`](processos/protocolo-benchmark.md) | O protocolo de benchmark: conjuntos de dados, partições, controlo e verificação, métricas, tolerâncias, reprodutibilidade e template de relatório |
| [`processos/decisoes-motores.md`](processos/decisoes-motores.md) | O registo de decisões de motores e licenças: matriz por função, riscos de construção, e os registos de decisão (ADR) com contexto, decisão e consequências |
| [`processos/alvo-validacao.md`](processos/alvo-validacao.md) | O primeiro alvo de validação, os alvos secundários por função, e o que cada um serve e o que não serve |
| [`processos/hardware-referencia.md`](processos/hardware-referencia.md) | A máquina de referência, o orçamento de memória, e o que esse orçamento torna impossível |
| [`processos/politica-falhas.md`](processos/politica-falhas.md) | Os estados de tarefa e de produto, e a tabela do que faz a execução parar ou continuar |
| [`processos/auditoria-licencas.md`](processos/auditoria-licencas.md) | A auditoria de licenças feita por build, e as decisões de dependência que dela resultam |
| [`processos/linha-base.md`](processos/linha-base.md) | O resultado de referência obtido pela via directa do motor, e os achados que a medição produziu |
| [`CHANGELOG.md`](CHANGELOG.md) | O registo de alterações do projecto, semeado com o registo de revisões da especificação |
| [`THIRD-PARTY.md`](THIRD-PARTY.md) | A declaração das licenças dos componentes de terceiros aprovados para uso, com a sua versão, o seu papel e o tipo de integração |
| [`NOTICE`](NOTICE) | O aviso de copyright do projeto, em ficheiro próprio, para que o texto da `LICENSE` permaneça intacto |

### 10.1 Como construir e verificar

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cargo build --release
scripts/verificar.sh
```

A verificação corre a análise estática e os testes do Rust, os testes da
camada científica, a auditoria de licenças por build, e uma execução de fumo
da CLI de ponta a ponta. Nenhuma das fases precisa de `sudo` nem de
dependências de sistema.

Os conjuntos de dados não estão no repositório. O manifesto de
[`manifests/conjuntos.yaml`](manifests/conjuntos.yaml) declara a licença, a
citação e a partição de cada um, e o URL de origem; os hashes do que está
efectivamente instalado estão em
[`manifests/hashes.yaml`](manifests/hashes.yaml), e são regenerados com
`python scripts/gerar-manifesto.py`.

**Convenção de referências:** as menções a outros documentos deste repositório usam o caminho relativo à raiz do repositório.

## 11. Estado atual e limitações

**O que existe:** a especificação técnica, as decisões de arquitectura tomadas e registadas, o protocolo com que o sistema é medido, a Fase 0 do roadmap fechada, a Fase 2 do roadmap concluída, e um núcleo executável que ingere imagens, as inventaria com hash, lê os seus metadados, avalia a sua qualidade, as executa num grafo de tarefas com cache por hash, e reconstrói uma cena esparsa pelo motor de SfM. O esquema de produto é revisto para incluir o formato em disco, o campo escalar de um mapa, a sua legenda e a declaração de ausência de CRS, e o registo de produtos passa a ser possível no catálogo. A Fase 9 está criada no roadmap, com as suas etapas em estado planeado, e a rasterização de superfície é a sua primeira produção.

**O que não existe:** a georreferenciação com pontos de controlo, a propagação da incerteza, a reconstrução densa e a distribuição. A sequência de implementação está descrita no [roadmap](docs/ROADMAP.md), e o estado de cada etapa therein.

**As limitações que a documentação assume e não esconde:**

- A exatidão alcançável depende da resolução, calibração, geometria de captura, georreferenciação, qualidade dos dados e de validação independente. Nenhuma ordem de implementação altera isso.
- A propagação da incerteza do controlo é **numérica**, não analítica, e depende do número de amostras.
- A equivalência entre a via densa em CPU e a de acelerador é uma **afirmação a medir**, não uma garantia.
- A via densa em CPU exige um componente com licença copyleft, instalado à parte e fora do caminho de código. Se o produto o distribuir, a questão de licença tem de ser revista antes.
- A reconstrução aprendida não é usada na cadeia de produção: a sua escala é ambígua, a sua confiança não está calibrada para o erro geométrico e alucina geometria em entradas incoerentes.
- Um único mapeador de controlo não resolve o problema da datum, e a concordância entre sensores não é verdade absoluta.
- **O ambiente de referência tem 3 826 MiB de RAM e não tem acelerador.** A reconstrução densa e a sua validação contra a referência de acelerador **não são executáveis** neste ambiente, e o estado dessa limitação está em [`processos/hardware-referencia.md`](processos/hardware-referencia.md) §3.

## 12. Licenças e software de terceiros

A **política de núcleo** é manter o núcleo distribuível livre de copyleft forte. Componentes com licença AGPL ou GPL podem ser executados como processos externos opacos, comunicando por um protocolo documentado e sem ligação de código, mas não são ligados ao núcleo nem aos seus adaptadores. A verificação faz-se por inspeção das dependências do binário distribuído, e não por convenção.

A tabela de motores, com a licença de cada um verificada a 2026-10-20, está em [`docs/Khnumn.md` §18.2](docs/Khnumn.md) e detalhada em [`processos/decisoes-motores.md`](processos/decisoes-motores.md). A lista de referências técnicas, com versão e data, está em [`docs/Khnumn.md` §26](docs/Khnumn.md). A **declaração das licenças de terceiros** é o ficheiro [`THIRD-PARTY.md`](THIRD-PARTY.md), e é a que está em uso numa dada versão.

A auditoria de licenças de um projeto concreto — incluindo modelos treinados, dados de exemplo, bibliotecas transitivas e binários distribuídos — é uma tarefa de integração, e não uma afirmação que este documento possa fazer. A partir da integração do `rasterio`, a auditoria cobre também a **árvore transitiva** do wheel, e não só o requisito declarado, conforme `processos/auditoria-licencas.md` §2.5. A rasterização de superfície é implementação própria em Rust, Apache-2.0, sem dependências de execução, e está registada em ADR-012 de `processos/decisoes-motores.md`.

## 13. Licença do projeto

O Khnumn é licenciado sob a **Apache License, Version 2.0**, cujo texto integral está em [`LICENSE`](LICENSE) e o aviso de copyright, em ficheiro próprio, em [`NOTICE`](NOTICE)., cujo texto integral está em [`LICENSE`](LICENSE).

É uma única licença, e é permissiva: não impõe copyleft e não obriga a abrir o código de quem o utiliza. A concessão explícita de patentes que a Apache-2.0 traz na sua seção 3 é a razão principal da escolha, porque responde ao risco identificado na especificação: uma licença de código, por si só, não resolve questões de patentes ou de licenças de dados.

As licenças dos componentes de terceiros **não** são aplicadas ao projeto. Cada uma é declarada, com a sua versão e o seu papel, em [`THIRD-PARTY.md`](THIRD-PARTY.md), e a decisão está registada em ADR-010, em [`processos/decisoes-motores.md`](processos/decisoes-motores.md).

---

**Khnumn** — uma plataforma de evidência geométrica rastreável, e não apenas uma ferramenta que gera modelos visualmente convincentes.
