# Khnumn — Registo de decisões de motores e licenças

**Âmbito:** este documento fixa as escolhas de motor, as alternativas avaliadas e as restrições que as condicionam. É a fonte de verdade para a tabela de §18.2 de `docs/Khnumn.md` e para as decisões fixadas de §27.1 do mesmo documento.
**Convenção de referências:** as menções a outros documentos deste repositório usam o caminho relativo à raiz do repositório.


**Estado:** proposta para fixação na Fase 0. As entradas marcadas `A FIXAR` dependem do primeiro alvo de validação.

**Convenção sobre o nome:** os registos de decisão referem o nome do projeto vigente na data em que foram escritos. O nome actual é Khnumn, desde 2026-10-20; as decisões anteriores a essa data referem Mímir, que era o nome de trabalho então.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-22 · **Idioma:** Português europeu

---

## Índice

1. [Princípio de política de licenças](#1-princípio-de-política-de-licenças)
2. [Matriz de motores por função](#2-matriz-de-motores-por-função)
3. [Backends de ajuste de feixes](#3-backends-de-ajuste-de-feixes)
4. [Riscos de construção e de compatibilidade](#4-riscos-de-construção-e-de-compatibilidade)
5. [Consumo de recursos por etapa](#5-consumo-de-recursos-por-etapa)
6. [Riscos em aberto](#6-riscos-em-aberto)
7. [Registo de decisões](#7-registo-de-decisões)

---

## 1. Princípio de política de licenças

### 1.1 Regra

O núcleo distribuível do Khnumn é livre de copyleft forte. Componentes sob AGPL ou GPL podem ser executados como processos externos separados, comunicando por um protocolo documentado e sem ligação de código, mas não são ligados ao núcleo nem aos seus adaptadores.

### 1.2 Fundamento

A licença de um componente condiciona a licença do produto e a obrigação de disponibilizar código-fonte. A fronteira entre agregação simples e obra derivada depende dos fato e não apenas da forma da distribuição, pelo que a separação tem de ser real e verificável, e não apenas declarativa. A verificação faz-se por inspeção das dependências do binário distribuído.

### 1.3 Consequência prática

O COLMAP 4.x é o candidato natural a motor de referência porque cobre SfM, MVS, malha e texturização sob licença permissiva, o que torna o OpenMVS dispensável do caminho principal. O custo desta escolha é uma limitação operacional de CPU, tratada em §6.1.

---

## 2. Matriz de motores por função

A coluna "licença" refere-se ao código do componente; as dependências transitivas têm de ser auditadas por build.

| Função | Escolha primária | Licença | Alternativas avaliadas | Nota de decisão |
|---|---|---|---|---|
| Ingestão e inventário | Própria, sobre GDAL/ExifTool | MIT / MIT | — | Nenhuma biblioteca de fotogrametria faz isto |
| Extracção de metadados | Própria, sobre `Pillow` + `piexif` + `defusedxml` | MIT-CMU / MIT / PSF-2.0 | ExifTool (Perl Artistic), como QA externo | Sem dependência de sistema no caminho de código; ver `processos/auditoria-licencas.md` §1 |
| Correspondência e SfM | COLMAP 4.2.1, por `pycolmap` | BSD-3-Clause | OpenMVG (MPL-2.0), GLOMAP integrado no COLMAP | O COLMAP expõe três mapeadores; escolher por tamanho e qualidade do grafo de vistas |
| Correspondência aprendida | COLMAP com ALIKED, LoMa ou LightGlue via ONNX | BSD + MIT (ONNX Runtime) | hloc (Apache-2.0) | Descritores de tipos diferentes não podem conviver na mesma base de dados; medição de custo de memória pendente |
| Reconstrução densa, caminho GPU | COLMAP `patch_match_stereo` + `stereo_fusion` | New BSD | — | Exige CUDA ou ROCm; não é executável no ambiente de referência, ver `processos/hardware-referencia.md` §3 |
| Reconstrução densa, caminho CPU | Motor de MVS externo, opcional | AGPL (OpenMVS) ou GPL (CMVS/PMVS2) | AliceVision (MPL-2.0, mas `DepthMap` exige CUDA), MVS em PyTorch | Executado como processo separado; ver §6.1 |
| Superfície em CPU, núcleo permissivo | COLMAP `delaunay_mesher` sobre a nuvem esparsa | New BSD | Poisson sobre a esparsa | Densidade substancialmente menor; é o caminho CPU por omissão |
| Malha | COLMAP (Poisson, Delaunay, advancing front) | New BSD | OpenMVS (AGPL, excluído), Poisson original | Poisson exige nuvem quase livre de outliers; Delaunay escala melhor |
| Texturização | COLMAP `mesh_texturer` | New BSD | OpenMVS (AGPL, excluído) | Atribui cada face à melhor vista por área projectada e ângulo |
| Ortoimagem | `rasterio`, que embute o GDAL | BSD-3-Clause | GDAL de sistema | Não é coberta por nenhum motor de SfM ou MVS; decisão a confirmar em `F4.E7`. O mesmo componente publica os rasters de §13.6, em `F9.E3` |
| DTM e filtragem de solo | Implementação própria, sobre `Open3D` | MIT | PDAL (BSD, sem wheel no PyPI e sem `conda` neste ambiente) | Não é coberta por nenhum motor de SfM ou MVS; ver `processos/auditoria-licencas.md` §2.4 |
| Nuvens de pontos, registo | `Open3D` | MIT | PDAL (BSD), CloudCompare (GPL, apenas ferramenta externa) | O CloudCompare é ferramenta de QA, não componente |
| Rasterização de superfície | Própria, em Rust | Apache-2.0 | `Open3D` (MIT), `CloudCompare` (GPL-3.0), motor de GPU (wgpu, OpenGL), motor de referência externo | As duas primeiras têm interface gráfica e a segunda é copyleft forte, e o ambiente de referência não tem acelerador. Ver ADR-012 |
| Escrita de rasters geoespaciais | `rasterio`, que embute o GDAL | BSD-3-Clause | GDAL de sistema | Serve a ortoimagem de §13.5 e a publicação dos rasters de §13.6; a árvore transitiva do wheel tem de ser auditada |
| TIFF intermédio | crate `tiff`, em Rust | MIT | — | Sem features de compressão, para zero dependências transitivas; a compressão final é a do COG. Ver ADR-013 |
| Geodesia e CRS | `pyproj`, sobre PROJ 9.8.1 | MIT | proj4rs (Rust puro, insuficiente) | Sem WKT e sem transformações 3D ou ortométricas; não substitui a PROJ |
| Ajuste de feixes e controlo | COLMAP, via ligações Python, com Ceres | New BSD | GTSAM (BSD) para grafos de fatores | O ajuste é do motor; a restrição de GCP usa pontos constantes e fixação do gauge, ver §6.2 |
| Propagação da incerteza do controlo | Ensemble próprio sobre a etapa final, sem dependência nova | — | Ajuste de feixes próprio com prior ponderado, em Ceres | Estimativa numérica da dispersão; escalada prevista, ver ADR-007 |
| Detecção de marcas de controlo | Implementação própria sobre projeções e ajuste de elipse | — | Detectores aprendidos, à base de redes convolucionais | Sem dependência de modelos treinados; ver ADR-008 |
| Catálogo e metadados | SQLite, via `rusqlite` com SQLite embebido | MIT | PostGIS (GPL) | A escolha do modo local ou servidor decide a dependência |
| Grafo de fatores e fusão de poses | GTSAM | BSD | — | Eigen, METIS e CCOLAMD têm licenças próprias |
| Visualização e QA | Rasterização própria, em Rust | Apache-2.0 | `Open3D` (MIT), `CloudCompare` (GPL) | A visualização passa a ser interna, em `F9.E2`; o CloudCompare mantém-se como ferramenta externa de QA e o Open3D como base da filtragem de solo de `F4.E8`. Ver ADR-012 |
| Reconstrução aprendida | Sem uso na cadeia principal | — | DUSt3R, MASt3R, VGGT | Ver §11.6 de `docs/Khnumn.md`: apenas como candidato, sob verificação geométrica clássica |

---

## 3. Backends de ajuste de feixes

### 3.1 Opções

O COLMAP oferece Ceres como backend por omissão e Caspar como backend experimental acelerado por GPU. O Caspar é seleccionado por opção e exige compilação específica. Ocupa-se de forma treinada nos modelos de câmara mais simples, não suporta priors de pose nem o refinamento de poses de sensores que não sejam o de referência, e impõe restrições ao refinamento de focais e de parâmetros extra. O mapeador global não expõe o selector do Caspar.

### 3.2 Implicação para a reprodutibilidade

Backends diferentes produzem resultados numericamente diferentes. O protocolo de §8 de `processos/protocolo-benchmark.md` tem de declarar, para cada comparação, qual o backend usado e qual a tolerância entre backends, em vez de presumir equivalência. A execução de referência tem de fixar o backend.

### 3.3 Opções de Ceres

| Opção | Valor por omissão | Impacto |
|---|---|---|
| `WITH_SUITESPARSE` | `OFF` a partir da 2.3 | CHOLMOD e SPQR são GPL; ligar esta opção torna GPL o binário resultante |
| `WITH_CUDA` | `OFF` | Solver de BA em GPU por cuDSS |
| `WITH_EIGENSPARSE` | desligada | Alternativa sem GPL ao SuiteSparse, com desempenho diferente |
| `WITH_CUDA` e `WITH_SUITESPARSE` | — | Só a combinação com SuiteSparse activo pode introduzir copyleft |

### 3.4 Requisitos da 2.3

A 2.3 substitui glog e gflags por Abseil, exige C++17, CMake 3.22 ou superior e Eigen 3.3.4 ou superior. A configuração de build é parte do registo de reprodutibilidade.

---

## 4. Riscos de construção e de compatibilidade

| Risco | Descrição | Mitigação |
|---|---|---|
| Licença transitiva | Uma dependência opcional com licença copyleft altera a licença do binário | Auditoria de dependências por build e inspeção do binário distribuído |
| Contadores SuiteSparse | Activar SuiteSparse torna o binário GPL | Manter a opção desligada e registar a decisão |
| Colisão de ABI | Determinadas versões de bibliotecas de hash podem produzir binários incompatíveis com o mesmo código-fonte | Fixar versões no SBOM e verificar a configuração de build |
| Modelos de câmara | A escolha do modelo de distorção altera os intrínsecos estimados e os resíduos | Escolher o modelo mais simples que descreva a lente, conforme a documentação do motor |
| Convenção de píxel | A conversão de calibração entre ferramentas exige um desvio de meio píxel | Aplicar a conversão na importação e documentá-la |
| ONNX Runtime | Os descritores aprendidos dependem do runtime e da versão dos modelos | Fixar e registar a versão do runtime e a do modelo |
| Deriva de versões | Actualizações de bibliotecas podem alterar resultados e licenças | Rever a tabela de §18.2 no momento de cada integração |

---

## 5. Consumo de recursos por etapa

Valores a medir com o protocolo, e não a assumir. As mitigações indicadas são as que o próprio motor documenta.

| Etapa | Gargalo típico | Mitigação documentada |
|---|---|---|
| Extração de características em CPU | RAM excessiva com imagens grandes | Reduzir o tamanho máximo de imagem, deslocar a primeira oitava, limitar o número de threads |
| Correspondência em GPU | Memória de GPU esgotada | Reduzir o número máximo de correspondências por par |
| Ajuste de feixes | Tempo de repetição do ajuste global em coleções grandes | Limitar correspondências, reduzir resoluções, escolher o backend acelerado, ajustar a frequência do ajuste global |
| Reconstrução densa | Memória de GPU e de disco | Limitar o tamanho máximo de imagem, o número de vistas de origem, o raio e o passo da janela, a cache e o número de iterações |
| MVS em grande escala | Memória e tempo de execução | Particionar a cena em clusters e podar imagens redundantes, com particionamento externo |
| Rasterização de superfície | Memória do framebuffer, do depth buffer e da malha carregada | Rasterizar por blocos, com orçamento declarado por tarefa; o TIFF intermédio descomprimido é o pico a vigiar |

O número de vistas de origem por vista de referência e o raio da janela são os dois parâmetros que mais influenciam o custo da etapa densa, e os dois degradam a qualidade quando reduzidos. Qualquer optimização neste troço tem de ser avaliada contra as métricas de §5.1 do protocolo, e não apenas contra o tempo.

Valores de referência para a etapa densa em CPU, medidos num conjunto de 11 imagens com 63 MP, num portátil com processador de 4 núcleos, 8 GB de RAM e sem acelerador: mapas de profundidade em 6 minutos e 24 segundos, fusão em 7 segundos, 1,12 milhões de pontos e pico de memória residente de 2,9 GB. Estes números servem de ordem de grandeza para o dimensionamento do orçamento de recursos, e não de promessa: o custo escala com o número de imagens, a resolução e o número de vistas de origem.

Para o caminho em acelerador, a mesma métrica de custo é dominada pela memória da GPU, e não pela RAM, o que inverte a estratégia de particionamento de §16.1 de `docs/Khnumn.md` consoante o caminho escolhido.

Duas estruturas multiplicam este custo e precisam de ser orçamentadas à parte. A propagação da incerteza do controlo, por ensemble, executa a etapa final N vezes, mas as etapas anteriores são partilhadas por todos os membros e ficam em cache, pelo que o custo real é N vezes apenas a etapa final, e não N vezes o pipeline. O refinamento iterativo da via densa repete a reconstrução, e cada passagem seguinte é mais barata do que a primeira, porque parte de uma nuvem já existente. O número de execuções de ambos os casos é um parâmetro explícito, e o custo total tem de ser estimado antes de a execução começar, para que o planeador possa escolher o método de controlo e o caminho de superfície que caibam no orçamento.

A rasterização de superfície, de §13.6 de `docs/Khnumn.md`, tem um perfil de custo próprio e diferente dos anteriores. O estrangulamento não é o número de imagens nem o tempo de execução, mas a memória do raster: o framebuffer e o depth buffer são proporcionais à resolução de saída, e a malha carregada é proporcional ao número de faces. A rasterização por blocos resolve o primeiro, e a descarte do que já foi rasterizado resolve o segundo. O TIFF intermédio, sem compressão, é a escrita mais volumosa da cadeia e é por isso que é o pico a vigiar, e não o raster em si.

---

## 6. Riscos em aberto

### 6.1 Reconstrução densa sem GPU

O COLMAP não implementa reconstrução densa em CPU: a etapa exige CUDA ou, desde a 4.2, ROCm. A issue que pede suporte a CPU no motor está aberta desde 2024 e a manutenção considera a via em CPU demasiado lenta para ser útil. Isto colide com o princípio CPU-first de §3.3 de `docs/Khnumn.md`, que exige que o sistema base funcione sem GPU.

**Decisão: três caminhos declarados** (ADR-005).

| Caminho | Motor | Requisito | Licença | Densidade |
|---|---|---|---|---|
| Esparso | COLMAP `delaunay_mesher` sobre a nuvem esparsa | CPU | New BSD | Baixa |
| Denso em CPU | Motor de MVS externo, opcional e instalável à parte | CPU | AGPL ou GPL | Alta |
| Denso em acelerador | COLMAP `patch_match_stereo` | CUDA ou ROCm | New BSD | Alta, com consistência geométrica multivista |

O planeador escolhe segundo a capacidade real do host, e o caminho usado fica registado na proveniência de cada produto. O sistema promete a melhor reconstrução que a máquina suporta, e declara o custo do caminho escolhido.

Consequências e riscos residuais, que ficam abertos:

- **Degradação de densidade em CPU.** No caminho esparso a superfície provém de uma nuvem de pontos muito mais esparsa do que a densa, e o produto tem de ser rotulado. A comparação entre DSM de origens diferentes não é legítima.
- **Dependência de um componente com licença própria.** O caminho denso em CPU exige um binário instalado à parte, com aviso de licença no primeiro uso. Se o produto for distribuído com esse binário, a questão de licença de §1.1 reabre-se e tem de ser revista.
- **Inexistência de um MVS permissivo em CPU com qualidade equivalente.** A via alternativa seria um plane-sweep em PyTorch, que corre em CPU mas cuja completude medida num conjunto público é da ordem de quarenta vezes inferior à da via aceleradora. É implementação própria, contra o princípio de §3.5, e só se justifica se uma demonstração comparativa o indicar.
- **Custo de particionamento invertido.** Em acelerador, o estrangulamento é a memória da GPU; em CPU, é a RAM e o disco. A estratégia de blocos de §16.1 tem de ser diferente consoante o caminho.

### 6.2 Fluxo de pontos de controlo

Os motores de referência não fornecem um fluxo de pontos de controlo de primeira classe, e a issue que o pede no COLMAP continua aberta.

**Decisão: implementação sobre as ligações Python do COLMAP** (ADR-006). A cadeia é detectar as marcas nas imagens, segundo o procedimento de ADR-008, triangulá-las no referencial local, estimar a similaridade de 7 parâmetros para o referencial mundial de forma ponderada pelas covariâncias, substituir as posições pelas coordenadas de levantamento, declarar os pontos constantes, fixar o gauge por três pontos, correr o ajuste constrangido e propagar a incerteza do controlo por ensemble, conforme ADR-007. Tudo isto é alcançável sem bifurcar o motor.

Consequências e riscos residuais:

- **A incerteza de levantamento não entra no ajuste como prior ponderado.** Um ponto constante entra com um resíduo de reprojeção subjecto à função robusta padrão. A restrição aplicada é mais forte do que a informação de que dispõe. O ensemble de ADR-007 não corrige esta insensibilidade: mede o efeito dela, e propaga a incerteza através da não-linearidade da fixação do gauge, que é a peça que faltava. A exatidão do produto continua a ter de ser afirmada contra pontos de verificação independentes.
- **A propagação é numérica e não analítica.** Depende do número de amostras, e um número insuficiente produz uma dispersão mal estimada. O número de amostras é um parâmetro explícito, e a estimativa é a contribuição do controlo, e não a incerteza total.
- **Combinação com priors de pose não é directa.** O motor não expõe um ajuste que simultaneamente aplique priors de pose e pontos constantes. O fluxo é: priors de pose durante o mapeamento, e uma passagem final de ajuste com os pontos de controlo fixos.
- **A deteção de marcas é a etapa que mais condiciona o resultado.** A qualidade da deteção, quantas imagens cada marca aparece e com que erro de píxel, condiciona diretamente a georreferenciação, e o seu erro não aparece no erro de reprojeção. A especificação de ADR-008 reduz o problema a décimas de píxel, mas não o anula.

### 6.3 Tolerância entre backends

O número e a forma da divergência entre Ceres e Caspar, e entre solvers com e sem cuDSS, ainda não foi medido. A tolerância de §8 do protocolo só pode ser fixada depois dessa medição.

---

## 7. Registo de decisões

Cada decisão é registada com data, contexto e consequência, para que possa ser revertida ou revista sem ambiguidade.

### ADR-001 — Motor de referência: COLMAP

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O sistema precisa de SfM, MVS, malha e texturização. A shortlist inicial inclui o COLMAP, o OpenMVS e o AliceVision.

**Decisão.** O COLMAP é o motor de referência. A sua licença permissiva cobre o conjunto completo de etapas, o que dispensa o OpenMVS do caminho principal e mantém o núcleo livre de copyleft forte.

**Consequências.** A ortoimagem e a filtragem de solo passam a exigir componentes adicionais, GDAL e PDAL. A etapa densa fica condicionada a GPU, e o risco 6.1 fica aberto.

### ADR-002 — OpenMVS fora do núcleo

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O OpenMVS é a referência habitual para a etapa densa com texturização, mas está sob AGPL-3.0.

**Decisão.** O OpenMVS não integra o núcleo. É o motor do caminho denso em CPU de ADR-005, instalado à parte, sinalizado e invocado apenas pela interface de adaptador de §18.3 de `docs/Khnumn.md`, com aviso de licença no primeiro uso. É também o benchmark externo de referência para a etapa densa.

**Consequências.** O núcleo permanece livre de copyleft forte. O caminho denso em CPU passa a depender de um binário que o utilizador tem de instalar, o que é um custo de adoção explícito. Perde-se a comparação directa com uma cadeia muito usada, que é precisamente o que justifica mantê-lo como benchmark externo. A disponibilidade de um caminho CPU completo é a contrapartida que faz a licença AGPL aceitável como adaptador, e não como dependência.

### ADR-003 — SUITESPARSE desligado

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** A partir da 2.3, o Ceres passou a desactivar o SuiteSparse por omissão porque os componentes CHOLMOD e SPQR são GPL.

**Decisão.** Manter a opção desligada em todas as construções distribuídas, e auditar a dependência transitiva de qualquer motor que a active.

**Consequências.** É preciso aceitar um desempenho diferente do que se obteria com CHOLMOD activo, ou avaliar a alternativa em Eigen. A escolha tem de ser medida, não presumida.

### ADR-004 — Implementação do fluxo de pontos de controlo

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O COLMAP documenta a georreferenciação por priors de pose e por alinhamento de centros de câmara, mas não oferece um fluxo de pontos de controlo de primeira classe.

**Decisão.** Mímir implementa o método `gcp_observations` de §10.4, com pontos de controlo como observações fixas no ajuste e incerteza declarada, e declara nos relatórios o método efectivamente usado.

**Consequências.** É trabalho de implementação, não de integração, e tem de ser feito antes de qualquer afirmação de exatidão absoluta. A alternativa `similarity_transform` está disponível desde o primeiro momento e é mais fraca, devendo ser identificada como tal nos relatórios.

### ADR-005 — Três caminhos de reconstrução densa

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O COLMAP só calcula mapas de profundidade em CUDA ou ROCm, e não existe hoje um MVS sob licença permissiva com qualidade equivalente em CPU. Um plane-sweep em PyTorch corre em CPU, mas a completude medida é da ordem de quarenta vezes inferior à da via aceleradora, e é implementação própria, contra o princípio de §3.5 de `docs/Khnumn.md`.

**Decisão.** O sistema mantém três caminhos de superfície, escolhidos pelo planeador segundo a capacidade real do host e registados na proveniência de cada produto: triangulação de Delaunay sobre a nuvem esparsa, em CPU e sem copyleft; motor de MVS externo e opcional, em CPU, com aviso de licença; e reconstrução densa em acelerador, pelo motor de referência.

**Consequências.** O sistema pode correr e produzir produtos completos numa máquina sem GPU, ao preço de uma densidade menor que tem de ser declarada. A qualidade máxima continua a exigir hardware. A escolha não é adiada para a implementação, porque define o que o produto mínimo promete. O risco residual principal é a degradação silenciosa: se o relatório não identificar o caminho, um DSM de origem esparsa pode ser lido como equivalente a um derivado de nuvem densa. **Este registo é alterado por ADR-009**, que inverte a prioridade dos caminhos quando o requisito é uma densidade comparável à da via de acelerador, e nesse caso a via densa em CPU passa a ser o caminho primário.

### ADR-006 — Restrição de pontos de controlo sobre as ligações Python do COLMAP

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O COLMAP não tem fluxo de pontos de controlo de primeira classe, e a issue que o pede continua aberta. As ligações Python expõem, porém, a configuração completa do ajuste, incluindo a declaração de pontos constantes e a fixação explícita do gauge por três pontos.

**Decisão.** Mímir implementa a restrição de pontos de controlo sobre as ligações Python do motor, sem bifurcar o COLMAP: marcação das marcas, triangulação local, similaridade de 7 parâmetros com estimador robusto para o referencial mundial, substituição das posições pelas coordenadas de levantamento, declaração dos pontos como constantes, fixação do gauge por três pontos e ajuste constrangido. O método de controlo por omissão passa a ser o de priors de pose GNSS.

**Consequências.** É trabalho de implementação, e não de integração, mas é alcançável sem manter um fork e sem esperar por um ciclo de revisão upstream. A limitação do modelo — a incerteza de levantamento não entrar como prior ponderado — mantém-se, e é tratada por ADR-007, que a mede por via numérica em vez de a ignorar. Por isso a exatidão do produto continua a ser afirmada contra pontos de verificação independentes. A deteção das marcas, tratada por ADR-008, substitui a marcação manual e reduz o erro de deteção a décimas de píxel. Se uma medição comparativa mostrar que a restrição por pontos constantes subutiliza a informação de controlo face a um prior ponderado formal, a questão deve ser reaberta com uma camada de ajuste própria.

### ADR-007 — Propagação da incerteza do controlo por ensemble

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** Um ponto de controlo com covariância declarada entra no ajuste do motor de referência como posição fixa, e a sua incerteza de levantamento não entra como prior ponderado. A restrição aplicada é, por isso, mais forte do que a informação de que dispõe, e a covariância interna do ajuste é um limite optimista. A matriz de covariância 3×3 é obrigatória e por ponto, porque a incerteza de um levantamento real é anisotrópica e correlacionada, e porque dois pontos medidos com instrumentos diferentes têm incertezas de ordens de grandeza distintas.

**Decisão.** A incerteza do controlo é propagada por via numérica: a etapa final é executada N vezes, e em cada execução as coordenadas dos pontos de controlo são perturbadas por um sorteio da sua covariância. A dispersão dos resultados é a incerteza do controlo. A similaridade de 7 parâmetros que ancora a solução passa a ser ponderada pelas covariâncias, com pesos inversos à variância e limiar do estimador robusto escalado pela mesma incerteza. O número de amostras é um parâmetro explícito.

**Consequências.** A incerteza do controlo entra efectivamente no cálculo, e a estimativa capta a não-linearidade da fixação do gauge por três pontos, que uma propagação linear não capta. Em troca, a estimativa depende do número de amostras e é uma estimativa numérica, e não analítica, o que tem de ser declarado nos relatórios. A incerteza assim obtida é a contribuição do controlo, e não a incerteza total; a combinação com a covariância interna da cena é que dá a total, e a combinação só é legítima se as partes forem aproximadamente independentes, o que tem de ser verificado.

A via alternativa, um ajuste de feixes próprio em que o ponto de controlo entra como prior ponderado, é exata e analítica, mas obriga a reimplementar o ajuste e contraria o princípio de reutilizar de §3.5 de `docs/Khnumn.md`. Fica prevista como escalada, a activar se uma medição comparativa mostrar que o ensemble é instável ou demasiado caro para projetos grandes.

### ADR-008 — Especificação das marcas de controlo e da sua deteção

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O erro de marcação de um ponto de controlo não aparece no erro de reprojeção, porque o modelo é perfeitamente consistente com a marca errada. Em ensaio de campo, a taxa de deteção automática de cruzes colapsou para 14% a 35 metros de altura de voo e para zero a 40 e 45 metros, e objetos de forma aproximada em X, como folhas, foram confundidos com as cruzes, obrigando a marcação manual que consumiu 1620 segundos contra 31 segundos do método automático. O centro ponderado de um alvo circular atinge um erro quadrático médio entre 0,20 e 0,40 píxeis, e alvos codificados entre 0,2 e 0,3 píxeis.

**Decisão.** O alvo de controlo é **circular e simétrico**, e o seu tamanho é especificado em **píxeis** e não em centímetros, com verificação da compatibilidade entre a GSD planeada e o tamanho do alvo antes do voo. A deteção é automática e funciona como **refinamento local** em sub-píxel, com a projeção das coordenadas do alvo no terreno para cada imagem a servir de posição inicial, o que dispensa alvos codificados. As deteções são filtradas por consistência multivista, e o operador confirma ou rejeita as deteções sobrepostas à imagem, sem deixar de medir coordenadas de píxel.

**Consequências.** O erro de marcação deixa de ser um risco relevante: passa a ser uma a duas ordens de grandeza abaixo da incerteza de levantamento. A automatização deixa de estar bloqueada pela necessidade de intervenção humana na medição, permanecendo apenas a revisão. A verificação da GSD contra o tamanho do alvo é uma exigência de planeamento, e tem de ser feita antes do voo, sob pena de se descobrir em campo que o alvo é invisível ou demasiado pequeno. A dependência do alvo simétrico limita a escolha de desenhos não simétricos, o que é uma restrição deliberada.

### ADR-009 — Refinamento iterativo da via densa em CPU

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** A via de acelerador reduz a imagem por omissão para acelerar, e essa é uma escolha de desempenho e não uma limitação do algoritmo. A via em CPU não tem essa pressão, e pode ser conduzida por um ciclo em que cada passagem usa a nuvem anterior como priori. O mecanismo de refinamento com a estimativa anterior é o mesmo que está presente dentro de uma única passagem, nos níveis de sub-resolução do motor de MVS em CPU e na pirâmide de níveis de resolução do motor de referência, e a literatura descreve-o como convergente em poucas iterações, com a iteração final a poder ser ligeiramente pior do que a anterior.

**Decisão.** A via densa em CPU é conduzida por um ciclo de refinação com um número máximo de iterações, um limite de tempo e um limite de memória, todos declarados. A paragem é por **autoconvergência**, com um limiar declarado de ganho de densidade e um limite de taxa de outliers. A **melhor iteração** é a retida, e não a última. A primeira passagem é feita em resolução plena. A comparação com a referência de acelerador é o critério de **validação**, e não de produção. Quando o requisito é uma densidade comparável à da via de acelerador, a via densa em CPU passa a ser o caminho primário, e a via esparsa a recurso de último caso.

**Consequências.** A via em CPU pode aproximar-se da via em acelerador, mas a afirmação tem de ser medida e não presumida, e é por isso que a correspondência com a referência é uma atividade de validação. O custo é multiplicado pelo número de iterações, e esse fator tem de ser medido e comparado com a alternativa de usar um acelerador. Se o orçamento de iterações esgotar sem autoconvergência, o produto é rotulado como abaixo do alvo, com o número de iterações e o motivo de paragem, e nunca é aceite em silêncio. A inversão de prioridade dos caminhos é uma consequência que ADR-005 tinha fixado em sentido contrário e que este registo substitui.

### ADR-010 — Licença única do projeto e declaração de terceiros

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** A especificação exige que o núcleo distribuível do Mímir seja livre de copyleft forte, o que implica que o próprio projeto tem de adoptar uma licença permissiva. A escolha da licença do projeto é uma coisa distinta da escolha das licenças dos componentes de terceiros: estas não se aplicam ao código do projeto, não se combinam com a dele, e cada componente é usado sob os seus próprios termos. Uma componente pode ser distribuída sob duas licenças alternativas sem que isso constitua ambiguidade, porque quem a utiliza escolhe. O que não faz sentido é aplicar duas licenças alternativas ao mesmo código do projeto, porque então não há uma resposta única para a pergunta "sob que termos é isto distribuído".

**Decisão.** O Mímir é licenciado sob a **Apache License 2.0**, em versão única. O texto integral está no ficheiro `LICENSE` na raiz do repositório, verbatim, como a seção 4(a) da licença exige. As licenças dos componentes de terceiros são declaradas à parte, no ficheiro `THIRD-PARTY.md` na raiz, e não se aplicam ao código do projeto.

**Justificação da escolha.** A Apache-2.0 é permissiva, não impõe copyleft, e traz uma concessão explícita de patentes na sua seção 3, o que responde diretamente ao risco identificado na especificação: uma licença de código, por si só, não resolve questões de patentes ou de licenças de dados. É a mesma razão que levou o OpenCV a migrar para ela em 2020. A licença impõe ainda a preservação dos avisos de atribuição e a entrega de uma cópia da licença a quem recebe o binário, o que é coerente com a exigência de inventário de licenças e de SBOM da especificação.

**Consequências.** Quem utiliza o Mímir tem de cumprir a Apache-2.0, incluindo a preservação dos avisos e a entrega da licença. Quem integra componentes com licença copyleft tem de o fazer por um processo externo, conforme a política da seção 1, e a licença do projeto não interfere com essa utilização. A designação do titular dos direitos tem de ser confirmada antes de qualquer distribuição, porque o texto da licença exige um aviso de copyright identificável.

### ADR-011 — Nome do projeto: Khnumn

**Estado:** proposta · **Data:** 2026-10-20

**Contexto.** O projeto usava o nome de trabalho Mímir, da figura nórdica associada à sabedoria. O nome não era adequado por duas razões. A primeira é de âmbito: Mímir designa uma figura da tradição do saber e da memória, o que descreve mal um sistema cuja preocupação central é a geometria medida e a sua rastreabilidade. A segunda é de livre uso: o nome está ocupado pelo Grafana Mimir, um sistema distribuído de métricas de grande escala com o mesmo domínio técnico, o que tornaria a identificação entre as duas coisas confusa.

Um nome novo tem de satisfazer três condições: ser semanticamente ajustado ao que o sistema faz, estar livre de conflito, e ser utilizável como identificador técnico — porque o projeto vai ter crates, um pacote Python, um directório de motor, um nome de motor e um directório de trabalho.

**Decisão.** O projeto passa a chamar-se **Khnumn**, com a grafia ASCII `khnumn` para identificadores.

Khnumn é o deus egípcio de cabeça de carneiro, divindade da criação e do Nilo, e o padroeiro da olaria. Segundo o mito, moldou os primeiros corpos humanos numa roda de oleiro. A metáfora é dupla e ambas as camadas servem. A forma é a imagem central: um sistema que recebe material bruto em observações dispersas e o transforma numa superfície coerente e defensável faz exatamente o que o oleiro faz com o barro. A roda é o varrimento da plataforma, e a mão que molda é o ajuste. E o mesmo deus é o das águas que inundam e renovam a terra, o que corresponde a um novo levantamento a renovar o modelo de um sítio.

O nome satisfaz ainda as condições de identificador. Não exige transliteração — ao contrário de um nome nórdico, em que teria de se decidir entre a forma de exibição com diacríticos e a forma ASCII — porque a grafia é ASCII pura. Tem seis caracteres, é pronunciável, e não contém sufixos que entrem em conflito com famílias de nomes já estabelecidas.

**Verificação.** A verificação foi feita a 2026-10-20, sobre 74 candidatos gerados a partir dos conceitos da própria especificação, da mitologia nórdica e da mitologia egípcia. Cada candidato foi submetido a cinco índices: busca de nome exato de repositórios no GitHub, projectos no GitLab, PyPI, crates.io e npm, e resolução de DNS em `.com`, `.org`, `.io`, `.dev`, `.net` e `.app`. Os finalistas foram ainda verificados por pesquisa web, para apanhar empresas e produtos fora do domínio do código.

O resultado para Khnumn: **zero** correspondências de nome exato no GitHub, **zero** em PyPI, crates.io, npm e GitLab, e **nenhum** domínio activo em nenhum dos seis sufixos testados. As únicas ocorrências de "Khnumn" na web são uma figura histórica egípcia, um nome próprio e uma entrada de spam.

**Consequências.** A mudança é mecânica e não altera nenhum requisito, interface, dependência ou decisão técnica: 156 ocorrências de nome em sete ficheiros, a renomeação do ficheiro de especificação e do directório de trabalho, e a criação de um `NOTICE` com o aviso de copyright, que a licença Apache-2.0 exige em ficheiro próprio para que o texto da licença permaneça intacto.

Os registos históricos de decisão mantêm o nome vigente na data em que foram escritos, e a convenção está declarada no topo do registo. Reescrevê-los tornaria a sequência anacrónica, e a história de um projeto é um activo, não um texto para uniformizar.

A designação do titular dos direitos é provisoriamente *Khnumn contributors*, e tem de ser confirmada antes de qualquer distribuição, tal como previsto em ADR-010.

### ADR-012 — Rasterização de superfície no núcleo

**Estado:** proposta · **Data:** 2026-10-22

**Contexto.** O sistema promete em §1.1 de `docs/Khnumn.md` mapas de cobertura, densidade, qualidade e incerteza, e §22 prevê a deteção de zonas com cobertura insuficiente; nenhum desses mapas tem produtor, e nenhum dos campos de §15.1 que dependem de uma projecção — a cobertura espacial, a consistência entre vistas e o desvio introduzido pela simplificação — é hoje apurável. A visualização está atribuída ao Open3D e ao CloudCompare, que são ferramentas com interface gráfica, e o CloudCompare é GPL-3.0, o que o exclui do produto pela política de §1. O ambiente de referência não tem acelerador, e §3.3 proíbe que o acelerador seja um pressuposto do binário distribuído.

**Decisão.** O Khnumn implementa a rasterização de superfície em Rust, no núcleo, sem dependências de execução, determinística e sem necessidade de ecrã. A projecção usada é a mesma função que apura os resíduos de reprojecção, e implementa a família de modelos de câmara do motor de SfM, e não apenas o modelo pinhole de §10.1.

**Alternativas avaliadas.** O Open3D e o CloudCompare cobrem a necessidade de ver, mas não são adequados ao produto: têm interface gráfica, e o segundo é copyleft forte. Um motor de GPU violaria o princípio CPU-first e tornaria o acelerador um pressuposto do formato de saída. Um motor de rasterização externo, de qualquer espécie, acrescentaria uma dependência com a mesma função de um componente que o projecto pode implementar com uma dependência de recursos já orçada.

**Consequências.** A visualização passa a ser interna, e a linha de §2 sobre visualização e QA muda de papel: o Open3D mantém-se como base da filtragem de solo de `F4.E8`, e o CloudCompare como ferramenta externa de QA. É trabalho de implementação e não de integração, e por isso tem de ser validado contra casos analíticos e contra a projecção do próprio motor, e não apenas observado. A rasterização não substitui o GDAL na ortoimagem de §13.5, que é uma etapa de reprojecção de rasters: as duas resolvem problemas diferentes, e a §13.6 não produz ortoimagem. A decisão cria um risco próprio, registado em §23 de `docs/Khnumn.md`: um raster produzido com um modelo de câmara diferente do modelo das observações é um produto errado que não denuncia o erro, porque a plausibilidade visual não é um indício de erro geométrico.

**Procedência da técnica.** A técnica de rasterização de triângulos com z-buffer e interpolação de profundidade por 1/z é de uso corrente, e anterior a qualquer implementação concreta de referência; a implementação do Khnumn deriva das descrições publicadas (Heckbert 1984; Bourke) e da especificação de modelos de câmara do COLMAP, com as fontes em §26 de `docs/Khnumn.md`. Um repositório externo foi consultado quanto à funcionalidade necessária —z-buffer, corte no plano near, níveis de detalhe, cor por campo escalar— e o seu autor declarou autorização de uso e melhoria; nenhum código, expressão ou estrutura de ficheiros desse repositório foi reproduzido, e nenhum dos seus ficheiros integra o Khnumn.

### ADR-013 — TIFF intermédio em Rust e publicação em COG na camada científica

**Estado:** proposta · **Data:** 2026-10-22

**Contexto.** §19.2 de `docs/Khnumn.md` prefere GeoTIFF e Cloud Optimized GeoTIFF para rasters georreferenciados, e a §18.2 já aponta o `rasterio` como a via. Publicar um COG exige tilling, overviews e compressão, que a escrita directa de TIFF não produz. Rust não tem codec de PNG, e o `tiff` em Rust não faz a organização de COG. A CRS de destino é uma necessidade geodésica, e a §18.1 determina que a geodesia passe obrigatoriamente pela PROJ.

**Decisão.** O núcleo escreve um TIFF intermédio, sem compressão, e a camada científica reescreve-o como Cloud Optimized GeoTIFF, com CRS, `nodata`, overviews e as tags de proveniência e de legenda.

**Consequências.** São dois produtos com uma linhagem, e não um: o intermédio tem hash e é produto intermédio, e o publicado é o produto final. O campo `format` do esquema de produto distingue `tiff` de `cog`. A divisão respeita a §18.1, porque a transformação para o CRS de destino é geodésia e a geodesia é da camada científica; o núcleo fica em espaço de câmara, onde não há CRS. A auditoria de licenças tem de cobrir a árvore transitiva do wheel do `rasterio`, e não apenas o requisito directo, ou a afirmação de §1.2 não se sustenta.
