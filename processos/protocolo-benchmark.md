# Khnumn — Protocolo de benchmark (Fase 0)

**Âmbito:** este documento operacionaliza a Fase 0 de `docs/Khnumn.md`. Define como se mede, com que hardware, sobre que dados, contra que referência e com que tolerâncias. Não é um relatório de resultados: é o protocolo que torna os resultados comparáveis e auditáveis.
**Convenção de referências:** as menções a outros documentos deste repositório usam o caminho relativo à raiz do repositório.


**Estado:** proposta para fixação na Fase 0. Os valores concretos que dependem do primeiro alvo de validação estão assinalados como `A FIXAR` e não devem ser preenchidos por omissão.

**Versão do protocolo:** 0.1.0 · **Data:** 2026-10-20 · **Idioma:** Português europeu

---

## Índice

1. [Objectivo e princípios](#1-objectivo-e-princípios)
2. [Hardware de referência](#2-hardware-de-referência)
3. [Conjuntos de dados](#3-conjuntos-de-dados)
4. [Controlo e verificação](#4-controlo-e-verificação)
5. [Métricas](#5-métricas)
6. [Tolerâncias por classe de projeto](#6-tolerâncias-por-classe-de-projeto)
7. [Regra de aceitação de uma melhoria](#7-regra-de-aceitação-de-uma-melhoria)
8. [Reprodutibilidade](#8-reprodutibilidade)
9. [Template de relatório](#9-template-de-relatório)
10. [Registo de execuções](#10-registo-de-execuções)

---

## 1. Objectivo e princípios

### 1.1 Objectivo

Responder a uma pergunta por vez, com dados que permitam respondê-la. O benchmark existe para sustentar decisões de engenharia, e não para produzir tabelas de comparação decorativas.

Cada execução responde a uma pergunta declarada, com uma variável alterada de cada vez. Uma execução que muda vários parâmetros e produz um número final não é um benchmark; é uma demonstração.

### 1.2 Princípios

| Princípio | Implicação prática |
|---|---|
| Mesmos dados | Todas as configurações comparadas correm sobre exatamente os mesmos ficheiros, pelos mesmos hashes |
| Mesma referência | O mesmo conjunto de pontos de verificação, com o mesmo ficheiro de coordenadas |
| Condições de hardware documentadas | CPU, RAM, armazenamento, sistema operativo, GPU e drivers registados por execução |
| Pré-processamento explícito | Qualquer filtragem, reamostragem, pirâmide ou conversão é declarada e igualada entre comparações |
| Parâmetros comparáveis | Os parâmetros que diferem são o objeto da comparação; os restantes são declarados como fixos |
| Nada de capturas de ecrã | A comparação é feita sobre métricas, com unidades e número de amostras |
| Rasterizações comparáveis | As mesmas câmaras, o mesmo modelo de câmara, a mesma resolução de saída e a mesma semente; a comparação é feita sobre os campos numéricos, nunca sobre as imagens |
| Repetibilidade | Cada execução é repetida um número declarado de vezes, e a dispersão é reportada |

### 1.3 O que este protocolo não faz

Não avalia a qualidade subjectiva de uma ortoimagem, nem a aparência de uma malha, nem a plausibilidade visual de uma nuvem. Essas intuições são úteis para detectar problemas, mas não são métricas. Quando uma inspeção visual sugere um problema, a execução tem de ser instrumentada para o confirmar ou o refutar.

Uma rasterização tem o mesmo estatuto. É um instrumento de diagnóstico: o que entra num relatório são os campos quantificados, e a imagem nunca é um critério de aceitação. Um produto de rasterização nunca é, por si só, um portão de aceitação; é o instrumento para apurar uma das métricas de §15.1 de `docs/Khnumn.md`, e a aceitação continua a ser decidida pelas tolerâncias de §15.5 e pelos pontos de verificação independentes.

---

## 2. Hardware de referência

Sem hardware de referência declarado, qualquer afirmação sobre tempo, RAM ou consumo energético é incomparável. O protocolo exige, no mínimo:

| Elemento | Valor | Estado |
|---|---|---|
| CPU (modelo, núcleos, frequência base) | Intel Core i3-5005U, 2 núcleos físicos / 4 threads, 2,00 GHz | medido a 2026-10-21 |
| RAM mínima e RAM de trabalho | 3 826 MiB totais; orçamento de trabalho 500 MiB com 300 MiB de folga, pico admissível 800 MiB | medido a 2026-10-21 |
| Armazenamento (tipo, capacidade, velocidade) | Partição única de 109 GB; ~40 GB livres na medição | medido a 2026-10-21 |
| Sistema operativo e versão do kernel | Zorin OS 18.1 (base Ubuntu 24.04), kernel Linux 7.0.0-38-generic x86_64 | medido a 2026-10-21 |
| GPU (modelo, memória, driver) | **ausente** — o acelerador é opcional por princípio de §3.3 e não existe neste ambiente | medido a 2026-10-21 |
| Ambiente de runtime (contentor, dependências) | venv Python 3.12.3 com pins em `requirements.lock`; Rust estável 1.98.1 com `Cargo.lock` versionado; nenhum contentor, por decision de F0.E7 | medido a 2026-10-21 |

O registo completo, com o que este orçamento torna impossível, está em
[`processos/hardware-referencia.md`](hardware-referencia.md).

### 2.0 Regra de medição de memória

O pico de memória residente de uma tarefa é lido de `/proc/<pid>/status`
(`VmHWM`), com amostragem de 50 ms, no processo que executa a tarefa. O valor
observado é um limite inferior do pico real, e a resolução da amostragem
acompanha o valor em cada relatório.

O uso de swap é **falha de orçamento** e não folga: uma tarefa que usa swap
excedeu o orçamento de trabalho. A medição de energia, quando não há
contador acessível, é reportada como proxy de tempo e utilização, conforme
§2.2.

### 2.1 Regra de comparação

Qualquer execução que corra sobre hardware diferente da referência é comparada apenas em métricas geométricas e nunca em tempo ou memória. As métricas de recurso só são comparáveis dentro da mesma máquina, e o relatório tem de indicar a máquina de cada execução.

### 2.2 Medição de energia

Quando a medição directa não estiver disponível, o relatório usa tempo e utilização como proxies e diz explicitamente que são proxies (§16.6). As interfaces a tentar, por ordem de preferência, são `intel-rapl` e `powercap` em Linux, as APIs de energia da GPU, e a API de energia do sistema em Windows. `powertop` é identificado como estimativa.

**Neste ambiente:** nenhum destes interfaces está acessível, e a medição de
energia é reportada como proxy de tempo e utilização, com essa declaração
explícita.

---

## 3. Conjuntos de dados

### 3.1 Selecção

Um conjunto é adotado se cumprir, cumulativamente:

1. licença de uso e de redistribuição compatível com o regime do projeto;
2. referência independente com exatidão documentada, quando a pergunta o exige;
3. capacidade de repetir a execução nas condições do §2.

A notoriedade não é critério de seleção.

### 3.2 Shortlist inicial

| Conjunto | Pergunta que serve | Referência disponível | Limitações |
|---|---|---|---|
| Campo de ensaio com GCPs e pontos de verificação | Georreferenciação e exatidão absoluta da cadeia completa | Pontos medidos por topografia | Escala e custo de aquisição |
| ETH3D | Qualidade da reconstrução densa e da texturização | Varrimentos de laser | Não valida escala nem datum |
| DTU | Exactidão densa em cenário controlado | Point clouds de luz estruturada | Cenário artificial, escala reduzida |
| Tanks&Temples | Volume e velocidade em grande escala | Trajectória e avaliação qualitativa | Sem verdade-fundamento densa |
| LaMAR | Robustez de SfM em grande escala e em sequências | Verdade-fundamento de SfM e marcas | Capturas de AR, não drone |
| ISPRS Vaihingen / Potsdam | Classificação de solo e produção de DTM | Rótulos de classes | Cobertura aérea, não SfM |
| ORB / sequência de vídeo próprio | Regime de vídeo de §12 e de rolling shutter | A definir em campo | Requer aquisição própria |

### 3.3 Partições

Cada conjunto é dividido em partições fixas e declaradas: `calibração`, `ajuste`, `verificação` e `teste`. As partições são ficheiros com os seus hashes, e a partição de verificação nunca é lida durante o ajuste. A exclusão é imposta pelo sistema, e não por convenção do operador.

---

## 4. Controlo e verificação

### 4.1 Separação

Os pontos de controlo entram no ajuste. Os pontos de verificação não entram em nada. A separação é imposta pelo carregamento: o ficheiro de verificação é lido apenas pelo validador, depois de o modelo estar congelado.

A implementação desta imposição é a seguinte, e é verificável:

| Momento | Quem pode ler o ficheiro de verificação | Como é imposto |
|---|---|---|
| Ingestão dos pontos de controlo | O carregador de controlo | O ficheiro é carregado com `role: control` e entra no ajuste |
| Marcação e ajuste | O carregador de controlo | O ficheiro de verificação não está carregado; as marcas detetadas são as dos pontos de controlo |
| Validação | O validador | O ficheiro de verificação é lido **depois** de o modelo estar congelado, e só para comparar |

Consequência prática: a exclusão é uma propriedade da carga, e não uma
instrução que o operador cumpre. Um operador que não saiba a regra não
consegue violá-la por descuido.

O esquema que valida cada ponto de controlo e de verificação é
[`schemas/controlo-v1.schema.json`](../schemas/controlo-v1.schema.json), e
exige a covariância 3×3, o método, o instrumento, a data e o operador.

### 4.2 Número de pontos

Os critérios normativos de `docs/Khnumn.md` §15.5 fixam um mínimo de trinta pontos de verificação para que a avaliação seja considerada plenamente conforme. Abaixo desse número, a avaliação é declarada como exploratória e o estado do produto não pode ser `PASS`.

| Quantidade | Mínimo | Origem |
|---|---|---|
| Pontos de verificação | 30 | ASPRS ed. 2 (2023), por argumento de teorema central-limite |
| Pontos de controlo | 3 | O gauge é fixado por três pontos (`docs/Khnumn.md` §10.4, passo 4) |
| Pontos de controlo recomendados | 8 a 15 | Para que a ponderação por variância e a propagação de incerteza tenham significado; abaixo de 5 o alinhamento é frágil |
| Exactidão dos pontos de controlo | ≈3× melhor que a do produto | USGS OFR 2023-1033 |
| Exactidão dos pontos de verificação | Declarada e incorporada na exactidão do produto | ASPRS ed. 2: a incerteza do ponto de verificação entra no cálculo, e não é tratada como nula |

### 4.3 Medição e registo

Cada ponto de verificação é registado com: coordenadas, CRS, datum, método de medição, precisão declarada, data de medição e quem a fez. A incerteza do ponto de verificação entra no cálculo da exatidão do produto, e não é tratada como nula.

### 4.4 Método de controlo

O método de controlo é o de `docs/Khnumn.md` §10.4, é declarado na configuração do projeto e é registado no relatório de cada execução. A política é:

| Método | Quando se aplica | Estado admissível do produto |
|---|---|---|
| `gnss_pose_priors` | Método por omissão, sempre que o GNSS tem qualidade suficiente | `PASS`, com a incerteza GNSS declarada |
| `gcp_observations` | Quando o projeto exige exatidão de levantamento e existem pontos de controlo medidos | `PASS`, com a incerteza propagada declarada |
| `similarity_transform` | Último recurso, quando não existe nem GNSS utilizável nem pontos de controlo | Nunca `PASS`; no máximo `PASS_WITH_WARNINGS` ou `NOT_VALIDATED`, com causa explícita |

A alteração do método obriga a repetir integralmente o ajuste e a validação, e os resultados de métodos diferentes não são comparáveis entre si.

A propagação da incerteza é, por omissão, numérica, por ensemble, conforme ADR-007. O número de amostras é um parâmetro explícito e tem de constar do relatório, e a medição dessa propagação é sujeito de §4.7.

### 4.5 Comparar métodos de controlo

Comparar métodos de controlo é uma pergunta de benchmark e não uma escolha de configuração. Convém responder a duas variantes separadamente:

1. **Qual é o mais exato?** Comparar `RMSE_H`, `RMSE_V` e `RMSE_3D` contra o mesmo conjunto de pontos de verificação, com os mesmos dados, o mesmo hardware e o mesmo número de execuções.
2. **Que custo tem cada um?** Comparar tempo, pico de RAM, memória de GPU e o número de marcas que exigem intervenção humana, que é o custo que não aparece nas métricas geométricas.

O resultado é a base da revisão do método por omissão e da decisão ADR-006, e é registado em `processos/decisoes-motores.md`.

### 4.6 Blunders

Uma discrepância superior a três vezes o RMSE-alvo em qualquer componente é tratada como blunder: é investigada, explicada e registada. Blunders não são descartados em silêncio, e a remoção de um é uma alteração do resultado que tem de constar do relatório.

### 4.7 Medir a propagação por ensemble

A propagação da incerteza do controlo é numérica, e por isso tem de ser medida como tal. Uma execução que declare a incerteza propagada tem de declarar também como essa incerteza foi obtida, para que possa ser comparada e para que se possa saber se o número de amostras foi suficiente.

O que se mede:

1. **Número de amostras efectivamente usadas** e o número mínimo declarado. A dispersão estimada a partir de um número insuficiente de amostras é mal estimada, e o relatório tem de distinguir a uma e a outra coisa.
2. **Convergência da dispersão.** Repetir o ensemble com subconjuntos de tamanho crescente e observar se a estimativa estabiliza. A sequência da dispersão agregada em função do número de amostras é a evidência de que a estimativa é fiável.
3. **Comparação com a covariância analítica.** A similaridade ponderada de 7 parâmetros tem uma covariância analítica. A dispersão do ensemble e essa covariância têm de ser comparadas, e a diferença medida: uma divergência grande indica que a propagação linear estava a perder a não-linearidade da fixação do gauge, o que é a razão de o ensemble existir.
4. **Decomposição da incerteza.** A incerteza total tem de ser decomposta nas parcelas de controlo e de cena, e a fração de controlo tem de ser reportada. É essa fração que diz se o produto está limitado pelo controlo ou pela cena, e é a informação que permite decidir se vale a pena melhorar o levantamento de campo.

Uma medição que mostre que a propagação linear e o ensemble concordam dentro da tolerância, para um número modesto de amostras, é um argumento a favor da via simples. Uma medição que mostre divergência é o argumento a favor da escalada prevista em ADR-007.

---

## 5. Métricas

### 5.1 Métricas geométricas obrigatórias

| Métrica | Unidade | Nota |
|---|---|---|
| `RMSE_X`, `RMSE_Y` | m (ou unidade do CRS) | Por eixo |
| `RMSE_H` | m | Combinado de X e Y, conforme §15.5 |
| `RMSE_V` | m | Vertical |
| `RMSE_3D` | m | Combinado de H e V, conforme §15.5 |
| Erro médio por eixo | m | Viés; esperado abaixo de 25% do RMSE-alvo |
| Mediana e percentis (P50, P90, P95) | m | A mediana e os percentis não substituem o RMSE |
| Número de pontos de verificação | — | Declarado com a métrica |
| Erro de reprojeção | px | Diagnóstico interno, não portão de aceitação |
| Erro de reprojeção por imagem | px | Para detectar imagens com problema |
| Completude da nuvem | % da área | Cobertura e densidade |
| Distância ponto-superfície contra referência | m | Quando existe superfície de referência |
| Descontinuidade em costuras de mosaico | m | Limite de 2 × `RMSE_H` |
| Componentes desconexos do modelo | — | Diagnóstico de cobertura |
| Dispersão do ensemble | m | Propagação da incerteza do controlo, por ponto e agregada |
| Número de amostras do ensemble | — | Eficácia da estimativa numérica |
| Fracção de incerteza atribuível ao controlo | % | Diagnóstico: o produto está limitado pelo controlo ou pela cena? |
| Densidade e completude da nuvem | — | Por iteração, para o refinamento iterativo |
| Dispersão de densidade entre iterações | — | Critério de autoconvergência |
| Erro de deteção das marcas de controlo | px | Qualidade da marcação automática |

### 5.2 Métricas de recurso

Tempo de parede por etapa, pico de RAM, tempo de CPU acumulado, espaço temporário, tráfego de leitura e escrita e energia, quando mensurável. Todas com a máquina associada. São de registo separado o custo do ensemble de propagação, o número de membros e o custo total, e o custo do refinamento iterativo, o número de iterações e o custo por iteração, porque são as duas estruturas que multiplicam o custo total do projeto.

### 5.3 Métricas de reprodutibilidade

Número de execuções repetidas, dispersão das métricas geométricas entre execuções, e diferença máxima face à execução de referência, dentro da tolerância declarada em §8.

---

## 6. Tolerâncias por classe de projeto

As tolerâncias são fixadas **antes** da execução, por classe de projeto, e não escolhidos depois de ver os resultados. A tabela é preenchida na Fase 0.

| Classe | GSD alvo | `RMSE_H` alvo | `RMSE_V` alvo | Completude mínima | Referência normativa |
|---|---|---|---|---|---|
| `levantamento_agricola_rtk` | 2,0 cm a 3,0 cm | 0,05 m | 0,08 m | 95 % da área do alvo | ASPRS Positional Accuracy Standards, ed. 2 (2023); ISO 17123-10; ISO 19623 |
| `levantamento_cadastral` | 1,5 cm | 0,03 m | 0,05 m | 98 % da área do alvo | ASPRS ed. 2 (2023); USGS OFR 2023-1033 (pontos de controlo com ≈3× melhor exactidão) |
| `reconstrucao_densa_sem_referencia` | 1,0 cm a 5,0 cm | — | — | 90 % da área de referência | Sem norma aplicável: o estado é `NOT_VALIDATED` por omissão |

A referência normativa por omissão é a edição 2 (2023) dos ASPRS Positional Accuracy Standards, com os limiares de blunder e de erro médio de §15.5. Um projeto que declare outra referência tem de a indicar no relatório e no ficheiro de configuração.

### 6.0 Leitura da tabela

| Coluna | Significado |
|---|---|
| `RMSE_H` alvo | Erro quadratico medio horizontal, combinado de `RMSE_X` e `RMSE_Y` |
| `RMSE_V` alvo | Erro quadratico medio vertical |
| Completude mínima | Fração da área de referência coberta por observações válidas |
| `—` | A tolerância não é aplicável a esta classe, e a sua ausência é declarada, não zero |

As três linhas correspondem a três decisões diferentes, e não a três
variantes da mesma:

1. **`levantamento_agricola_rtk`** é a classe do alvo primário
   (`processos/alvo-validacao.md` §2). É a única classe em que o produto
   pode ser declarado conforme, porque é a única com pontos de verificação
   independentes.
2. **`levantamento_cadastral`** é mais exigente e exige pontos de controlo
   com cerca de três vezes melhor exactidão do que a exigida ao produto
   (USGS OFR 2023-1033).
3. **`reconstrucao_densa_sem_referencia`** é a classe em que cai, por
   omissão, qualquer reconstrução feita sobre os conjuntos públicos. Sem
   referência independente, o estado é `NOT_VALIDATED`, e a linha não
   transporta tolerâncias de RMSE precisamente porque não há com que
   comparar.

### 6.0.1 Regras que acompanham as tolerâncias

| Regra | Valor | Origem |
|---|---|---|
| Número mínimo de pontos de verificação | 30 | ASPRS ed. 2 |
| Erro médio em relação ao `RMSE_H` alvo | < 25 % | ASPRS ed. 2 |
| Discrepância que constitui *blunder* | > 3 × o `RMSE` alvo, em qualquer componente | ASPRS ed. 2 |
| Descontinuidade admissível em costura de ortomosaico | ≤ 2 × `RMSE_H` | ASPRS ed. 2 |
| Erro de reprojecção | **diagnóstico, não portão de aceitação** | `docs/Khnumn.md` §15.4 |

O erro de reprojecção é um diagnóstico interno do ajuste. Um modelo com
erro de reprojecção muito baixo pode ter a escala ou a georreferenciação
erradas, e o portão de aceitação é a exactidão medida contra pontos de
verificação independentes.

### 6.1 Validação da via densa em CPU contra a referência de acelerador

A afirmação de que a via densa em CPU se aproxima da via de acelerador é medida, e esta seção define como. O protocolo é executado como uma atividade de validação, e não como parte da execução de produção, porque exige uma máquina com acelerador.

Condições da comparação:

- a **mesma cena**, com os **mesmos ficheiros de entrada** e a mesma resolução de entrada nos dois caminhos;
- o **motor de acelerador na melhor configuração**, e não na configuração de omissão, que reduz a imagem para acelerar. A referência é o melhor que o caminho de acelerador consegue, e não o mais rápido;
- a mesma deteção de marcas e o mesmo conjunto de pontos de controlo;
- o mesmo número de iterações de refinamento, quando aplicável, para que a comparação seja entre caminhos e não entre configurações de iteração.

Métricas da comparação:

| Métrica | Definição |
|---|---|
| Densidade | Pontos por unidade de área, e a sua distribuição espacial, não apenas o total |
| Completude | Fração da área de referência coberta por pontos dentro de uma tolerância de distância |
| Distância ponto-superfície | Distância de cada ponto da via em CPU à superfície da referência, em ambas as direções |
| Taxa de outliers | Fração de pontos que não são consistentes com a superfície de referência |
| Resíduo de reprojeção | Diagnóstico de consistência interna de cada caminho |

A aceitação é por limiares declarados, e não por semelhança global: cada métrica tem de estar dentro de uma percentagem declarada da referência. A comparação é feita por sub-região, e não apenas no total, porque uma diferença grande numa zona pequena é precisamente o tipo de defeito que um total agregado esconde.

O resultado é registado como uma das entradas da validação de cada classe de projeto, e é o que sustenta a afirmação sobre a proximidade entre os dois caminhos. Enquanto não for medida, essa afirmação não é feita.

---

## 7. Regra de aceitação de uma melhoria

Uma alteração só é integrada como padrão se, cumulativamente:

1. passar os testes de correção;
2. não degradar nenhuma métrica geométrica além da tolerância acordada;
3. mostrar benefício mensurável no objectivo declarado;
4. ter comportamento de falha documentado;
5. manter a proveniência e os metadados;
6. ser reproduzível no hardware de referência.

Um ganho de tempo acompanhado de um aumento do erro vertical para além do limite acordado não é uma melhoria, é uma troca. A troca tem de ser explícita, medida e aceite por quem define a tolerância.

---

## 8. Reprodutibilidade

### 8.1 Nível exigido

O protocolo declara, por classe de comparação, um de três níveis:

- **Identidade binária:** os produtos têm de ser idênticos byte a byte. Exigível apenas onde não há paralelismo nem bibliotecas de terceiros com ordem de soma indeterminada.
- **Equivalência numérica:** as métricas têm de concordar dentro de uma tolerância explícita, por exemplo `1e-6` em erro de reprojeção e `1e-3` m nas coordenadas de pose.
- **Equivalência de métricas:** apenas as métricas agregadas têm de concordar dentro de tolerância.

Para geometria científica, a tolerância tem de ser escrita. "Resultados equivalentes" sem número não é um critério.

### 8.2 Fontes de não determinismo a registar

Ordem de redução numérica em somas paralelas, versões de bibliotecas, semente aleatória,Threads e afinação de processadores, ordem de leitura de ficheiros e hardware de execução.

### 8.3 Procedimento

Cada execução regista: hash de cada entrada, hash de cada saída, parâmetros, versões de software e de bibliotecas, versões de modelos quando aplicáveis, decisão do planeador, resíduos do ajuste, e o estado final.

---

## 9. Template de relatório

```
Relatório de benchmark — <id da execução>

Data:                <AAAA-MM-DD>
Questão:             <o que esta execução responde>
Hipótese:            <o que se espera e porquê>
Variável alterada:   <parâmetro único>

Dados
  Conjunto:          <nome e partição>
  Hashes de entrada: <lista ou ficheiro de hashes>
  Referência:        <ficheiro de pontos de verificação e n>

Ambiente
  Máquina:           <identificador conforme §2>
  Software:          <versões e SBOM>
  Semente:           <valor ou N/A>

Configuração
  <ficheiro de configuração integral, versionado>

Controlo
  Método:                 <gnss_pose_priors | gcp_observations | similarity_transform>
  Pontos de controlo:     <n, com covariância e metadados de cada um>
  Propagação:             <ensemble | analytic_similarity | none>
  Amostras do ensemble:   <n usado, mínimo declarado, convergência observada>
  Dispersão por ponto:    <agregada e por ponto>
  Fracção de controlo:    <% da incerteza total atribuível ao controlo>

Superfície
  Caminho:                <sparse_delaunay | dense_cpu | dense_accelerator>
  Iterações:              <n realizada, n máxima, motivo de paragem>
  Densidade por iteração: <tabela>
  Melhor iteração:        <índice>
  Abaixo do alvo:         <sim | não>

Resultados
  Métricas geométricas:   <tabela completa de §5.1, com n>
  Métricas de recurso:    <tabela completa de §5.2, com máquina>
  Repetições:             <k execuções, dispersão>

Estado:                   <PASS | PASS_WITH_WARNINGS | FAIL | NOT_VALIDATED>
Causas:                   <se não PASS, a causa concreta>
```

---

## 10. Registo de execuções

Cada linha é uma execução. O registo é acumulativo e acompanha o projeto.

| ID | Data | Questão | Variável | Hardware | Dados | Estado | Relatório |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — |

---

## Nota de âmbito

Este protocolo não substitui a nota de rigor inicial de `docs/Khnumn.md`. Os resultados produzidos segundo este protocolo são medições sob condições declaradas; a exatidão alcançável depende ainda da resolução, calibração, geometria de captura, georreferenciação, qualidade dos dados e de validação independente.
