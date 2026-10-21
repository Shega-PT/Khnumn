# Khnumn — Especificação técnica de um sistema modular de fotogrametria, videogrametria e reconstrução geoespacial

**Estado do documento:** proposta técnica inicial para investigação e desenvolvimento (I&D)  
**Versão:** 0.1.0  
**Data:** 2026-10-20  
**Idioma:** Português europeu  
**Nome de trabalho:** Khnumn — nome do deus egípcio que moldava as primeiras formas humanas numa roda de oleiro, e cujas águas do Nilo renovavam a terra. A nomenclatura anterior, Mímir, foi abandonada por estar ocupada pelo sistema Grafana Mimir; a verificação de que Khnumn não correspondia a nenhum repositório, pacote, empresa ou domínio foi feita a 2026-10-20 e está registada em ADR-011.

> **Nota de rigor:** este documento define uma arquitetura proposta, não afirma que o sistema já existe nem que os algoritmos propostos foram validados. A precisão alcançável depende da resolução, calibração, geometria de captura, georreferenciação, qualidade dos dados e validação independente. As decisões aqui descritas devem ser verificadas por experiências reprodutíveis.
**Convenção de referências:** as menções a outros documentos deste repositório usam o caminho relativo à raiz do repositório.

## Índice

1. [Resumo executivo](#1-resumo-executivo)
2. [Objetivos, âmbito e exclusões](#2-objetivos-âmbito-e-exclusões)
3. [Princípios de engenharia](#3-princípios-de-engenharia)
4. [Vocabulário e produtos de saída](#4-vocabulário-e-produtos-de-saída)
5. [Tipos de dados e limites de compatibilidade](#5-tipos-de-dados-e-limites-de-compatibilidade)
6. [Arquitetura lógica](#6-arquitetura-lógica)
7. [Modelo de dados e proveniência](#7-modelo-de-dados-e-proveniência)
8. [Ingestão, validação e normalização](#8-ingestão-validação-e-normalização)
9. [Deteção do cenário e seleção de pipeline](#9-deteção-do-cenário-e-seleção-de-pipeline)
10. [Calibração, geometria e georreferenciação](#10-calibração-geometria-e-georreferenciação)
11. [Reconstrução SfM e ajuste de feixes](#11-reconstrução-sfm-e-ajuste-de-feixes)
12. [Videogrametria e sequências temporais](#12-videogrametria-e-sequências-temporais)
13. [Reconstrução densa e produtos 3D](#13-reconstrução-densa-e-produtos-3d)
14. [Fusão multissensor e validação cruzada](#14-fusão-multissensor-e-validação-cruzada)
15. [Precisão, incerteza e critérios de aceitação](#15-precisão-incerteza-e-critérios-de-aceitação)
16. [Eficiência de RAM, CPU, energia e armazenamento](#16-eficiência-de-ram-cpu-energia-e-armazenamento)
17. [Execução distribuída e tolerância a falhas](#17-execução-distribuída-e-tolerância-a-falhas)
18. [Linguagens e componentes reutilizáveis](#18-linguagens-e-componentes-reutilizáveis)
19. [Interfaces, integração e formatos](#19-interfaces-integração-e-formatos)
20. [Segurança, integridade e reprodutibilidade](#20-segurança-integridade-e-reprodutibilidade)
21. [Plano de testes e benchmarks](#21-plano-de-testes-e-benchmarks)
22. [Plano de desenvolvimento por fases](#22-plano-de-desenvolvimento-por-fases)
23. [Riscos e perguntas de investigação](#23-riscos-e-perguntas-de-investigação)
24. [Exemplos técnicos](#24-exemplos-técnicos)
25. [Glossário](#25-glossário)
26. [Referências técnicas iniciais](#26-referências-técnicas-iniciais)
27. [Decisões de arquitectura: fixadas e por fixar](#27-decisões-de-arquitectura-fixadas-e-por-fixar)
28. [Conclusão](#28-conclusão)
29. [Registo de revisões](#29-registo-de-revisões)

---

## 1. Resumo executivo

Khnumn é uma proposta de sistema autónomo, modular e distribuído para transformar conjuntos heterogéneos de imagens e vídeos numa representação espacial coerente, mensurável e rastreável. As fontes previstas incluem imagens de satélite, levantamentos feitos por drones, câmaras fotográficas, telemóveis e, numa fase posterior, sensores auxiliares como LiDAR, GNSS/IMU, dados multiespectrais, térmicos e radar.

O sistema deverá poder funcionar num computador modesto, com CPU e RAM como base e GPU como aceleração opcional, e escalar para estações de trabalho e servidores. A execução distribuída não significa que qualquer conjunto de dados possa ser processado rapidamente num equipamento limitado: significa que a arquitetura controla os recursos, divide o trabalho e permite continuar em máquinas mais capazes sem mudar o modelo de dados ou a lógica científica.

A proposta não consiste em substituir indiscriminadamente bibliotecas maduras. O valor próprio deverá estar na normalização de observações heterogéneas, no encaminhamento automático para métodos adequados, na gestão explícita de incerteza, na fusão de resultados com proveniência e na validação independente. Os algoritmos de reconstrução existentes devem ser usados quando forem adequados, comparados em benchmarks e substituídos apenas quando existir uma vantagem demonstrada.

### 1.1 Resultado esperado

A partir de dados compatíveis, Khnumn deverá conseguir produzir, conforme a geometria e a qualidade de entrada:

- nuvem de pontos esparsa e densa;
- malha triangular texturizada;
- modelo digital de superfície (DSM/MDS);
- modelo digital do terreno (DTM/MDT), quando seja possível separar terreno e objetos;
- ortomosaico ou ortoimagem;
- mapas de cobertura, densidade, qualidade e incerteza;
- relatórios de calibração, georreferenciação e validação;
- metadados de proveniência para rastrear cada produto até às fontes e operações que o produziram.

Nem todos os dados permitem todos os produtos. Por exemplo, uma imagem única sem informação adicional não permite, em geral, recuperar uma geometria 3D métrica única. O sistema deve declarar essa limitação em vez de inventar profundidade.

## 2. Objetivos, âmbito e exclusões

### 2.1 Objetivos principais

1. **Precisão geométrica:** minimizar erros sistemáticos e aleatórios e quantificar a incerteza restante.
2. **Eficiência:** limitar picos de RAM, utilização de CPU, tráfego e consumo energético, sem sacrificar silenciosamente a qualidade.
3. **Autonomia controlada:** detetar características do conjunto de dados, escolher um pipeline justificável e comunicar confiança e limitações.
4. **Correção humana:** permitir ao utilizador alterar a classe de cenário, os pressupostos e as escolhas de processamento.
5. **Integração:** disponibilizar uma API estável, formatos abertos e componentes substituíveis.
6. **Distribuição:** dividir tarefas em unidades reexecutáveis, verificáveis e tolerantes a falhas.
7. **Reprodutibilidade:** registar versões, parâmetros, dados de entrada, sementes aleatórias quando aplicável e resultados de validação.

### 2.2 Cenários pretendidos

- terreno natural, campos agrícolas, florestas e zonas costeiras;
- edifícios, fachadas, monumentos e áreas urbanas;
- infraestruturas lineares, como estradas, caminhos e condutas visíveis;
- objetos de escala pequena, desde que a resolução e a geometria de captura sejam suficientes;
- cenas interiores;
- levantamentos aéreos nadirais e oblíquos;
- sequências de vídeo de câmaras em movimento;
- dados de satélite com modelos geométricos e metadados adequados;
- conjuntos mistos, desde que haja ligações geométricas ou referências externas que permitam alinhá-los.

### 2.3 Exclusões e limites

Khnumn não deve prometer reconstrução 3D precisa a partir de qualquer conjunto de imagens. Uma superfície sem textura, reflexiva, transparente, repetitiva ou em movimento pode impedir correspondências fiáveis. Imagens com resoluções, bandas espectrais ou épocas muito diferentes podem não ser diretamente comparáveis. Dados SAR não são fotografias óticas e exigem modelos próprios. Dados térmicos não devem ser tratados como imagens RGB comuns sem reconhecer diferenças de resolução, ótica e física da medição.

A classificação automática de cenário é uma ajuda ao encaminhamento, não uma prova da validade geométrica. A aprovação de um modelo para uso legal, cadastral, engenharia ou segurança deve seguir os requisitos normativos aplicáveis ao domínio e à jurisdição; este documento não estabelece certificação.

## 3. Princípios de engenharia

### 3.1 Medir antes de otimizar

Cada melhoria deverá ser avaliada em três eixos: qualidade geométrica, custo de recursos e robustez. Uma alteração que reduza o tempo em 30% mas aumente o erro vertical para além do limite acordado não é uma otimização aceitável.

### 3.2 Incerteza como dado de primeira classe

As coordenadas e os produtos não devem ser apresentados apenas como valores exatos. Quando possível, devem incluir covariâncias, resíduos, confiança, densidade de observações e origem dos dados. A ausência de estimativa de incerteza deve ser indicada explicitamente.

### 3.3 Arquitetura CPU-first

O sistema base deverá funcionar sem GPU. A GPU pode acelerar etapas paralelizáveis, mas a existência de GPU não pode ser pressuposto do formato de dados nem da API. Os caminhos CPU e GPU devem ser testados quanto à consistência e à qualidade.

Esta exigência tem uma consequência concreta que é preciso não esconder: os motores de SfM e MVS mais correntes não implementam a reconstrução densa em CPU. A etapa densa do COLMAP exige CUDA ou ROCm, e não existe hoje, sob licença permissiva, um MVS em CPU com qualidade equivalente. Khnumn resolve esta tensão com três caminhos declarados, escolhidos pelo planeador a partir da capacidade real do host:

1. **Caminho CPU, núcleo permissivo.** A reconstrução esparsa e a triangulação de Delaunay sobre a nuvem esparsa produzem DSM e malha sem GPU e sem dependências com copyleft. A densidade é substancialmente menor do que a de uma nuvem densa, e o produto tem de reflectir essa origem de forma explícita.
2. **Caminho CPU, qualidade de densa.** Um motor de MVS executado como processo externo, instalado à parte e sinalizado, com licença copyleft. A qualidade é a da reconstrução densa completa; o custo é a dependência de um componente com licença própria e a necessidade de o instalar.
3. **Caminho GPU, qualidade máxima.** O motor de referência, que calcula os mapas de profundidade em acelerador. É o caminho por omissão sempre que a máquina tem hardware compatível.

O que o sistema promete não é reconstrução densa em qualquer máquina, mas a melhor reconstrução que a máquina suporta, com o caminho efectivamente usado registado na proveniência de cada produto e o seu custo declarado. A escolha é uma decisão de planeamento, não uma escolha implícita.

### 3.4 Modularidade com contratos

Cada módulo recebe dados tipados, parâmetros versionados e limites de recursos; devolve resultados, métricas e erros estruturados. Um módulo não deve modificar silenciosamente os dados de entrada nem descartar metadados sem registo.

### 3.5 Reutilizar, medir, só depois substituir

A implementação própria deve concentrar-se nas lacunas demonstradas: fusão heterogénea, encaminhamento, controlo de qualidade, gestão de incerteza e execução eficiente. SfM, MVS, álgebra geoespacial e otimização numérica têm décadas de investigação; reinventá-los sem uma vantagem demonstrável aumenta o risco e o prazo.

## 4. Vocabulário e produtos de saída

- **Fotogrametria:** inferência de medidas e geometria a partir de imagens, apoiada em modelos de projeção e controlo geométrico.
- **Videogrametria:** uso de sequências de vídeo como fonte de observações, normalmente selecionando fotogramas informativos e modelando o movimento da câmara.
- **SfM (Structure from Motion):** estima simultaneamente poses de câmaras e estrutura 3D a partir de correspondências entre imagens.
- **MVS (Multi-View Stereo):** estima geometria densa a partir de várias vistas já alinhadas.
- **Ajuste de feixes (bundle adjustment):** otimização conjunta de parâmetros de câmaras e pontos 3D para reduzir erros de reprojeção.
- **GCP:** ponto de controlo no terreno com coordenadas conhecidas, usado para ancorar ou verificar a solução.
- **Checkpoint:** ponto independente usado para avaliar a precisão; não deve ser confundido com ponto usado para ajustar o modelo.
- **GSD:** dimensão aproximada no terreno representada por um píxel, em condições especificadas.
- **CRS:** sistema de referência de coordenadas.
- **DSM/MDS:** modelo digital de superfície, que inclui edifícios e vegetação visíveis.
- **DTM/MDT:** modelo digital do terreno, idealmente representando o solo nu; exige classificação e pode não ser inferível em áreas ocultas.
- **Ortoimagem:** imagem corrigida geometricamente para uma projeção cartográfica e um modelo de superfície.
- **Proveniência:** registo da origem dos dados e de todas as transformações relevantes.

## 5. Tipos de dados e limites de compatibilidade

### 5.1 Imagem ótica comum

JPEG, PNG, TIFF e formatos RAW podem ser aceites através de adaptadores. Para metrologia, convém preservar o original e criar uma representação de trabalho sem sobrescrever a fonte. A conversão para 8 bits, a aplicação de nitidez, a redução de ruído ou o balanço de brancos podem alterar as características usadas na correspondência; qualquer transformação deve ser documentada.

A gestão da cor é um requisito de consistência e não um detalhe estético. Os perfis ICC incorporados devem ser lidos e aplicados, e não descartados, porque a mesma cena aparece com resposta diferente conforme o espaço de cor de saída. As correções de lente, em especial a vinheta e o sombreamento angular, são determinantes para a uniformidade radiométrica do mosaico, e podem ser estimadas empiricamente com painéis de reflectância conhecidos ou pelo método da linha empírica, quando existirem condições para o fazer. Em multiespectral, a calibração radiométrica até reflectância de superfície é anterior à fusão: dois produtos com a mesma resposta espectral nominal e calibrações diferentes não são comparáveis por simples aritmética. A consistência radiométrica entre datações é uma condição de validade do produto e não um detalhe de apresentação.

### 5.2 Vídeo

O vídeo é uma sequência temporal, não apenas uma coleção arbitrária de imagens. Devem ser preservados timestamps, taxa de fotogramas, informação sobre obturador quando disponível e eventuais perdas de fotogramas. Extrair todos os fotogramas pode aumentar muito o custo sem aumentar a informação geométrica; a seleção deve considerar deslocamento, nitidez, sobreposição e mudança de perspetiva.

### 5.3 Satélite

Os dados de satélite podem conter georreferenciação por grelha, RPC (Rational Polynomial Coefficients), parâmetros orbitais, modelo do sensor, ângulo de observação, correções atmosféricas e metadados de produto. A geometria de uma imagem de satélite não deve ser presumida equivalente à de uma câmara pinhole de drone. O adaptador deve identificar o modelo geométrico disponibilizado e encaminhar para um método compatível.

A resolução espacial varia por missão, banda e produto. A título de exemplo, os produtos Sentinel-2 têm bandas com diferentes resoluções; não se deve assumir que todas as bandas têm a mesma resolução nem inferir detalhe abaixo do limite de amostragem. A resolução do píxel não é, por si só, uma garantia de exatidão posicional.

É necessário distinguir o que uma imagem de satélite permite produzir. Uma imagem isolada, georreferenciada por grelha ou por RPC, permite ortorretificação sobre um modelo de elevação e, a partir daí, uma ortoimagem ou um mapa de reflectância. Não permite, por si só, recuperar geometria 3D métrica: a profundidade não é observável numa única vista, e o modelo de elevação usado na ortorretificação é uma entrada externa, não um produto derivado. A reconstrução tridimensional exige um par estéreo ou triestéreo, com geometria de aquisição e ângulo de convergência próprios, e o seu tratamento é substancialmente diferente do de um par aéreo convencional.

Os sensores *pushbroom* acrescentam uma condição que não existe na aquisição aérea convencional: a imagem é adquirida linha a linha ao longo do tempo, e a atitude do sensor varia durante esse percurso. O modelo geométrico é, por isso, dependente do tempo, e a interpolação de atitude ao longo da faixa tem de ser parte do modelo, e não um detalhe de implementação. Um modelo que ignore esta dependência é uma aproximação, e a aproximação tem de ser declarada como tal.

Os RPC são aproximações polinomiais do modelo geométrico exato do sensor e estão sujeitos a um viés sistemático, tipicamente de alguns metros na direção radial. Esse viés tem de ser estimado e corrigido, em regra com pontos de controlo, e o seu valor residual tem de constar do relatório. Um produto ortorretificado a partir de RPC sem correção de viés não pode ser declarado conforme a um padrão de exatidão de levantamento.

A co-registação entre aquisições distintas, a máscara de nuvens e de sombras e a consistência radiométrica entre datas são operações de pré-condicionamento com efeitos diretos sobre a exatidão final, e não passos de pós-processamento opcionais.

### 5.4 RGB, multiespectral, térmico e SAR

Estes dados devem partilhar um modelo de metadados comum, mas não um pressuposto de aparência equivalente. RGB e multiespectral podem ter bandas e centros de banda distintos; térmico depende da calibração radiométrica e ótica; SAR mede retrodispersão coerente e tem geometria e efeitos de layover/shadow próprios. A fusão só é válida quando há um modelo físico e geométrico adequado para cada sensor.

### 5.5 LiDAR e dados de profundidade

LiDAR, nuvens de pontos de scanner e sensores RGB-D podem servir de referência geométrica ou de fonte complementar. Devem ser registados o sistema de coordenadas, a calibração entre sensores, a densidade, o padrão de varrimento e a incerteza. A fusão não deve assumir que uma nuvem densa é necessariamente correta.

### 5.6 Tempo e sincronização

O tempo é uma dimensão da medição, não um metadado acessório, e é a origem mais frequente de erro silencioso em fusão multissensor.

A relação entre o tempo GNSS e o tempo UTC envolve um desvio de segundos intercalares, estável desde 2017 mas acumulativo no histórico. Qualquer registo que misture relógios de origem diferente tem de declarar a convenção usada e a fonte do desvio aplicado.

As câmaras de consumo não têm relógio de tempo real preciso. A data e hora dos ficheiros é definida pelo utilizador e pode divergir do tempo real em minutos ou horas, enquanto o carimbo temporal GNSS presente nos metadados tem resolução de um segundo e é mais fiável, mas nem sempre existe. Um sistema que trate o carimbo do ficheiro como tempo de captura estará errado em muitas campanhas, e o erro será invisível no erro de reprojeção.

O instante de captura de uma imagem tem de ser declarado por convenção: início da exposição, meio da exposição ou fim da exposição. Em sensores *rolling shutter*, a exposição não é simultânea em toda a imagem, e a escolha da convenção afecta a consistência entre o instante de captura e a pose estimada.

Em vídeo, a taxa de fotogramas nominal pode não reflectir o espaçamento real dos fotogramas, e podem existir fotogramas perdidos. Uma taxa constante no ficheiro não é evidência de amostragem temporal constante.

A magnitude do problema traduz-se diretamente em erro posicional: um desvio de relógio de um segundo numa plataforma que se desloca a dez metros por segundo produz um erro de dez metros, muito superior aos erros geométricos típicos de um levantamento. Por isso a reconciliação de relógios, os fusos intercalares e a resolução temporal dos carimbos têm de ser verificados antes de qualquer ajuste.

A sincronização dos próprios workers e dos registos de telemetria é um problema distinto, resolvido por NTP ou, quando o exige, por PTP. Não deve ser confundida com a sincronização dos sensores.

### 5.7 Marcas de controlo e a sua deteção

Um ponto de controlo só existe no terreno como um alvo desenhado, e é esse alvo que tem de ser identificado em cada imagem onde aparece. A forma como isso é feito determina um erro que **não aparece no erro de reprojeção**, porque o modelo é perfeitamente consistente com a marca errada. Por isso a marcação tem de ser especificada, e não improvisada.

**Desenho do alvo.** O alvo é **circular e simétrico**. A simetria é o que garante que o centro estimado não seja enviesado pela perspectiva, e a circularidade é o que permite recuperar escala e rotação por ajuste de elipse. Desenhos assimétricos, como cruzes simples, não são recomendados: em ensaio de campo a taxa de deteção de cruzes colapsou para 14% a 35 m de altura de voo e para zero a 40 e 45 m, porque o ângulo de vista as deforma, e objetos de forma aproximada em X, como folhas, foram confundidos com as cruzes. Alvos circulares ou de padrão codificado são os que a literatura sustenta.

**Tamanho especificado em píxeis, não em centímetros.** O alvo deve ocupar cerca de 20 a 30 píxeis de diagonal na imagem, e o valor é o que determina a precisão da deteção: o centro ponderado de um alvo circular atinge um erro quadrático médio entre 0,20 e 0,40 píxeis, e alvos codificados entre 0,2 e 0,3 píxeis. A GSD planeada e o tamanho do alvo têm portanto de ser verificados **antes do voo**, e não depois. O alvo não deve ser excessivamente grande: a inferência do centro passa a ser dominada pelo erro de excentricidade, que cresce com o tamanho aparente.

**Detecção como refinamento, e não como busca.** Como as poses das câmaras são conhecidas antes da fase de controlo, as coordenadas do alvo no terreno podem ser projectadas para cada imagem e fornecer a posição inicial. A deteção passa a ser um refinamento local em sub-píxel à volta dessa posição, o que é mais estável do que uma busca global e dispensa alvos codificados, porque cada alvo fica identificada pela sua posição no terreno e não pelo seu padrão.

**Filtro de consistência.** Uma deteção só é aceite se for consistente com a reprojeção do mesmo alvo observada noutra imagem. É este filtro que rejeita falsos positivos, e é ele que torna a deteção automática segura. Em conjunto, apenas os alvos em uso devem estar visíveis: a presença de alvos não utilizados leva o detector a marcar objetos que depois têm de ser descartados à mão.

**Revisão humana, não medição humana.** O operador confirma ou rejeita as deteções sobrepostas à imagem. A correção humana continua a existir, como em §2.1, mas já não exige que alguém meça coordenadas de píxel, que era a fonte de erro irrecuperável.

A precisão que se pode esperar deste procedimento é de décimas de píxel, e é por isso que a marcação deixa de ser um risco relevante: o erro de deteção de um alvo circular fica uma a duas ordens de grandeza abaixo da incerteza de levantamento de um receptor GNSS.

## 6. Arquitetura lógica

A arquitetura proposta separa o controlo do fluxo de dados dos motores de reconstrução.

```text
[Fontes e conectores]
        |
        v
[Ingestão + inventário + hashes]
        |
        v
[Normalização de metadados e CRS]
        |
        v
[Diagnóstico de qualidade e cenário]
        |
        v
[Planeador de pipeline e orçamento de recursos]
        |
        +-----------------------------+
        |                             |
        v                             v
[Calibração / georreferência]   [Extração de características]
        |                             |
        +-------------+---------------+
                      v
        [Correspondências e grafo de vistas]
                      |
                      v
        [SfM / poses / ajuste global]
                      |
                      v
        [MVS / profundidade / nuvem densa]
                      |
                      v
        [Fusão geométrica e classificação]
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
      [DSM/DTM]   [Malha 3D] [Ortoimagem]
          |           |           |
          +-----------+-----------+
                      v
       [Validação independente + incerteza]
                      |
                      v
      [Exportação + relatório + proveniência]
```

### 6.1 Módulos

1. **Conectores:** leem ficheiros locais, diretórios, catálogos de dados e APIs autorizadas. Não devem conter lógica de reconstrução.
2. **Inventário:** cria identificadores estáveis, hashes, tamanho, formato, timestamps e ligações a metadados.
3. **Normalizador:** harmoniza unidades, datas, CRS e convenções de eixos, mantendo os valores originais.
4. **Quality Gate:** calcula nitidez, exposição, saturação, duplicação, metadados ausentes, estimativa de sobreposição e sinais de movimento.
5. **Scenario Classifier:** estima classes candidatas e respetiva confiança; permite correção manual e guarda a decisão final.
6. **Planner:** escolhe operações com base nos dados, objetivos, recursos disponíveis e limites de qualidade.
7. **Motores geométricos:** executam calibração, correspondências, SfM, MVS, alinhamento e fusão.
8. **Validator:** separa validação interna da validação com checkpoints independentes.
9. **Exporter:** escreve produtos e relatórios em formatos documentados.
10. **Scheduler:** distribui tarefas, gere memória, checkpoints, repetição e cancelamento.

### 6.2 Fluxo de trabalho como DAG

O projeto deve ser representado como um grafo acíclico dirigido (DAG) de tarefas. Cada tarefa tem entradas imutáveis, parâmetros explícitos, versão do algoritmo, limites de recursos e saídas identificadas por hash. Se uma entrada ou parâmetro não mudar, uma tarefa pode ser reutilizada a partir da cache, desde que a versão e o ambiente sejam compatíveis.

Uma tarefa que falhe deve produzir um estado e um motivo legíveis. Não se deve converter automaticamente uma falha geométrica em sucesso parcial sem marcar os produtos afetados.

O DAG é a estrutura de controlo desde o início, e não um refinamento tardio. A Fase 1 implementa-o em memória, com cache baseada no hash das entradas, dos parâmetros e das versões; a Fase 7 acrescenta apenas a distribuição entre máquinas, sem alterar o modelo de dados nem a forma das tarefas. Adiar a execução distribuída para o fim não obriga a adiar o DAG: o que não pode ser adiado é a noção de tarefa versionada e reexecutável, porque dela dependem a cache, a reprodutibilidade e a testabilidade de cada etapa, e todas são necessárias muito antes da distribuição.

## 7. Modelo de dados e proveniência

Cada observação deve poder ser representada sem exigir que todos os sensores preencham os mesmos campos.

### 7.1 Entidades essenciais

- `Project`: CRS-alvo, objetivo, limites de qualidade, recursos e política de retenção.
- `Asset`: ficheiro ou objeto original, hash, tamanho, formato, URI, data de ingestão.
- `SensorModel`: intrínsecos, modelo de projeção, bandas, calibração e versão.
- `Capture`: timestamp, pose conhecida ou estimada, GNSS/IMU, parâmetros de exposição e origem.
- `Observation`: píxel, raio, ponto 3D ou medição com covariância e ligação à fonte.
- `ControlPoint`: papel de controlo ou checkpoint, com coordenadas, covariância 3×3 obrigatória, método de medição, instrumento, data e operador. Um ponto sem covariância é um erro de configuração, não uma omissão tolerada.
- `ProcessingTask`: algoritmo, versão, parâmetros, dependências e estado.
- `Product`: ficheiro derivado, sistema de coordenadas, resolução, incerteza e proveniência.
- `QualityReport`: métricas, amostras de validação, alertas e critérios de aceitação.

### 7.2 Exemplo conceptual de registo JSON

```json
{
  "asset_id": "asset-000042",
  "source_uri": "dataset/flight_01/frame_0042.jpg",
  "sha256": "<hash-calculado-na-ingestao>",
  "media_type": "image/jpeg",
  "capture_time_utc": "2026-05-12T10:24:31.125Z",
  "sensor_id": "camera-01",
  "position": {
    "crs": "EPSG:4979",
    "coordinates": [ -1.2345, 43.2100, 112.4 ],
    "units": { "horizontal": "deg", "vertical": "m" },
    "uncertainty": {
      "horizontal_1sigma": { "value": 0.8, "unit": "m" },
      "vertical_1sigma": { "value": 1.5, "unit": "m" }
    },
    "source": "GNSS_EXIF"
  },
  "orientation": {
    "source": "unknown",
    "status": "not_verified"
  },
  "processing": {
    "original_preserved": true,
    "normalization_profile": "photo-v1"
  },
  "control_point": {
    "id": "cp-007",
    "role": "control",
    "crs": "EPSG:3763",
    "coordinates": [ -74218.412, -104731.955, 128.417 ],
    "units": { "horizontal": "m", "vertical": "m" },
    "covariance": {
      "units": "m2",
      "matrix": [ [ 0.0004, 0.0, 0.0 ], [ 0.0, 0.0004, 0.0 ], [ 0.0, 0.0, 0.0025 ] ]
    },
    "method": "RTK_network",
    "instrument": "GNSS-RECEIVER-MODEL-X",
    "measured_utc": "2026-05-10T08:41:55.000Z",
    "operator": "field-team-1"
  }
}
```

Os valores de coordenadas acima são ilustrativos e não representam um levantamento real. Um campo de incerteza simplificado não substitui uma covariância completa quando esta for necessária. A estrutura real deve ser versionada por esquema e validada.

A incerteza deve ser sempre acompanhada da sua unidade explícita e nunca ser herdada implicitamente do CRS das coordenadas: um sistema geográfico expressa a componente horizontal em graus e a vertical em metros, pelo que um valor isolado como `0.8` fica ambíguo. Para o cálculo numérico, a posição deve ser convertida para um referencial local ENU em metros, preservando a coordenada geodésica original e registando a transformação aplicada.

A covariância de um ponto de controlo é uma matriz 3×3 e não um escalar, porque a incerteza de um levantamento real é anisotrópica: o vertical de um receptor RTK é tipicamente pior do que o horizontal, e os eixos podem estar correlacionados. A incerteza é sempre declarada com a sua unidade explícita, e nunca herdada do CRS das coordenadas: um sistema geográfico expressa a componente horizontal em graus e a vertical em metros, pelo que um valor isolado como `0.8` fica ambíguo. Para o cálculo numérico, a posição é convertida para um referencial local ENU em metros, preservando a coordenada geodésica original e registando a transformação aplicada.

A matriz de covariância é obrigatória e o seu registo é validado contra a exatidão-alvo do projeto: uma covariância de ordem de grandeza incompatível com as tolerâncias declaradas é um erro de configuração, porque determina se o produto será limitado pelo controlo. O método, o instrumento e a data não são decorativos: são o que permite avaliar mais tarde se a incerteza declarada é a adequada para aquele aparelho naquele dia.

### 7.3 Regras de proveniência

- preservar os originais;
- registar transformações de píxeis que possam afetar a geometria;
- registar CRS e operações de transformação;
- guardar versões de software e parâmetros;
- distinguir dados medidos, estimados, interpolados e inferidos por modelo;
- não substituir silenciosamente dados em falta por valores fictícios;
- manter ligações entre produtos e dados de origem.

## 8. Ingestão, validação e normalização

### 8.1 Sequência mínima

1. Descobrir ficheiros e confirmar permissões de leitura.
2. Calcular hash criptográfico e inventariar formato, tamanho e data.
3. Ler EXIF/XMP e metadados do fornecedor sem os considerar automaticamente verdadeiros.
4. Verificar integridade, decodificação, dimensões e canais.
5. Identificar duplicados exatos e quase duplicados.
6. Estimar nitidez, exposição, saturação, ruído e conteúdo útil.
7. Normalizar datas, unidades, CRS e convenções, preservando os valores de origem.
8. Detectar as marcas de controlo nas imagens, refining a posição inicial projectada a partir das coordenadas do terreno, e filtrar as deteções por consistência multivista.
9. Submeter as deteções a revisão humana, registando as aceitações e as rejeições.
10. Gerar relatório de lacunas e advertências.

### 8.2 Metadados em falta

A ausência de posição GNSS não impede necessariamente a reconstrução relativa por SfM, mas pode impedir uma localização absoluta fiável sem GCPs ou outra fonte de georreferenciação. Uma altitude EXIF não deve ser usada sem verificar datum, tipo de altitude e origem. Altitude elipsoidal e altitude ortométrica não são equivalentes.

### 8.3 Qualidade de imagem

Uma métrica de nitidez, como a variância do Laplaciano, pode ser usada como indicador aproximado:

\[
Q_{sharp}=\operatorname{Var}(\nabla^2 I)
\]

É uma métrica sensível ao conteúdo, ruído e processamento; não deve, isoladamente, determinar se uma imagem é utilizável. A qualidade deve combinar vários sinais e, quando possível, comparar imagens do mesmo conjunto.

### 8.4 Verificação de acquisibilidade do controlo

Antes de processar, o sistema verifica se as marcas de controlo declaradas são utilizáveis nas imagens adquiridas, e não apenas se existem. A verificação é feita por imagem e cobre a dimensão aparente do alvo, o contraste com o fundo, a presença de obstrução ou sombra sobre o alvo e o número mínimo de imagens em que cada marca tem de aparecer.

Uma verificação que falhe não é um aviso: é uma condição que invalida o controlo previsto. A consequência tem de ser comunicada com a sua causa, e não convertida em silêncio numa degradação do resultado, porque um controlo parcialmente detectado degrada a georreferenciação de forma difícil de distinguir de um erro de ajuste.

## 9. Deteção do cenário e seleção de pipeline

A deteção automática deverá produzir uma distribuição de confiança, não apenas um rótulo inflexível. Exemplo de classes iniciais: `aerial_nadir`, `aerial_oblique`, `urban_facade`, `indoor`, `natural_terrain`, `vegetation`, `satellite_optical`, `multispectral`, `thermal`, `sar`, `mixed` e `unknown`.

### 9.1 Sinais utilizados

- metadados do sensor e do produto;
- altitude e ângulos de captura, quando fiáveis;
- resolução, relação de aspeto e características de imagem;
- padrões de movimento e sobreposição;
- distribuição de textura e repetição;
- presença de bandas ou características específicas de sensor;
- resultados preliminares de correspondência e geometria.

### 9.2 Política de decisão

O classificador sugere um cenário, confiança e razões observáveis. Se a confiança for baixa ou os testes geométricos falharem, o sistema deve escolher um pipeline conservador, pedir confirmação ou declarar que não há evidência suficiente. A correção manual tem prioridade e fica registada. O utilizador pode também impor limites de recursos ou exigir checkpoints.

Nenhuma decisão de encaminhamento pode assentar num indício que o sistema não saiba calibrar. Em particular, a confiança declarada por um método de reconstrução aprendida não é utilizável como critério, pelas razões de §11.6.

### 9.3 Evitar a falsa precisão

A seleção de um pipeline não deve ser otimizada apenas para produzir um modelo visualmente denso. Densidade, textura e aparência não garantem exatidão métrica. O planeador deve otimizar uma função multiobjetivo, por exemplo:

\[
J = \lambda_q E_q + \lambda_t T + \lambda_m M + \lambda_e E_{energy} + \lambda_r R_{risk}
\]

onde `E_q` representa uma penalização de qualidade estimada, `T` o tempo, `M` o pico de memória, `E_energy` a energia e `R_risk` o risco de falha. Os pesos dependem do projeto e devem ser configuráveis; a expressão é uma proposta de planeamento, não uma métrica validada universal.

O planeador tem ainda de escolher o caminho de reconstrução densa disponível, descrito em §13.1. Essa escolha não é livre: o caminho em CPU tem menor densidade e o caminho com acelerador exige hardware que pode não existir na máquina. Um plano que não explicita o caminho escolhido é incompleto, porque produtos com origens geométricas diferentes não são comparáveis entre si.

## 10. Calibração, geometria e georreferenciação

### 10.1 Modelo de câmara pinhole

Para uma câmara ótica convencional, uma aproximação comum é:

\[
\mathbf{x} \sim K [R\mid t] \mathbf{X}
\]

onde `X` é um ponto 3D em coordenadas do mundo, `R` e `t` descrevem a pose da câmara, `K` contém os parâmetros intrínsecos e `x` é a coordenada homogénea do ponto na imagem. A relação deve ser complementada por um modelo de distorção adequado à lente. O símbolo `~` indica igualdade até um fator de escala em coordenadas homogéneas.

Os intrínsecos típicos incluem focais em píxeis, ponto principal e parâmetros de distorção. A calibração deve considerar foco, zoom, estabilização digital/ótica e mudanças de modo. Uma calibração pode deixar de ser válida se a configuração física da câmara mudar.

A importação de uma calibração obtida por ferramenta externa exige atenção à convenção de coordenadas de píxel e à ordem dos parâmetros de distorção. Ferramentas como OpenCV e Kalibr usam coordenadas inteiras para o centro do píxel e centram o ponto principal em `((largura - 1) / 2, (altura - 1) / 2)`; o COLMAP coloca a origem no canto superior esquerdo, situa o centro do píxel em `(0.5, 0.5)` e centra o ponto principal em `(largura / 2, altura / 2)`. A conversão exige somar `0.5` às componentes `cx` e `cy`. Sem esta correção introduz-se um erro sistemático de meio píxel em todas as observações, que nem a auto-calibração nem um erro de reprojeção baixo denunciam. A ordem dos parâmetros de distorção também tem de coincidir entre o modelo de origem e o modelo de destino; o modelo `OPENCV` do COLMAP usa os mesmos `k1, k2, p1, p2` do OpenCV, enquanto `FULL_OPENCV` acrescenta `k3, k4, k5, k6`.

Em câmaras de consumo, os parâmetros de distorção podem variar com a distância de foco e não apenas com o zoom. Uma calibração única para toda a coleção pode, por isso, introduzir resíduos sistemáticos por grupo de imagens; a partição por configuração de captura deve ser avaliada antes de se aceitar um único modelo partilhado.

### 10.2 Rolling shutter e obturador

Em sensores rolling-shutter, linhas diferentes são expostas em instantes diferentes. Se a câmara se move rapidamente, um modelo de pose única por fotograma pode ser inadequado. A primeira versão pode sinalizar esse risco; modelos com tempo por linha só devem ser adicionados após existir um teste de referência e um caso de uso claro.

### 10.3 Georreferenciação

O sistema deve distinguir:

- coordenadas locais arbitrárias da reconstrução SfM;
- georreferenciação aproximada através de GNSS/EXIF;
- alinhamento com pontos de controlo;
- ajuste com GNSS/IMU e respetivas incertezas;
- validação com checkpoints independentes.

A distinção entre estes cinco regimes é uma distinção de propagação de erro, não de nomenclatura: cada um lida de forma diferente com a incerteza, e as afirmações de exatidão que o sistema pode fazer dependem do regime efectivamente usado. Todos eles pressupõem a reconciliação de relógios e de convenções de captura descrita em §5.6.

As transformações entre sistemas de coordenadas devem usar bibliotecas geodésicas e operações identificadas. Não se deve aplicar uma transformação genérica de datum sem verificar a área, a época e a disponibilidade de grelhas de transformação.

### 10.4 Modelo observacional do controlo

A forma como o controlo entra no sistema não é um detalhe de implementação: determina como os erros se propagam e que afirmações de exatidão são legítimas. Distinguem-se três métodos, com propriedades de erro distintas, e a escolha deve ser explícita na configuração do projeto e justificada no relatório.

1. **Transformação de similaridade aplicada depois da reconstrução.** A solução SfM é ajustada ao referencial geodésico por uma transformação de 7 parâmetros (rotação, translação e escala), estimada a partir da correspondência entre centros de câmara e posições GNSS conhecidas. É simples e robusto, e exige pelo menos três imagens não colineares. Mas é o mais fraco dos três para precisão absoluta: não propaga a incerteza para dentro da geometria, não corrige resíduos locais, e impõe uma escala global única mesmo quando a distribuição do GNSS é heterogénea.
2. **Priors de pose GNSS durante o ajuste.** A posição GNSS de cada imagem entra como observação no ajuste de feixes, com a sua covariância. Melhora a georreferenciação e propaga a incerteza para as poses, mas transfere diretamente para o modelo o erro e a correlação do receptor GNSS, e degrada-se quando a distribuição das observações é fraca ou enviesada. Um prior não é um ponto de controlo: a qualidade do prior é a qualidade do receptor e da sua configuração, e deve ser tratada como tal nos relatórios.
3. **Pontos de controlo como observações no ajuste.** Cada ponto de controlo, de coordenadas conhecidas com incerteza declarada, entra como ponto 3D fixo no ajuste, observável nas imagens onde a marca é identificável. A incerteza do ponto entra na ponderação das observações correspondentes. É o método que permite declarar propagação de incerteza de forma coerente em §15.3 e sustentar a camada de evidência de §14.4, e é também o que exige marcação, identificação e medição rigorosas.

Os motores de referência mais correntes não cobrem o método 3 de forma nativa: o COLMAP documenta explicitamente a georreferenciação por priors de pose e por alinhamento de centros de câmara, mas não oferece um fluxo de pontos de controlo de primeira classe. Khnumn implementa este fluxo sobre as ligações Python do COLMAP, sem bifurcar o motor, segundo a seguinte cadeia:

1. **Detecção das marcas.** As coordenadas de píxel de cada marca de controlo nas imagens onde é visível são obtidas por deteção automática, segundo o procedimento de §5.7, e registadas com a imagem e com o ponto de controlo a que pertencem. A revisão humana confirma ou rejeita as deteções; não substitui a medição.
2. **Triangulação local.** Cada ponto de controlo é triangulado no referencial local da reconstrução, a partir das suas observações, e entra no modelo como ponto tridimensional.
3. **Similaridade ponderada para o referencial mundial.** A transformação de 7 parâmetros entre o referencial local e o referencial geodésico é estimada a partir das correspondências entre os pontos de controlo triangulados e as suas coordenadas de levantamento. A estimativa é **ponderada** pelas covariâncias de cada ponto, com pesos inversos à variância, e o limiar do estimador robusto é escalado pela mesma incerteza. Dois pontos medidos com instrumentos diferentes têm pesos diferentes, e é isso que faz com que um ponto de maior precisão domine efectivamente o alinhamento. É esta transformação que ancora a escala e a posição, e é ela que substitui o GNSS quando os pontos de controlo existem.
4. **Fixação do gauge e das posições.** As posições tridimensionais dos pontos de controlo são substituídas pelas coordenadas de levantamento, e os pontos são declarados constantes na configuração do ajuste. O gauge é fixado explicitamente por três pontos, o que torna a solução métrica e georreferenciada e remove a ambiguidade descrita em §11.4.
5. **Ajuste constrangido.** O ajuste de feixes é executado com os pontos de controlo fixos. Os resíduos de reprojeção nas marcas de controlo passam a ser os resíduos de um ajuste constrangido, e não o erro de um modelo livre.
6. **Propagação da incerteza do controlo por ensemble.** A etapa final é executada N vezes, e em cada execução as coordenadas dos pontos de controle são perturbadas por um sorteio da sua covariância. A dispersão dos resultados é a incerteza do controlo propagada. Esta via é necessária porque a restrição do passo 4 é rígida: um ponto constante entra no ajuste com um resíduo de reprojeção subjecto à função robusta padrão, e a sua incerteza de levantamento não entra como prior ponderado. O ensemble não corrige a insensibilidade do modelo, mede o efeito dela, e propaga a incerteza **através** da não-linearidade da fixação do gauge, que é precisamente a peça que uma propagação linear não capta.

O ensemble tem duas consequências que o relatório tem de declarar. A primeira é que a incerteza do controlo é estimada por via numérica, e não de forma analítica, pelo que depende do número de execuções: um número insuficiente de amostras produz uma dispersão mal estimada, e o número de amostras é um parâmetro explícito, não um detalhe. A segunda é que a estimativa é a **contribuição do controlo** para a incerteza, e não a incerteza total; a combinação com a covariância interna da cena é que dá a incerteza total, e a comparação com pontos de verificação independentes continua a ser o árbitro final.

A via alternativa, prevista mas não adotada por omissão, é um ajuste de feixes próprio em que o ponto de controlo entra como prior ponderado pela sua covariância. É exata e analítica, mas obriga a reimplementar o ajuste, e o ensemble resolve o mesmo problema sem esse custo. A escolha fica registada em `processos/decisoes-motores.md` e é revista se uma medição comparativa mostrar que o ensemble é instável ou demasiado caro para projetos grandes.

Quando não existem pontos de controlo, aplicam-se os outros dois métodos: a similaridade, com os centros de câmara como correspondências, e os priors de pose GNSS, com a sua covariância. A escolha é sempre explícita na configuração do projeto e no relatório, e o método por omissão é o de priors de pose, por estar disponível sem trabalho adicional e por propagar incerteza para as poses. A transformação de similaridade é o último recurso, e um produto que só pode ser justificado por ela nunca pode ser declarado conforme, porque não existe propagação de incerteza para a geometria.

### 10.5 GSD e limite de detalhe

O GSD depende da dimensão do píxel, distância ao objeto, ótica e orientação. Para uma câmara nadiral simplificada:

\[
GSD \approx \frac{H\,p}{f}
\]

onde `H` é a distância da câmara ao plano observado, `p` é o tamanho físico do píxel e `f` é a distância focal física. A aproximação não cobre terreno com relevo, obliquidade nem todos os modelos de sensor. Um GSD pequeno não implica automaticamente um erro posicional igualmente pequeno.

## 11. Reconstrução SfM e ajuste de feixes

### 11.1 Deteção e descrição de características

O pipeline identifica pontos ou regiões distinguíveis e calcula descritores. Podem ser avaliados métodos tradicionais como SIFT/ORB e métodos aprendidos, tendo em conta desempenho, licença, estabilidade, dependências e custo. A escolha deve ser configurável e validada em cenas com textura fraca, vegetação, repetição e variação de iluminação.

### 11.2 Correspondências e rejeição de outliers

As correspondências candidatas devem passar testes de consistência, incluindo geometria epipolar quando aplicável e estimadores robustos como RANSAC. Um par com muitas correspondências não é necessariamente um par geometricamente útil; o sistema deve medir distribuição espacial, paralaxe e consistência.

### 11.3 Grafo de vistas

Cada imagem é um nó; ligações representam sobreposição e correspondências verificadas. O grafo deve evitar componentes desconexos e ligações falsas. Para coleções muito grandes, o planeador pode usar informação temporal, GPS aproximado, vocabulário visual ou índices para reduzir o número de pares candidatos.

### 11.4 Ajuste de feixes

Uma formulação clássica minimiza os resíduos de reprojeção:

\[
\min_{\{R_i,t_i\},\{X_j\}}\sum_{(i,j)\in\mathcal{O}}
\rho\left(\left\|\mathbf{u}_{ij}-\pi(K_i,R_i,t_i,X_j)\right\|^2_{\Sigma_{ij}^{-1}}\right)
\]

onde `O` é o conjunto de observações, `u_ij` é a posição medida do ponto `j` na imagem `i`, `π` é o modelo de projeção, `Σ` representa a covariância da medição e `ρ` é uma função robusta. A ponderação por incerteza permite não tratar todas as observações como igualmente fiáveis.

A reconstrução SfM tem ambiguidades de gauge: sem ancoragem, a solução pode ser determinada apenas até a uma transformação de similaridade (rotação, translação e escala) em cenários monoculares convencionais. GCPs, distâncias conhecidas, GNSS ou sensores adicionais podem fixar a escala e a referência, mas a qualidade depende das incertezas e da geometria.

O gauge tem de ser fixado de forma explícita na parametrização do ajuste, e não apenas descrito: enquanto a transformação de similaridade global permanecer livre, o sistema normal do problema é singular e a covariância estimada a partir da sua inversa não é fiável. Fixar o gauge é condição necessária para que §15.3 e a camada de evidência de §14.4 tenham significado.
O motor de referência disponibiliza dois mecanismos explícitos para o fazer, e ambos são usados por Khnumn: a fixação por duas poses de câmara conhecidas e a fixação por três pontos tridimensionais. A segunda é a via que o fluxo de pontos de controlo de §10.4 emprega, porque ancorar o gauge em pontos de levantamento é simultaneamente o que fixa a escala e o que georreferencia a solução.


A incerteza que o ajuste propaga obtém-se da inversa da informação de Fisher do problema linearizado, isto é, do produto jacobiano ponderado. Duas cautelas são necessárias. A primeira é que o sistema normal pode ser singular por duas razões que exigem diagnósticos diferentes: por liberdade de gauge, ou por deficiente observabilidade geométrica da cena. A segunda é que a relação entre o valor dos resíduos e a variância depende da convenção adotada para o ruído; a covariância só pode ser comparada com a exatidão externa depois de fixada essa convenção. Um intervalo de confiança derivado de uma covariância mal escalada não é uma afirmação sobre a exatidão do produto.

### 11.5 Diagnóstico

O relatório deve incluir erro de reprojeção, número de câmaras registadas, pontos triangulados, distribuição espacial dos pontos, componentes desconexos, observações rejeitadas, ângulos de interseção e indicadores de degenerescência. Um erro de reprojeção baixo não prova, por si só, que o modelo tenha escala ou georreferenciação corretas. Os indicadores de degenerescência devem distinguir explicitamente a liberdade de gauge, que é esperada e foi removida por construção, da deficiente observabilidade geométrica da cena, que é um aviso sobre a própria cena e não sobre a parametrização.

### 11.6 Reconstrução aprendida e os seus limites

Para além dos descritores aprendidos, que substituem apenas a deteção de pontos, existem desde 2024 modelos de reconstrução que substituem o SfM propriamente dito por uma passagem directa de inferência. O DUSt3R e o MASt3R estimam mapas de pontos por píxel a partir de pares de imagens; o VGGT e o Fast3R processam dezenas ou centenas de vistas numa única passagem. A atração é evidente: sem optimização por cena, sem inicialização e com um custo muito inferior ao de um SfM completo.

Esta classe de métodos tem, todavia, três limitações documentadas que são diretamente relevantes para os objetivos de Khnumn.

1. **Escala ambígua.** A saída é definida apenas até uma transformação de similaridade, pelo que não constitui geometria métrica. Cabeças de escala métrica recentes procuram resolver o problema, mas são específicas de cada modelo e não estão validadas de forma alargada. O que um método aprendido devolve é, no mínimo, a mesma ambiguidade de gauge que §11.4 descreve para o SfM.
2. **Confiança não calibrada.** Os canais de confiança por píxel são treinados em conjunto com a geometria e não correspondem ao erro geométrico. Depreciá-los para filtragem de pontos, fusão multivista ou decisão de confiança conduz a decisões erradas, especialmente sob mudança de distribuição.
3. **Alucinação de geometria.** Estes modelos devolvem estrutura tridimensional densa e suporte entre vistas para entradas que não correspondem a nenhuma cena coerente: misturas de cenas sem relação, imagens repetidas e ruído. A falha é anterior a qualquer agregação de resíduos, e por isso não é corrigida por métricas de consistência multivista que usem o próprio modelo como avaliador.

A estas três acresce a liberdade de referencial da saída: duas execuções corretas podem diferir por uma rotação fraccionária, o que desloca pontos distantes o suficiente para tornar a variância entre execuções enganadora.

A regra de uso que Khnumn deve adoptar é, por isso, restritiva: um método de reconstrução aprendida não pode ser a fonte primária de geometria métrica. Pode ser usado para gerar candidatos, para densificar correspondências, para propor inicializações e priors, sempre sob verificação geométrica clássica, sempre dentro do regime de incerteza de §15, e sempre com o resultado marcado como inferido e não medido. A §9.3 aplica-se com a máxima força: a aparência convincente de uma nuvem de pontos aprendida não é evidência de exatidão.

## 12. Videogrametria e sequências temporais

O sistema deve evitar tratar todos os fotogramas como observações independentes quando são quase idênticos. A extração de fotogramas deve considerar:

- intervalo temporal e deslocamento visual;
- nitidez e desfoque de movimento;
- mudança de perspetiva e paralaxe;
- sobreposição suficiente sem excesso de redundância;
- fotogramas perdidos, timestamps e taxa de fotogramas variável;
- mudanças de exposição e foco.

A seleção pode começar com uma amostragem temporal limitada, aumentando a densidade apenas onde a geometria ou a qualidade o justificarem. Uma política adaptativa deve ter limites explícitos de memória e tempo.

SLAM/VIO pode ser útil para estimar movimento ao longo da sequência, mas não é sinónimo de reconstrução fotogramétrica global. SLAM procura geralmente consistência incremental e localização; um pipeline SfM/MVS pode privilegiar um ajuste global e produtos de levantamento. A integração deve manter claras as diferenças entre trajetória em tempo real, reconstrução final e georreferenciação.

## 13. Reconstrução densa e produtos 3D

### 13.1 MVS e mapas de profundidade

Após estimar poses e calibração, a reconstrução densa calcula profundidade por vista e combina as estimativas. Os resultados devem ser filtrados com base em consistência entre vistas, ângulo de observação, textura, oclusão e incerteza. Superfícies brilhantes, transparentes ou sem textura podem produzir profundidade errada.

A etapa densa é a mais exigente em recursos de todo o sistema e a que mais varia entre máquinas: o número de vistas de origem por vista de referência, o raio da janela e o tamanho máximo de imagem determinam simultaneamente o custo e a qualidade. Estes parâmetros não podem ser reduzidos por omissão sob pressão de tempo ou de memória; qualquer redução tem de ser avaliada contra as métricas geométricas de §15.1 e registada.

Concretamente, o sistema dispõe de três caminhos para obter superfície, e a escolha entre eles é feita pelo planeador e registada:

| Caminho | Motor | Requisito | Densidade | Observação |
|---|---|---|---|---|
| Esparso | Triangulação de Delaunay sobre a nuvem esparsa | CPU | Baixa | Aplicável à nuvem esparsa; é o único caminho totalmente permissivo em CPU |
| Denso em CPU | Motor de MVS externo, com licença copyleft | CPU | Alta | Executado como processo separado; exige instalação e tem aviso de licença |
| Denso em acelerador | Motor de referência | CUDA ou ROCm | Alta e com consistência geométrica multivista | Caminho por omissão quando existe hardware compatível |

Os três produzem produtos que não são equivalentes e que não devem ser comparados como se o fossem. Um DSM derivado da nuvem esparsa e uma nuvem densa têm densidades, precisões aparentes e modos de falha diferentes, e um relatório que os apresente sem distinção é enganador. Todo o produto de superfície tem, por isso, de declarar o caminho de que veio, a densidade efectiva e a sua proveniência.

**Refinamento iterativo da via densa em CPU.** A via densa em CPU não é uma passagem única. Como o motor de MVS em CPU não tem a pressão de tempo que tem a via de acelerador, que reduz a resolução por omissão, ele pode ser conduzido por um ciclo de refinação em que cada passagem usa a nuvem anterior como informação de partida.

O que cada passagem faz: a nuvem da passagem anterior é usada para estreitar o intervalo de profundidade candidato, píxel a píxel, o que reduz o espaço de hipóteses sem reduzir a informação; para filtrar hipóteses que a passagem anterior já rejeitou; e para escolher as vistas de origem mais informativas. Este mecanismo de refinamento com priori da iteração anterior é o mesmo que está presente, dentro de uma única passagem, nos níveis de sub-resolução do motor de MVS em CPU e na pirâmide de níveis de resolução do motor de referência, e é ele que a literatura descreve como convergente em poucas iterações.

Como se decide que a nuvem já é suficiente: o critério de produção é a **autoconvergência**, e não uma comparação com outra execução. O ciclo termina quando o ganho de densidade entre iterações consecutivas deixa de exceder um limiar declarado e a taxa de outliers deixa de melhorar. Este critério não exige referência externa e é reprodutível.

A comparação com a referência de acelerador é o critério de **validação**, e é uma atividade distinta: faz-se no protocolo de benchmark, sobre a mesma cena, com a mesma resolução de entrada e com o motor de acelerador na melhor configuração, e a aceitação é por densidade, completude e distância ponto-superfície dentro de um limiar declarado. É esta comparação que permite afirmar que a via em CPU se aproxima da via em acelerador, e é por isso que a afirmação é medida e não presumida.

Guarda-se a melhor iteração, não a última. Cada iteração é pontuada com as métricas de §15.1 e o produto retido é o da iteração com melhor pontuação. A sequência é convergente mas não monotónica: a evidência publicada mostra que, a partir de um certo número de iterações, a melhoria deixa de se acumular e a iteração final pode ser ligeiramente pior do que a anterior.

A primeira passagem não é reduzida. O ganho mais barato e maior não está em iterar mais, está em não reduzir: a via de acelerador reduz a imagem por omissão para acelerar, e essa redução é uma escolha de desempenho, não uma limitação do algoritmo. A via em CPU começa em resolução plena.

O orçamento é declarado. O ciclo tem um número máximo de iterações, um limite de tempo e um limite de memória, todos explícitos. Se o orçamento for esgotado sem que a autoconvergência seja atingida, o produto é rotulado como abaixo do alvo, com o número de iterações efectivamente realizadas e o motivo de paragem. Não é aceite em silêncio.

Isto tem uma consequência para a prioridade dos caminhos. O refinamento iterativo só se aplica à via densa: repetir a reconstrução esparsa devolve a mesma nuvem esparsa, e não há nada a iterar. A prioridade fixada em ADR-005 inverte-se portanto quando o requisito é uma densidade comparável à da via de acelerador: nesse caso a via densa em CPU é o caminho primário, e a via esparsa passa a recurso de último caso, para quem não pode sequer instalar o motor externo. Quando o requisito é apenas um produto completo e rápido, a via esparsa continua a ser a escolha por omissão. A decisão é do planeador, segundo os requisitos do projeto e a capacidade do host.

O custo desta via é o fator multiplicador das iterações sobre o tempo de processamento, e é ele que tem de ser medido e comparado com a alternativa de usar um acelerador. A referência de ordem de grandeza é a medição de um conjunto de 11 imagens com 63 megapíxeis, processado num portátil sem acelerador em cerca de sete minutos: cinco iterações sobre um levantamento de duas centenas de imagens é um custo real, e não um detalhe de implementação.
### 13.2 Fusão de nuvens

As nuvens podem ser alinhadas e fundidas usando transformações rígidas ou, quando justificável, modelos mais flexíveis. Uma transformação não rígida pode esconder erros de calibração e deformar a geometria; não deve ser aplicada apenas para melhorar a aparência visual. Métodos como ICP dependem de inicialização, sobreposição e geometria suficiente.

### 13.3 DSM e DTM

O DSM representa a superfície observada, incluindo objetos elevados. O DTM pretende representar o terreno subjacente e exige classificação de pontos e tratamento de zonas ocultas. Em floresta densa, imagens óticas aéreas podem não observar o solo; qualquer DTM derivado deve indicar que zonas são medidas, interpoladas ou desconhecidas.

A filtragem de solo não é uma etapa da reconstrução SfM ou MVS: os motores de referência não a realizam. A produção de um DTM exige uma etapa autónoma de classificação de pontos, tipicamente com filtragem morfológica sobre a nuvem, que o Khnumn tem de compor e de documentar como tal. A mesma observação aplica-se à ortoimagem, em §13.5.

O mesmo se aplica à origem da superfície: um DSM obtido do caminho esparso de §13.1 tem de ser rotulado como tal, e o seu produto tem de indicar a densidade de que parte. Um DSM de maior resolução nominal, mas derivado de uma nuvem esparsa, não é melhor do que um derivado de uma nuvem densa: são geometrias de naturezas diferentes, e a comparação entre elas só é legítima com a mesma origem declarada. O mesmo se aplica às iterações: um produto de superfície declara o número de iterações que o originou e o motivo de paragem, porque duas iterações do mesmo ciclo não têm a mesma densidade nem a mesma completude.

### 13.4 Malhas e texturas

A triangulação e a texturização devem preservar unidades, orientação, escala e origem. O nível de detalhe deve poder ser reduzido para visualização sem destruir o produto de maior resolução. Os produtos derivados devem indicar se a simplificação alterou medidas geométricas.

### 13.5 Ortoimagem

A ortorretificação depende da geometria do sensor, do modelo de superfície e do CRS de destino. Em edifícios altos, uma ortoimagem simples baseada em terreno pode produzir deslocamentos e fachadas inclinadas; um produto verdadeiramente ortorretificado para cenário urbano pode exigir um DSM e modelação apropriada.

A produção da ortoimagem não está coberta pelos motores de SfM e MVS. É uma etapa de reprojeção de rasters, dependente de uma cadeia geoespacial própria, e o relatório de proveniência tem de registar o modelo de superfície, o CRS de destino e o método de reamostragem efectivamente usados. Nas costuras de mosaico, a descontinuidade admissível entre parcelas vizinhas é de duas vezes o `RMSE_H`, conforme §15.5, e a verificação dessa descontinuidade é parte da validação do produto e não um detalhe de montagem visual.

## 14. Fusão multissensor e validação cruzada

A inovação central proposta para Khnumn é uma camada de fusão que não mistura medições sem contexto. Cada medição deve manter tipo, sistema de coordenadas, época, resolução, modelo do sensor, covariância e proveniência.

### 14.1 Fusão em três níveis

1. **Fusão de metadados:** harmoniza relógios, CRS, unidades, calibração e referências. A harmonização de relógios não é uma conversão de formato: inclui a reconciliação de segundos intercalares, a conversão para tempo UTC, a resolução temporal dos carimbos e a declaração da convenção de instante de captura, conforme §5.6. Duas fontes cujas escalas temporais não estejam alinhadas não são fundíveis, por melhores que sejam os seus modelos geométricos.
2. **Fusão geométrica:** alinha poses, pontos, superfícies ou nuvens com modelos adequados e restrições explícitas.
3. **Fusão de produtos:** combina DSMs, ortoimagens ou classificações apenas quando as escalas, épocas e semânticas são compatíveis.

### 14.2 Compatibilidade temporal

Uma imagem de satélite de uma data e um levantamento por drone de outra data podem representar objetos que mudaram. O sistema deve calcular ou receber uma janela temporal de compatibilidade e marcar mudanças prováveis. Não deve fundir automaticamente edifícios demolidos, vegetação sazonal ou obras em curso numa única superfície supostamente contemporânea.

### 14.3 Validação cruzada

A concordância entre sensores é evidência útil, mas não equivale a verdade absoluta: os sensores podem partilhar erros de datum, calibração ou processamento. Sempre que possível, a validação final deve usar checkpoints independentes, medidos com método e precisão adequados.

### 14.4 Método próprio a investigar

Proposta: manter uma representação de evidência por célula/elemento espacial, incluindo estimativa geométrica, covariância, número e diversidade de observações, proveniência, época e indicadores de consistência. A decisão de aceitar, rejeitar ou manter múltiplas hipóteses deve usar regras explícitas e ser testada contra conjuntos de referência. Esta camada não deve ser apresentada como inovação comprovada até haver benchmarks comparativos.

## 15. Precisão, incerteza e critérios de aceitação

### 15.1 Métricas mínimas

- erro de reprojeção em píxeis;
- RMSE e viés em checkpoints horizontais e verticais;
- erro médio e a sua relação com o RMSE-alvo, para deteção de viés;
- percentis de erro, não apenas média;
- completude e densidade da nuvem;
- distância ponto-superfície ou métricas de nuvem contra referência;
- consistência entre vistas;
- cobertura espacial e zonas sem observações;
- taxa de falha e proporção de dados rejeitados;
- tempo, pico de RAM, CPU, armazenamento temporário e energia, quando mensurável.

Para coordenadas observadas `x_i` e referência `x_i*`, o RMSE escalar é:

\[
RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(x_i-x_i^*)^2}
\]

Para erros 3D, é necessário definir se a métrica é por eixo, distância euclidiana 3D, ou outra estatística. Os resultados devem indicar a unidade, o sistema de coordenadas, o número de pontos e como foram escolhidos.

### 15.2 Separar ajuste e avaliação

Os GCPs usados para ajustar o modelo não devem ser reutilizados como se fossem validação independente. Reservar checkpoints que não participem no ajuste é essencial para avaliar a exatidão externa. Se não existirem checkpoints, o relatório deve declarar que a precisão absoluta não foi validada independentemente, e o estado do produto tem de ser `NOT_VALIDATED` e não `PASS`.

O número de pontos de verificação não é arbitrário. Os critérios normativos de §15.5 fixam um mínimo de trinta para que a avaliação seja considerada plenamente conforme, e o número de pontos efectivamente disponíveis tem de constar do relatório ao lado da estatística calculada, porque um RMSE sobre cinco pontos não é a mesma afirmação do que um RMSE sobre trinta.

### 15.3 Incerteza combinada

Para uma combinação simplificada de erros independentes, uma aproximação comum é:

\[
\sigma_{total}\approx\sqrt{\sigma_1^2+\sigma_2^2+\cdots+\sigma_k^2}
\]

Esta expressão só é apropriada quando a independência e a natureza dos erros justificam a combinação quadrática. Erros correlacionados, vieses e transformações complexas exigem propagação de covariância adequada; não se deve usar a fórmula como garantia universal.

Há um caso particular que merece ser explicitado, porque é o regime por omissão de Khnumn. A incerteza de um produto com controlo decai em duas partes: a incerteza da cena, que vem da covariância interna do ajuste de feixes, e a incerteza do controlo, que vem do ensemble descrito em §10.4. A primeira é uma estimativa linear, válida enquanto a geometria for bem condicionada. A segunda é uma estimativa numérica, válida para o número de amostras usado, e é ela que capta a não-linearidade da fixação do gauge.

A incerteza total combina as duas, e a combinação só é legítima se as partes forem aproximadamente independentes, o que tem de ser verificado e não presumido: erros de datum, de calibração ou de processamento podem ser comuns aos dois termos e então a combinação quadrática é demasiado optimista. Esta é a razão pela qual a afirmação quantitativa sobre a exatidão do produto continua a ter de ser sustentada pela comparação com pontos de verificação independentes, pelas métricas de §15.1 e pelos critérios de §15.5, e não pela propagação interna. A propagação interna é o que permite **prever** a exatidão e **diagnosticar** se o produto está limitado pelo controlo; é o checkpoint que a **demonstra**.

### 15.4 Critérios de aceitação por projeto

Não deve existir um único limite de erro para todos os cenários. Antes do processamento, o projeto deve definir tolerâncias horizontais/verticais, escala, completude, resolução, CRS, data de referência e nível de confiança. Se o resultado falhar, o sistema deve emitir um estado como `PASS`, `PASS_WITH_WARNINGS`, `FAIL` ou `NOT_VALIDATED`, acompanhado das causas.

O erro de reprojeção é um diagnóstico interno do ajuste e não um critério de aceitação do produto. Um modelo pode ter um erro de reprojeção muito baixo e uma escala ou georreferenciação erradas, e um erro de reprojeção elevado pode ser preferível a um modelo estável mas mal parametrizado. O portão de aceitação é a exatidão medida contra pontos de verificação independentes.

### 15.5 Critérios normativos de referência

Os critérios de aceitação não devem ser improvisados caso a caso. Existem normas públicas que fixam as estatísticas, os limiares e, sobretudo, a separação entre controlo e verificação. As referências seguintes são as mais diretamente aplicáveis e devem ser citadas no relatório sempre que uma decisão de aceitação se apoie nelas.

**ASPRS Positional Accuracy Standards for Digital Geospatial Data, edição 2 (2023).** Expressa a exatidão posicional em três grandezas: `RMSE_H`, combinado a partir de `RMSE_X` e `RMSE_Y`; `RMSE_V`, vertical; e `RMSE_3D`, combinado das duas anteriores. Os pontos de verificação têm de ser independentes, e a sua própria exatidão de levantamento passa a ser incorporada na exatidão declarada do produto. A edição fixa ainda um conjunto de regras operacionais que o Khnumn deve implementar e reportar:

- para que a avaliação seja plenamente conforme, são necessários pelo menos trinta pontos de verificação, por um argumento de teorema central-limite;
- uma discrepância entre o produto e um ponto de verificação que exceda três vezes o RMSE-alvo em qualquer componente (X, Y ou Z) é um *blunder*, que tem de ser investigado, explicado e corrigido, e nunca descartado em silêncio;
- o erro médio deve ser inferior a 25% do RMSE-alvo; caso contrário, deve ser investigado e diagnosticado, e qualquer correção de viés deve de ser registada;
- em mosaicos de ortoimagem, a descontinuidade admissível nas costuras é de duas vezes o `RMSE_H`.

A edição 2 eliminou a referência ao nível de confiança de 95%, por ter gerado confusão entre grandezas derivadas da mesma distribuição de erros, e relaxou os fatores de segurança de exatidão exigidos aos pontos de controlo e de verificação.

**USGS OFR 2023-1033 (Guidelines for calibration of uncrewed aircraft systems imagery).** Reitera que o GSD não é a exatidão posicional, que a exatidão do produto não pode exceder a exatidão dos pontos de controlo, e que os pontos de controlo devem ter precisão de cerca de três vezes a exatidão exigida ao produto, recomendando trinta GCPs sempre que possível. Onde não existirem pontos de verificação suficientes, recomenda validação cruzada por subconjuntos aleatórios de GCPs, método que o Khnumn pode implementar como alternativa explícita, e não como substituto silencioso da verificação independente.

**ISO 17123-10 (procedimentos de campo para sistemas de medição por fotografia de UAV), em revisão em 2026, e ISO 19623 (processamento de dados de UAV).** A primeira define procedimentos de verificação de campo com marcadores no terreno utilizados simultaneamente como pontos de controlo e como pontos de verificação, que é exatamente o protocolo de controlo e verificação exigido por §15.2.

Estas normas não anulam os requisitos contratuais do projeto; traduzem-nos em limiares verificáveis. Quando o Khnumn aceitar um produto, o relatório deve indicar qual das referências foi aplicada e segundo que edição.

## 16. Eficiência de RAM, CPU, energia e armazenamento

### 16.1 Processamento por blocos

Imagens, rasters e nuvens grandes devem ser processados em blocos ou tiles, com limites de memória. Cada bloco precisa de uma margem de contexto quando os algoritmos dependem de vizinhança, para evitar artefactos nas fronteiras. A fusão de fronteiras deve ser determinística e testada.

### 16.2 Multirresolução

Usar pirâmides de imagem e níveis de detalhe permite executar deteção preliminar em resolução reduzida e reservar alta resolução para pares ou regiões relevantes. O sistema deve preservar a possibilidade de voltar à fonte original para a etapa final, evitando que a redução inicial elimine detalhe essencial.

### 16.3 Orçamento de recursos

Cada tarefa deve declarar memória estimada, memória máxima, número de threads, espaço temporário e possibilidade de GPU. O scheduler deve impor limites globais, aplicar backpressure e evitar que demasiadas tarefas de memória elevada corram simultaneamente.

Duas estruturas multiplicam o custo e por isso têm de ter orçamento próprio. A propagação da incerteza do controlo, por ensemble de §10.4, executa a etapa final N vezes; e o refinamento iterativo da via densa, de §13.1, repete a reconstrução densa um número variável de vezes. Em ambos os casos o número de execuções é um parâmetro declarado, não um valor implícito, e o custo total é estimado antes de começar, para que o planeador possa escolher um método de controlo e um caminho de superfície que caibam no orçamento. O que é verdade para o ensemble é que as etapas anteriores à final são partilhadas por todos os membros, e por isso não multiplicam o custo; o que é verdade para o refinamento é que a passagem seguinte é mais barata do que a primeira, porque parte de uma nuvem já existente.

### 16.4 Cache e armazenamento temporário

A cache deve usar hashes de entradas, parâmetros e versões de software. Os dados temporários devem ter política de retenção e limpeza segura, mas os produtos e relatórios necessários à auditoria não podem ser eliminados como se fossem cache descartável.

A cache é também o que torna barato o ensemble de propagação: como as entradas da etapa final diferem entre membros, mas todas as etapas anteriores são idênticas, a parte cara do processamento é partilhada e fica em cache, e a propagação custa apenas as execuções finais. O mesmo se aplica ao refinamento iterativo, em que a passagem seguinte só aproveita o que a anterior produziu.

### 16.5 Precisão numérica

Usar `float32` em todos os cálculos pode ser insuficiente para certas otimizações geométricas ou coordenadas grandes; usar `float64` em tudo pode aumentar custo. A escolha deve ser feita por etapa e validada numericamente. Uma estratégia possível é trabalhar em coordenadas locais centradas perto da área de interesse, mantendo transformações explícitas para o CRS global.

### 16.6 Medir energia

A energia não deve ser inferida apenas pelo tempo de CPU. Quando possível, recolher medições de energia suportadas pelo hardware ou pelo sistema operativo, documentando o método. Em hardware sem medição directa, reportar tempo e utilização como proxies, não como consumo energético exato.

As interfaces a tentar são, por ordem de preferência: contadores de energia do processador expostos pelo sistema operativo, através de `powercap` e `intel-rapl` em Linux; APIs de gestão e de contagem de energia da GPU; e a API de energia do sistema em Windows. Ferramentas de estimativa como o `powertop` devem ser identificadas como estimativas e não como medições. Qualquer valor publicado tem de ser acompanhado do método, do intervalo de amostragem, da duração da medição e do consumo de fundo da máquina em repouso, sob pena de não ser comparável entre execuções.

## 17. Execução distribuída e tolerância a falhas

### 17.1 Unidades de trabalho

Unidades candidatas incluem ingestão por ativo, extração de características, correspondências por pares, cálculo de profundidade por vista, processamento de tiles e exportação de produtos. Ajustes globais de poses e operações que exigem consistência global podem limitar o paralelismo; devem ser identificados explicitamente.

Duas unidades de trabalho específicas acrescem a esta lista: o **membro de ensemble**, que é uma execução da etapa final com uma perturbação específica das coordenadas de controlo, e a **iteração de refinação**, que é uma execução da reconstrução densa com um conjunto de parâmetros e um priori herdado da iteração anterior. Ambas são executáveis de forma independente e paralelizable, e ambas produzem resultados que têm de ser agregados por uma etapa posterior, responsável pela dispersão ou pela seleção.

### 17.2 Contrato de tarefa

Cada tarefa deve ter:

- identificador estável;
- entradas e hashes;
- versão do algoritmo e parâmetros;
- limites de recursos;
- estado e progresso;
- logs estruturados;
- saídas temporárias e finais;
- estratégia de retry;
- verificação de integridade após conclusão.

### 17.3 Idempotência e checkpoints

Executar a mesma tarefa com as mesmas entradas e parâmetros deve produzir resultados equivalentes dentro das tolerâncias definidas. Quando existam operações não determinísticas, devem registar-se sementes, versões e diferenças esperadas. Checkpoints permitem retomar um projeto sem repetir todas as etapas.

### 17.4 CPU e GPU heterogéneas

O scheduler deve anunciar capacidades dos workers, não presumir que todos têm a mesma arquitetura. A ausência de GPU não deve bloquear tarefas que disponham de implementação CPU. Um worker com GPU pode ser escolhido para uma etapa específica, desde que a conversão de dados e o custo de transferência não anulem o benefício.

### 17.5 Consistência de resultados

A distribuição pode alterar ordem de redução numérica e, portanto, produzir pequenas diferenças em otimizações. A política de reprodutibilidade deve definir se se exige identidade binária, equivalência numérica dentro de tolerância ou apenas equivalência de métricas. Para geometria científica, a tolerância deve ser explícita.

## 18. Linguagens e componentes reutilizáveis

### 18.1 Proposta de linguagens

- **Rust:** núcleo de orquestração eficiente, validação de esquemas, gestão de tarefas, integridade e componentes com requisitos de segurança de memória.
- **Python:** prototipagem científica, experimentação, avaliação, ferramentas de diagnóstico e integração inicial com bibliotecas de visão computacional, em particular através das ligações `pycolmap`.
- **C/C++:** interoperabilidade com motores de visão e geometria já existentes e kernels onde o ecossistema maduro o justifique, incluindo solvers de otimização não linear e grafos de fatores.
- **SQL/SQLite ou PostgreSQL/PostGIS:** catálogo de projetos e metadados; a escolha depende do modo local ou servidor.
- **JSON/JSON Schema ou formatos equivalentes:** contratos de dados versionados entre módulos.

A atribuição acima deve ser lida com realismo quanto ao ecossistema disponível. O Rust é adequado para esquema, DAG, catálogo, validação e integridade, mas o ecossistema geoespacial em Rust é imaturo: a implementação pura existente de transformações de CRS não suporta WKT nem transformações 3D ou ortométricas. A geodesia tem, por isso, de passar obrigatoriamente pela PROJ através de uma interface nativa, e não por uma reimplementação em Rust. O mesmo se aplica ao núcleo geométrico: as rotinas de SfM, MVS e ajuste de feixes disponíveis são C/C++ ou Python, e reimplementá-las em Rust contraria o princípio de reutilizar, medir e só depois substituir de §3.5.

Não é obrigatório implementar tudo em várias linguagens desde o primeiro dia. O MVP deve minimizar fronteiras de interoperabilidade até os contratos e os benchmarks estarem estáveis.

### 18.2 Bibliotecas e projetos a avaliar

A tabela abaixo foi verificada em 2026-10-20. A coluna da licença refere-se ao código do próprio componente; as dependências transitivas e as efectivamente compiladas têm licenças próprias e têm de ser auditadas por build, não por tabela.

| Componente | Uso possível | Licença | Observações de avaliação |
|---|---|---|---|
| COLMAP | SfM, MVS, malha e texturização | New BSD (permissiva) | Referência de base forte e em desenvolvimento activo. Desde a versão 4.0 (2026-03) integra o mapeador global (o repositório autónomo do GLOMAP foi descontinuado e migrado para aqui) e o mapeador hierárquico, para além do incremental; a texturização de malhas deixou de exigir o OpenMVS. Dispõe de `pycolmap` como superfície de integração principal, e é por essa via que Khnumn implementa a restrição de pontos de controlo de §10.4. A reconstrução densa é a sua limitação estrutural: exige CUDA ou ROCm, e não há via em CPU. A triangulação de Delaunay, pelo contrário, aplica-se tanto à nuvem densa como à esparsa, e é o que sustenta o caminho CPU permissivo de §13.1. A cópia oficial avisa que compilar com dependências de licença própria altera a licença do binário resultante. |
| pycolmap | Interfaces Python para SfM, MVS e acesso à base de dados | New BSD (segue o COLMAP) | Ponto de entrada preferencial para o protótipo em Python: mais estável que a CLI e com acesso programático à base de dados e aos modelos. |
| OpenMVG | SfM e ferramentas de visão geométrica | MPL-2.0 (copyleft fraco, por ficheiro) | Alternativa ou referência de comparação. Robustez e atividade inferiores às do COLMAP; útil para validar um segundo motor, não como baseline principal. |
| OpenMVS | Reconstrução densa, malhas e texturas | **AGPL-3.0 (copyleft forte)** | **Fora do núcleo, mas não dispensável.** A licença AGPL obriga à disponibilização do código-fonte correspondente quando o programa é modificado e executado como serviço de rede, o que colide com o objectivo de produto distribuível, e por isso não entra no caminho de código. É, no entanto, o motor do caminho denso em CPU de §13.1, porque tem uma via completa em CPU sem acelerador e sem a perda de completude que uma implementação de plane-sweep traz. Executa-se como processo separado, é instalado à parte e é sinalizado com aviso de licença. O COLMAP 4.x cobria MVS, malha e texturização sob BSD, o que dispensa o OpenMVS para o caminho de acelerador mas não para o caminho de CPU. |
| OpenDroneMap | Pipeline de fotogrametria de ponta a ponta para dados de drone | GPL-3.0 (copyleft forte) | Baseline externo de referência, executado como processo separado. Não é adequado como biblioteca interna de um produto cujo código não é aberto. |
| AliceVision / Meshroom | SfM, MVS, meshing e texturização; interface em grafo de nós | MPL-2.0 (com dependências entre as quais CGAL, GPL/LGPL) | Alternativa ao COLMAP para pipelines visuais e protótipos. Exige atenção às dependências transitivas. |
| hloc | Correspondência e recuperação de imagens com descritores aprendidos | Apache-2.0 (permissiva) | Complementa o COLMAP quando se usam descritores aprendidos e se pretende reduzir o número de pares candidatos. |
| OpenCV | Processamento de imagem, estimadores geométricos e I/O | Apache-2.0 desde a 4.5.0 (BSD-3 antes) | A migração para Apache 2.0 foi feita para incluir cláusulas de patentes. O SIFT passou para o repositório principal na 4.4.0, após a expiração da patente em 2020. Os módulos de `contrib` conservam licenças próprias e devem ser verificados à parte. |
| Ceres Solver | Otimização não linear e ajuste de feixes | New BSD (permissiva) | A partir da 2.3 substitui glog e gflags por Abseil, exige C++17, CMake ≥ 3.22 e Eigen ≥ 3.3.4. **Atenção:** `WITH_SUITESPARSE` passou a `OFF` por omissão porque os componentes CHOLMOD e SPQR da SuiteSparse são GPL; ligar essa opção torna GPL o binário resultante. A flag tem de ser verificada antes de qualquer distribuição. |
| GDAL | Leitura, escrita e processamento raster/vetor | MIT (permissiva) | Ecossistema amplo; verificar drivers e dependências da build. É também a via habitual para ortorretificação e ortomosaico, que os motores de SfM e MVS não produzem. |
| PROJ | Transformações de sistemas de coordenadas | MIT (permissiva) | Essencial para transformações geodésicas corretas. Não é dispensável no Rust: ver §18.1. |
| PDAL | Processamento de nuvens de pontos | BSD (permissiva) | Inclui componentes da SuiteSparse sob BSD. Útil ao integrar LiDAR e, em especial, na filtragem de solo para obter DTM, que os motores de SfM não realizam. |
| GTSAM | Estimativa de estado e grafos de fatores | BSD simplificada (com Eigen MPL2, METIS Apache-2.0, CCOLAMD BSD-3) | Considerar para fusão de poses, GNSS/IMU e otimização de grafos. |
| Open3D | Processamento 3D, registo e visualização | MIT (permissiva) | Útil para protótipos e avaliação de operações em nuvens e malhas. |
| Rasterio | API Python para rasters geoespaciais | BSD-3-Clause (permissiva) | Simplifica protótipos; depende do ecossistema GDAL. |
| CloudCompare | Inspeção e comparação de nuvens | GPL-3.0 (copyleft forte) | Excelente ferramenta externa de referência e QA, executada fora do produto. Não é núcleo. |
| ONNX Runtime | Execução de descritores e correspondentes aprendidos | MIT (permissiva) | Necessário para os descritores aprendidos suportados pelo COLMAP (ALIKED, LoMa, LightGlue). |

**Policy de licenças do núcleo.** A proposta é manter o núcleo distribuível livre de copyleft forte. Componentes AGPL ou GPL podem ser executados como processos externos opacos, comunicando por um protocolo documentado e sem ligação de código, mas não devem ser ligados ao núcleo nem aos seus adaptadores. Esta fronteira entre agregação simples e obra derivada depende dos fato e não apenas da forma da distribuição, e não é uma questão que este documento possa resolver; qualquer componente copyleft deve passar por revisão jurídica antes de ser adotado. A licença do próprio projeto é a Apache-2.0, em versão única, e está registada em ADR-010, em `processos/decisoes-motores.md`; as licenças dos componentes de terceiros são declaradas à parte, em `THIRD-PARTY.md`, e não se aplicam ao código do projeto.

A tabela é uma shortlist, não uma aprovação automática. O registo detalhado das escolhas, das alternativas avaliadas e das decisões correlatas está em `processos/decisoes-motores.md`. Antes de integrar, verificar repositório oficial, atividade, versões, plataforma, licença do código, licenças das dependências, requisitos de distribuição e compatibilidade com a versão concreta. As licenças de uma biblioteca e das dependências compiladas podem diferir. Como as licenças e as dependências mudam, esta tabela deve ser revida no momento de cada integração e não ser tratada como um registo permanente.

### 18.3 Estratégia de integração

Criar interfaces internas estreitas para motores externos: `run`, `inspect`, `cancel`, `collect_metrics` e `export`. Os adaptadores devem converter os formatos de entrada e saída sem espalhar detalhes específicos de uma biblioteca pelo resto do sistema. Guardar a versão do motor e os parâmetros exatos em cada tarefa.

A fronteira do adaptador é também a fronteira de licença. Um motor com copyleft forte deve ser invocado apenas por esta interface, como processo separado, e os seus resultados entram no sistema como dados com proveniência, nunca como código ligado ao núcleo. Esta separação deve ser verificável por inspeção das dependências do binário distribuído, e não apenas por convenção.

O adaptador do caminho denso em CPU é o caso de referência. A fronteira tem de incluir a troca de formatos, que no motor de MVS externo assenta no formato de cena e nos ficheiros de nuvem de pontos e de malha, e não em qualquer formato interno. O utilizador tem de instalar o componente à parte, e o sistema tem de o avisar da licença no primeiro uso, antes de o invocar, e registar no relatório que versão foi usada e com que parâmetros. Um produto que distribua esse binário tem de reabrir a questão da licença antes de o fazer.

## 19. Interfaces, integração e formatos

### 19.1 Interfaces

- **CLI:** interface principal para automação, servidores e depuração.
- **API local:** para aplicações de desktop e integração com outros sistemas.
- **API de serviço:** para submissão de projetos e consulta de tarefas em ambiente distribuído.
- **UI opcional:** inspeção do conjunto de dados, correção do cenário detetado, configuração de tolerâncias e visualização de relatórios.

A UI não deve ser necessária para executar o núcleo. Todos os parâmetros essenciais devem poder ser definidos por configuração versionada ou CLI.

### 19.2 Formatos sugeridos

- imagens originais nos formatos fornecidos, sem conversão destrutiva;
- GeoTIFF e Cloud Optimized GeoTIFF para rasters georreferenciados;
- LAS/LAZ para nuvens de pontos quando apropriado;
- GeoPackage para dados geoespaciais vetoriais;
- PLY ou formatos 3D comuns para intercâmbio de nuvens e malhas;
- glTF/GLB ou 3D Tiles para visualização e distribuição 3D, consoante o caso;
- JSON/JSONL para relatórios e metadados legíveis por máquina;
- STAC para catalogação de ativos geoespaciais quando adequado.

A escolha final deve privilegiar formatos interoperáveis e preservar CRS, unidades, timestamps, no-data, resolução e proveniência. O Cloud Optimized GeoTIFF é um padrão de organização de GeoTIFF com tiles e níveis de resolução que favorecem acesso parcial; não é, por si só, um algoritmo de reconstrução.

## 20. Segurança, integridade e reprodutibilidade

- validar nomes, caminhos e metadados externos antes de os usar;
- evitar execução de comandos montados a partir de nomes de ficheiro não confiáveis;
- limitar tamanho e profundidade de arquivos comprimidos para reduzir risco de decompression bombs;
- calcular hashes dos originais e produtos críticos;
- separar credenciais de conectores dos ficheiros de projeto;
- aplicar permissões mínimas a workers distribuídos;
- autenticar pedidos e proteger o transporte em instalações de servidor;
- evitar que os logs incluam tokens, credenciais ou dados privados desnecessários;
- documentar a retenção e eliminação de dados;
- manter SBOM e inventário de licenças para versões distribuídas.

Para reprodutibilidade, guardar configuração do projeto, versões, parâmetros, CRS, hashes, decisões manuais, relatórios e estado dos workers. Um relatório deve distinguir resultados reproduzíveis de resultados sujeitos a não determinismo numérico.

## 21. Plano de testes e benchmarks

### 21.1 Níveis de teste

1. **Unitários:** conversões de unidades, CRS, parsing de metadados, hashes, cálculo de métricas.
2. **Integração:** adaptadores, pipeline com conjunto pequeno, exportação e reimportação.
3. **Geométricos sintéticos:** câmaras e pontos com geometria conhecida, ruído controlado e casos degenerados.
4. **Conjuntos de referência:** dados com GCPs/checkpoints de qualidade documentada.
5. **Robustez:** metadados em falta, imagens corrompidas, timestamps duplicados, discos cheios, interrupções e workers indisponíveis.
6. **Desempenho:** RAM máxima, tempo, throughput, uso de CPU/GPU, espaço temporário e energia quando mensurável.
7. **Regressão:** comparar métricas e produtos após cada alteração.

### 21.2 Matriz de cenários

| Cenário | Principal dificuldade | Métricas importantes |
|---|---|---|
| Drone nadiral em campo | sobreposição, relevo, vegetação | checkpoints XY/Z, completude, GSD |
| Fachadas urbanas | oclusão, ângulos, superfícies repetitivas | erro 3D, cobertura, reprojeção |
| Floresta | oclusão do solo e movimento de folhas | cobertura, erro de classificação, limites do DTM |
| Interior | pouca textura, iluminação, loops | consistência de pose, erro de escala, cobertura |
| Vídeo em movimento | desfoque e rolling shutter | deriva, erro de trajetória, robustez |
| Satélite ótico | modelo do sensor, resolução e geometria | erro geográfico, compatibilidade RPC, checkpoints |
| Multissensor | escalas e datas diferentes | resíduos de alinhamento, consistência temporal |
| Dados mistos | CRS e qualidade heterogéneos | erro por fonte, rastreabilidade e falhas de fusão |

O critério de seleção de um conjunto não é a sua notoriedade mas a existência de referência independente com exatidão documentada. Uma shortlist inicial, a fixar no `processos/protocolo-benchmark.md`, cobre três necessidades distintas:

- **Cadeia completa com controlo de solo:** campos de ensaio com pontos de controlo e de verificação medidos por topografia, como os campos de ensaio da USGS ou de entidades nacionais de cartografia. São o único tipo de conjunto que valida a georreferenciação e a exatidão absoluta, e por isso têm de constar do primeiro alvo.
- **MVS com verdade-fundamento densa:** ETH3D, com varrimentos de laser como referência, e DTU, com point clouds de luz estruturada num cenário controlado e de escala conhecida. Servem para medir a qualidade da reconstrução densa e a da texturização, mas não para validar escala ou datum.
- **SfM em grande escala e sequências:** Tanks&Temples, para volume e velocidade, e LaMAR, com capturas de AR e verdade-fundamento de SfM, útil para a robustness da sequência e para o regime de vídeo de §12.
- **Classificação de solo e de volumes:** ISPRS Vaihingen e Potsdam, para a etapa de filtragem de solo e a produção de DTM em §13.3, e conjuntos de ortoimagem com verdade-fundamento para a validação radiométrica e de costura de §13.5.

A correspondência entre cenários e conjuntos é parte do protocolo, e cada conjunto usado tem de ser acompanhado do seu regime de licença e de citação.

### 21.3 Comparação justa

Os benchmarks devem usar os mesmos dados, os mesmos checkpoints, condições de hardware documentadas e parâmetros comparáveis. Reportar configurações CPU/GPU, versões, resolução de entrada e pré-processamento. Não comparar apenas capturas de ecrã ou densidade visual.

### 21.4 Critérios para aceitar uma melhoria

Uma melhoria só deve ser integrada como padrão se:

- passar os testes de correção;
- não degradar métricas geométricas para além das tolerâncias acordadas;
- mostrar benefício mensurável no objetivo declarado;
- ter comportamento de falha documentado;
- manter a proveniência e os metadados;
- ser reproduzível no ambiente de referência.

## 22. Plano de desenvolvimento por fases

### Fase 0 — Definição experimental

- fixar um conjunto de dados pequeno, público e legalmente utilizável;
- escolher checkpoints ou uma referência independente, e o seu número mínimo, por §15.5;
- definir métricas, tolerâncias e hardware de referência;
- avaliar licenças e dependências, e fixar a política de licenças do núcleo por §18.2;
- decidir o método de controlo de §10.4 para o primeiro alvo;
- documentar a linha de base manual.

**Saída:** o protocolo de benchmark e o registo de decisões de motores, mantidos em `processos/protocolo-benchmark.md` e `processos/decisoes-motores.md`, e as decisões iniciais. Não é um produto acabado.

### Fase 1 — MVP de ingestão e inventário

- CLI;
- ingestão de imagens estáticas;
- extração de EXIF/XMP;
- hashing e esquema de metadados;
- relatório de qualidade e campos ausentes;
- armazenamento local de projeto;
- DAG em memória, com cache por hash das entradas, dos parâmetros e das versões.

**Aceitação:** um conjunto de dados pode ser inventariado sem perda do original e com erros reportados claramente.

### Fase 2 — Primeiro pipeline SfM

- integração com um motor estabelecido;
- reconstrução esparsa;
- relatório de câmaras, pontos, reprojeção e falhas;
- exportação de poses e nuvem esparsa;
- testes com imagens conhecidas.

**Aceitação:** reconstrução reproduzível dentro das tolerâncias estabelecidas e limitações explicitadas.

### Fase 3 — Georreferenciação e validação

- CRS e transformações via biblioteca geodésica;
- ingestão de GCPs e checkpoints;
- métricas independentes XY/Z;
- relatório de incerteza e resíduos;
- distinção formal entre controlo e validação.

### Fase 4 — Reconstrução densa

- integração MVS;
- nuvem densa, malha e DSM;
- processamento por blocos e controlo de RAM;
- deteção de zonas com cobertura insuficiente.

### Fase 5 — Planeador e deteção de cenário

- classificador inicial baseado em regras e metadados;
- confiança e razões explicáveis;
- substituição manual;
- seleção de pipeline com fallback;
- registo de todas as decisões.

### Fase 6 — Vídeo e sensores auxiliares

- seleção adaptativa de fotogramas;
- timestamps e modelação de rolling shutter quando necessário;
- GNSS/IMU e sincronização temporal;
- fusão com nuvens externas e avaliação independente.

### Fase 7 — Distribuição

- persistência do DAG e recuperação após interrupção;
- scheduler CPU-first;
- workers locais e remotos;
- checkpoints, retry, cache e controlo de recursos;
- testes de falhas e consistência numérica.

Esta fase acrescenta a distribuição a um DAG e a uma cache que já existem desde as fases anteriores. O que é novo aqui é a escala e a tolerância a falhas, não o modelo de execução.

### Fase 8 — Fusão heterogénea avançada

- representação de evidência com incerteza e proveniência;
- alinhamento de fontes com modelos geométricos adequados;
- tratamento de incompatibilidade temporal;
- benchmarks contra baselines estabelecidos.

A sequência é deliberada: construir primeiro uma linha de base verificável, e só depois introduzir complexidade distribuída e fusão avançada. Caso contrário, será difícil saber se um resultado errado vem da geometria, dos metadados, do planeador ou da distribuição.

## 23. Riscos e perguntas de investigação

1. **Precisão incompatível entre fontes:** imagens com GSD, óticas e épocas distintas podem não suportar uma fusão métrica direta.
2. **Geometria degenerada:** vistas quase idênticas, pouca paralaxe, cenas planas ou padrões repetitivos podem produzir soluções mal condicionadas.
3. **Escala e datum errados:** posições EXIF podem usar referências ou altitudes diferentes das assumidas.
4. **Falsa confiança do classificador:** um cenário mal classificado pode escolher o pipeline errado; é obrigatório permitir override e fallback.
5. **RAM limitada:** MVS e ajuste global podem exceder a memória disponível; os limites devem ser testados em hardware modesto.
6. **Custo de I/O:** processamento por tiles pode trocar RAM por tráfego de disco; medir ambos.
7. **Deriva de versões:** atualizações de bibliotecas podem alterar resultados e licenças.
8. **Dependências e patentes:** licenças de código não resolvem automaticamente questões de patentes ou licenças de dados.
9. **Dados de referência insuficientes:** sem checkpoints independentes, não se pode declarar precisão absoluta comprovada.
10. **Integração temporal incorreta:** dados de épocas diferentes podem representar mudanças reais, não erro geométrico.
11. **Confusão entre densidade e precisão:** uma malha visualmente detalhada pode conter deformações.
12. **Promessas energéticas:** sem medição, qualquer afirmação de baixo consumo é apenas hipótese.

### Questões a responder experimentalmente

- Que motor de SfM oferece o melhor compromisso em CPU e RAM para o hardware mínimo definido?
- Qual é o ganho real de usar metadados GNSS para reduzir pares candidatos sem excluir ligações úteis?
- Como representar incerteza comum entre SfM, GNSS/IMU, RPC e LiDAR?
- Que métricas detetam melhor fusões erradas entre fontes com resoluções e épocas diferentes?
- Qual a estratégia de blocos que mantém continuidade geométrica entre tiles?
- Que classes de cenário são identificáveis com confiança apenas por metadados e imagens?
- Qual a tolerância numérica adequada entre execução local, CPU distribuída e GPU?

## 24. Exemplos técnicos

### 24.1 Exemplo de configuração de projeto

O seguinte YAML é ilustrativo; os nomes de campos devem ser formalizados num esquema versionado antes da implementação.

```yaml
project:
  id: levantamento-experimental-001
  target_crs: "EPSG:XXXX"   # substituir pelo CRS real validado
  scenario: auto
  allow_manual_override: true

control:
  method: gnss_pose_priors   # gnss_pose_priors | gcp_observations | similarity_transform
  gcp_file: null
  gcp_uncertainty_m: null
  prior_position_std_m: null   # incerteza GNSS assumida nos priors de pose
  covariance_required: true    # a covariancia 3x3 de cada GCP e obrigatoria
  propagation: ensemble        # ensemble | analytic_similarity | none
  ensemble_samples: 50         # numero de execucoes da etapa final
  ensemble_min_samples: 20

dense:
  path: auto                  # auto | sparse_delaunay | dense_cpu | dense_accelerator
  max_iterations: 5
  min_density_gain: 0.05      # limiar de autoconvergencia entre iteracoes
  max_outlier_rate: 0.10
  first_pass_full_resolution: true
  keep_best_iteration: true

quality:
  independent_checkpoints_required: true
  min_checkpoints: 30
  max_horizontal_rmse_m: null
  max_vertical_rmse_m: null
  max_mean_error_ratio: 0.25
  blunder_factor: 3.0
  acceptance_reference: "ASPRS Positional Accuracy Standards, ed. 2 (2023)"
  require_uncertainty_report: true
  diagnostics:
    max_reprojection_error_px: 1.5

resources:
  execution_mode: cpu_first
  max_workers: 2
  memory_budget_mb: 1800
  temporary_storage_policy: bounded
  gpu: optional

processing:
  preserve_originals: true
  image_pyramid: true
  sparse_reconstruction: true
  dense_reconstruction: true
  build_mesh: false
  build_orthoimage: false

reproducibility:
  record_software_versions: true
  record_parameters: true
  hash_inputs_and_outputs: true
```

Os valores de erro estão incompletos de propósito: as tolerâncias têm de ser definidas para a aplicação e o CRS. `EPSG:XXXX` é um marcador e não deve ser usado num projeto real. O orçamento de memória é uma configuração, não uma garantia de que todos os motores respeitarão exatamente esse limite; o scheduler precisa de monitorização e controlo de processos.

A estrutura de `quality` separa o que é portão de aceitação do que é apenas diagnóstico. Os limiares de RMSE, de erro médio e de *blunder*, bem como o número mínimo de pontos de verificação, seguem os critérios normativos de §15.5, e a referência aplicada fica registada no próprio ficheiro. O erro de reprojeção aparece sob `diagnostics` porque mede a qualidade interna do ajuste e não a exatidão do produto, e por §15.4 não deve servir de portão de aceitação. O bloco `control` materializa a escolha do método de controlo descrita em §10.4, e o valor por omissão é o de priors de pose GNSS, por estar disponível sem trabalho adicional e por propagar incerteza para as poses. A ausência de um ficheiro de GCPs, com `method: gcp_observations`, tem de ser tratada como erro de configuração e não como omissão silenciosa; e a escolha de `similarity_transform` obriga a que o estado do produto não possa ser `PASS`, por §10.4. O mesmo bloco declara a propagação: por omissão, a incerteza do controlo é obtida por ensemble, com um número de amostras explícito, porque um número insuficiente produz uma dispersão mal estimada. O bloco `dense` materializa o ciclo de refinação de §13.1: o número máximo de iterações, o limiar de autoconvergência, e a exigência de que a primeira passagem seja feita em resolução plena.

### 24.2 Exemplo de pseudocódigo do planeador

```text
function plan(project, assets, hardware):
    inventory = validate_and_inventory(assets)
    quality = estimate_quality(inventory)
    scenario = classify_scenario(inventory, quality)

    if project.manual_scenario exists:
        scenario.final = project.manual_scenario
        scenario.reason = "user_override"

    constraints = derive_constraints(project, hardware, quality)
    candidates = pipelines_compatible_with(scenario.final, inventory)

    for candidate in candidates:
        candidate.expected_cost = estimate_cost(candidate, constraints)
        candidate.risk = estimate_failure_risk(candidate, quality)
        candidate.validation_plan = select_validation(candidate, project)
        candidate.dense_path = choose_dense_path(candidate, hardware, project)
        candidate.control_budget = choose_control_budget(candidate, project)

    chosen = choose_feasible_candidate(candidates, constraints)

    if chosen is none:
        return status("NEEDS_USER_DECISION", explain_incompatibilities())

    return create_versioned_DAG(chosen, inventory, constraints)
```

O pseudocódigo define o comportamento esperado, não uma implementação executável. `estimate_cost`, `estimate_failure_risk` e `choose_feasible_candidate` exigem modelos e testes próprios. O sistema deve poder explicar porque escolheu um pipeline e quais alternativas rejeitou. `choose_dense_path` escolhe entre os três caminhos de §13.1 segundo a capacidade do host e o requisito de densidade do projeto; `choose_control_budget` fixa o número de amostras do ensemble de §10.4 e o número de iterações do refinamento, de modo que o custo total do plano é conhecido antes de a execução começar.

### 24.3 Exemplo de verificação de RMSE

```python
from math import sqrt
from statistics import mean


def error_metrics(observed, reference):
    """Calcula métricas por eixo para pares de coordenadas correspondentes.

    observed e reference são sequências de tuplos (x, y, z), na mesma unidade
    e no mesmo sistema de coordenadas. A correspondência dos pontos tem de ser
    estabelecida independentemente desta função.
    """
    if len(observed) != len(reference) or not observed:
        raise ValueError("As listas têm de ter o mesmo tamanho e não podem ser vazias")

    errors = [
        tuple(float(a[k]) - float(b[k]) for k in range(3))
        for a, b in zip(observed, reference)
    ]

    axis_rmse = tuple(
        sqrt(mean(error[k] ** 2 for error in errors))
        for k in range(3)
    )
    axis_bias = tuple(
        mean(error[k] for error in errors)
        for k in range(3)
    )
    euclidean_rmse = sqrt(
        mean(sum(component ** 2 for component in error) for error in errors)
    )

    return {
        "n": len(errors),
        "bias_xyz": axis_bias,
        "rmse_xyz": axis_rmse,
        "rmse_3d": euclidean_rmse,
    }
```

A função calcula estatísticas simples; não transforma CRS, não verifica datum, não calcula intervalos de confiança e não confirma que os pontos de referência são independentes. Essas condições têm de ser verificadas antes da chamada. Para levantamentos rigorosos, acrescentar análise de outliers, distribuição dos resíduos e incerteza da própria referência.

### 24.4 Exemplo de estados de tarefa

Estados sugeridos: `PENDING`, `READY`, `RUNNING`, `RETRY_WAIT`, `SUCCEEDED`, `SUCCEEDED_WITH_WARNINGS`, `FAILED`, `CANCELLED` e `BLOCKED`. Cada transição deve ter regras documentadas. Por exemplo, `SUCCEEDED_WITH_WARNINGS` exige produtos utilizáveis e advertências registadas; não deve ser usado para mascarar ausência de uma etapa obrigatória.

## 25. Glossário

| Termo | Definição resumida |
|---|---|
| Bundle adjustment | Otimização conjunta de poses de câmara e pontos 3D. |
| Checkpoint | Ponto de referência independente para avaliação. |
| Covariância de controlo | Matriz 3×3 que descreve a incerteza de um ponto de controlo, com correlação entre eixos. |
| CRS | Sistema de referência de coordenadas. |
| DSM/MDS | Modelo digital de superfície, incluindo objetos elevados. |
| DTM/MDT | Modelo do terreno, com limitações em zonas ocultas. |
| GCP | Ponto de controlo usado para ancorar a solução. |
| Ensemble | Execução repetida de uma etapa com entradas perturbadas, usada para propagar incerteza por via numérica. |
| Gauge | Liberdade de transformação global de uma reconstrução, fixa por construção. |
| GSD | Dimensão no terreno representada por um píxel, em condições definidas. |
| Marca de controlo | Alvo físico, de desenho simétrico, detectado automaticamente nas imagens e usado como ponto de controlo. |
| MVS | Reconstrução densa a partir de várias vistas. |
| Ortoimagem | Imagem corrigida geometricamente para uma projeção e superfície. |
| Proveniência | Histórico rastreável de origem e processamento. |
| Ponto constante | Ponto 3D cuja posição é fixada no ajuste, e não refinado. |
| Prior de pose | Observação da posição de uma câmara que restringe o ajuste sem a determinar. |
| RPC | Modelo polinomial racional usado em alguns produtos de imagem de satélite. |
| SfM | Estimativa de poses e estrutura 3D a partir de imagens. |
| Similaridade | Transformação de rotação, translação e escala, usada para ancorar uma reconstrução. |
| Alvo de controlo | Desenho simétrico usado em campo para materializar um ponto de controlo, especificado em píxeis e não em centímetros. |
| Tile | Bloco espacial usado para processamento ou armazenamento. |

## 26. Referências técnicas iniciais

As ligações abaixo são pontos de partida, verificados em 2026-10-20. A versão e a licença devem ser reverificadas no momento da integração e para a configuração concreta que será distribuída, porque tanto as versões como as licenças mudam.

### Motores e bibliotecas

1. **COLMAP — documentação, FAQ e registo de alterações:** https://colmap.github.io/ , https://colmap.github.io/faq.html , https://colmap.github.io/changelog.html . A FAQ é a referência mais útil para decisões de operação: a escolha entre mapeadores incremental, global e hierárquico, escolha de modelo de câmara, reconstrução com priors de pose, georreferenciação, convenção de coordenadas de píxel, e opções de RAM e aceleradores na reconstrução densa. O registo de alterações documenta a integração do GLOMAP como mapeador global e a introdução de ALIKED, LoMa e LightGlue, do backend de ajuste de feixes Caspar e do suporte ROCm/HIP.
2. **Ceres Solver — documentação, histórico de versões e licença:** https://ceres-solver.readthedocs.io/ e https://ceres-solver.readthedocs.io/latest/version_history.html . Verificar a opção de SuiteSparse, que passou a `OFF` por omissão e que torna o binário GPL quando activada, e a substituição de glog e gflags por Abseil a partir da 2.3.
3. **OpenCV — licença:** https://opencv.org/license/ . A licença é Apache 2.0 desde a 4.5.0 e BSD-3 antes disso; o SIFT passou para o repositório principal na 4.4.0, após a expiração da patente em 2020.
4. **OpenMVG:** https://github.com/openMVG/openMVG . Projecto de visão geométrica e SfM, sob MPL-2.0; verificar documentação e licença actuais.
5. **OpenMVS:** https://github.com/cdcseacave/openMVS . Projecto de reconstrução multi-view, sob **AGPL-3.0**; ver §18.2 quanto à implicação para o núcleo.
6. **OpenDroneMap:** https://www.opendronemap.org/ e https://github.com/OpenDroneMap/ODM . Referência de pipeline para fotogrametria orientada a dados de drone, sob GPL-3.0; verificar a licença e as dependências da versão concreta.
7. **AliceVision e Meshroom:** https://alicevision.readthedocs.io/ e https://alicevision.org/ . Framework de fotogrametria sob MPL-2.0; a documentação de licenças lista as dependências transitivas, entre as quais CGAL sob GPL/LGPL.
8. **hloc — Hierarchical Localization:** https://github.com/cvg/Hierarchical-Localization . Recuperacção e correspondência de imagens com descritores aprendidos, sob Apache-2.0.
9. **GDAL — documentação oficial:** https://gdal.org/en/stable/ . Biblioteca para leitura, tradução e processamento de formatos raster e vectoriais, sob MIT; a licença da biblioteca não substitui a análise das dependências da build escolhida.
10. **PROJ:** https://proj.org/ . Biblioteca para transformações cartográficas e geodésicas, sob MIT.
11. **PDAL:** https://pdal.io/ . Ferramentas para processamento de nuvens de pontos e dados LiDAR, sob BSD.
12. **Open3D:** https://open3d.org/ . Processamento e visualização 3D, sob MIT.
13. **GTSAM:** https://gtsam.org/ . Estimativa de estado e grafos de fatores, sob BSD simplificada, com dependências de terceiros de licenças distintas.
14. **Rete de documentação do COLMAP quanto a extractores e correspondentes aprendidos:** em https://colmap.github.io/faq.html . A escolha entre SIFT, ALIKED e LoMa, e entre força bruta e LightGlue, é explicada com critérios de cenário.

### Normas e critérios de aceitação

15. **ASPRS Positional Accuracy Standards for Digital Geospatial Data, edição 2 (fevereiro de 2023):** https://my.asprs.org/Common/Uploaded%20files/PERS/HLA/HLA%202023-10-2.pdf . Referência principal para §15.5: `RMSE_H`, `RMSE_V` e `RMSE_3D`, mínimo de trinta pontos de verificação, regra do *blunder* a três vezes o RMSE-alvo, erro médio inferior a 25% do RMSE-alvo e tolerância de costura de duas vezes o `RMSE_H`.
16. **USGS OFR 2023-1033 — Guidelines for calibration of uncrewed aircraft systems imagery:** https://pubs.usgs.gov/publication/ofr20231033/full . Distinção entre GSD e exatidão posicional, exigência de pontos de controlo com cerca de três vezes a exatidão do produto, e procedimento de validação cruzada por subconjuntos.
17. **ISO 17123-10, procedimentos de campo para sistemas de medição por fotografia de UAV:** https://www.iso.org/standard/83171.html . Em revisão em 2026, com procedimentos que usam marcadores no terreno tanto como pontos de controlo como de verificação.
18. **ISO 19623, processamento de dados de UAV, e ISO/IEC Guide 98-3 (GUM), expressão da incerteza de medição.** Referências a obter junto da ISO; a segunda é a base formal do orçamento de incerteza referido em §15.3.
19. **OGC GeoPose 1.0.** Formato normalizado de troca de pose, relevante para o intercâmbio de poses entre fontes heterogéneas em §14.

### Formatos e padrões de catalogação

20. **OGC Cloud Optimized GeoTIFF, versão 1.0 (documento 21-026, publicado em 2023-07-14):** https://docs.ogc.org/is/21-026/21-026.html e https://www.ogc.org/standards/ogc-cloud-optimized-geotiff/ . Especificação para organização de GeoTIFF que favorece acesso eficiente a partes e resoluções de um raster.
21. **STAC, Community Standard versão 1.1 (documento 25-004, publicado em 2025-10-14):** https://stacspec.org/ e https://docs.ogc.org/cs/25-004/25-004.html . Catalogação de activos geoespaciais, com a construção comum de bandas, campos de `nodata`, estatísticas e unidades.
22. **GeoPackage — OGC, versão 1.2:** https://www.ogc.org/standard/geopackage/ . Formato de intercâmbio geoespacial para dados vectoriais e rasters tiled.

### Dados e referências de investigação

23. **ESA Copernicus Data Space Ecosystem:** https://dataspace.copernicus.eu/ . Portal e serviços de acesso a dados Copernicus; confirmar condições de acesso, produto e metadados de cada coleção.
24. **Sentinel-2 — documentação da ESA:** https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-2 . Referência para características da missão e bandas; as resoluções e propriedades devem ser consultadas por produto e banda.
25. **DUSt3R, Geometric 3D Vision Made Easy (CVPR 2024):** https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_DUSt3R_Geometric_3D_Vision_Made_Easy_CVPR_2024_paper.pdf . Referência primária para a classe de reconstrução aprendida de §11.6, onde estão MASt3R (ECCV 2024) e VGGT (CVPR 2025).
26. **Estudo de robustez de métricas de consistência multivista:** https://arxiv.org/html/2605.18754 . Documenta a alucinação de geometria por parte de backbones de reconstrução aprendida, que é a limitação invocada em §11.6.
27. **Incerteza de perturbação com cognizência de gauge em reconstrução por passagem directa:** https://arxiv.org/html/2610.07883 . Explica a liberdade de referencial da saída e a sua consequência sobre a variância entre execuções.
28. **Global Structure-from-Motion Revisited (GLOMAP, ECCV 2024):** https://lpanaf.github.io/eccv24_glomap/ . Base do mapeador global integrado no COLMAP 4.0.

### Nota sobre fontes e licenças

A lista não é uma auditoria jurídica. Antes de incorporar uma dependência, verificar a licença do código, modelos treinados, dados de exemplo, plugins, bibliotecas transitivas e binários distribuídos. Verificar também termos de utilização dos dados de origem, atribuição, restrições de redistribuição e eventual necessidade de conservar avisos de copyright. Uma biblioteca com licença permissiva pode ser compilada com componentes sujeitos a condições diferentes.

---

## 27. Decisões de arquitectura: fixadas e por fixar

### 27.1 Decisões já fixadas

Estas decisões estão tomadas. O registo com contexto, alternativas avaliadas e consequências está em `processos/decisoes-motores.md`, e nenhuma delas é reaberta sem um novo registo de decisão.

1. **Motor de referência:** o COLMAP 4.x. Cobre SfM, MVS, malha e texturização sob licença permissiva, o que dispensa o OpenMVS do caminho principal e mantém o núcleo livre de copyleft forte. Registo em ADR-001.
2. **Política de licenças do núcleo:** o núcleo distribuível é livre de copyleft forte. Os componentes com licença copyleft são executados como processos externos, fora do caminho de código, e a verificação faz-se por inspeção das dependências do binário, e não por convenção. Registo em ADR-002 e ADR-003.
3. **Caminho da reconstrução densa:** três caminhos declarados, escolhidos pelo planeador segundo a capacidade real do host, e descritos em §13.1. O sistema promete a melhor reconstrução que a máquina suporta, e declara em cada produto qual o caminho usado e o seu custo. Registo em ADR-005.
4. **Método de controlo por omissão:** os priors de pose GNSS, por estarem disponíveis sem trabalho adicional e por propagarem incerteza para as poses. A transformação de similaridade é o último recurso e nunca origina um estado `PASS`. Registo em ADR-006.
5. **Implementação da restrição de pontos de controlo:** sobre as ligações Python do COLMAP, pela substituição das posições de levantamento e fixação das marcas como pontos constantes, com a fixação explícita do gauge por três pontos. Registo em ADR-006.
6. **Incerteza do controlo:** a covariância 3×3 de cada ponto de controlo é obrigatória, com método, instrumento, data e operador, e é validada contra a exatidão-alvo do projeto. A incerteza é propagada por **ensemble** sobre a etapa final, com número de amostras explícito; a via analítica, com um ajuste próprio em que o ponto entra como prior ponderado, fica prevista como escalada. Registo em ADR-007.
7. **Marcas de controlo:** alvo circular e simétrico, de tamanho especificado em píxeis e verificado contra a GSD planeada antes do voo, com deteção automática como refinamento local e revisão humana das deteções. Registo em ADR-008.
8. **Refinamento iterativo da via densa em CPU:** a via densa em CPU é conduzida por um ciclo com priori da iteração anterior, paragem por autoconvergência, orçamento declarado e retenção da melhor iteração. A comparação com a referência de acelerador é o critério de validação, e não de produção. Quando o requisito é densidade comparável à da via de acelerador, esta passa a ser o caminho primário em CPU. Registo em ADR-009.

### 27.2 Decisões por fixar

Estas decisões dependem do primeiro alvo de validação e são tomadas na Fase 0, com o protocolo de `processos/protocolo-benchmark.md` como instrumento.

1. **Primeiro alvo de validação:** recomendar um levantamento de drone RGB pequeno, com pontos de controlo e checkpoints independentes conhecidos. É um caso mais controlável do que começar por fundir simultaneamente satélite, vídeo, térmico e SAR.
2. **Definição de hardware mínimo:** especificar CPU, RAM, armazenamento e sistema operativo concretos. Sem isso, "baixo consumo" e "funciona em computadores modestos" não são critérios verificáveis, e o caminho de §13.1 escolhido em CPU depende deste valor.
3. **Tolerâncias por aplicação:** definir erro horizontal/vertical e completude desejados para cada classe de projeto, e qual das referências normativas de §15.5 se aplica a cada uma.
4. **Modelo de metadados versionado:** fixar CRS, unidades, convenções de eixos, timestamps, convenção de instante de captura e representação da incerteza.
5. **Protocolo de checkpoints:** definir como os pontos independentes são medidos, distribuídos e excluídos do ajuste, e qual o número mínimo aceitável, por referência a §15.5.
6. **Política de falhas:** decidir quando o pipeline pode continuar com advertências e quando deve parar para pedir intervenção humana.
7. **Critério para inovação própria:** só declarar vantagem depois de comparar a camada de fusão/validação com baselines em conjuntos de teste públicos e próprios.

## 28. Conclusão

Khnumn deve ser desenvolvido como uma plataforma de evidência geométrica rastreável, e não apenas como uma ferramenta que gera modelos visualmente convincentes. A prioridade técnica é construir uma cadeia verificável: dados originais preservados, metadados normalizados, geometria apropriada a cada sensor, estimativa de incerteza, processamento dentro de limites de recursos e validação independente.

A melhor estratégia é começar com um MVP estreito e mensurável, baseado em componentes maduros, e expandir progressivamente para vídeo, satélite, sensores auxiliares e execução distribuída. A fusão heterogénea poderá tornar-se o elemento diferenciador, mas terá de demonstrar que melhora a consistência, a precisão ou a robustez sem esconder incompatibilidades entre fontes.

## 29. Registo de revisões

A versão deste documento identifica o estado da proposta, e não o histórico de edição. Como ainda não existe implementação, as revisões não incrementam a versão: registam-se aqui, com data e alcance, para que a diferença entre o que foi validado e o que foi apenas escrito possa ser reconstruída.

| Data | Versão | Âmbito da revisão |
|---|---|---|
| 2026-10-20 | 0.1.0 | Revisão inicial do documento. Validação de conceito contra fontes primárias; correção das licenças dos motores e da tabela de §18.2, com a exclusão do copyleft forte do núcleo; identificação de que os motores de referência não fornecem fluxo de pontos de controlo de primeira classe e definição do modelo observacional do controlo em §10.4; introdução de critérios de aceitação normativos em §15.5; introdução das limitações da reconstrução aprendida em §11.6; introdução das seções de radiometria e de referência temporal; reconciliação do DAG fundacional com o faseado; atualização das referências com versão e data. |
| 2026-10-20 | 0.1.0 | Renomeação do projeto. O nome de trabalho passa de Mímir para **Khnumn**, nome do deus egípcio que moldava as primeiras formas numa roda de oleiro. A mudança foi motivada pelo conflito de uso com o Grafana Mimir e por o desajuste semântico do nome anterior, e foi precedida de verificação em cinco índices e na web, sobre 74 candidatos. O ficheiro de especificação passou a `docs/Khnumn.md`, o directório de trabalho foi renomeado, e foi criado um `NOTICE` com o aviso de copyright, mantendo o texto da licença intacto. Os registos de decisão anteriores a esta data mantêm o nome vigente na altura. Registo em ADR-011. |
| 2026-10-20 | 0.1.0 | Reorganização da documentação e politização de licenças. A especificação e o roadmap passam para `docs/`, por descreverem o sistema e a ordem de construção; o registo de decisões e o protocolo de benchmark passam para `processos/`, por serem registos vivos que crescem com o trabalho. As referências entre documentos passaram a usar o caminho relativo à raiz do repositório, com a convenção declarada em cada ficheiro. O projeto passa a ter uma licença única, a Apache-2.0, com o texto em `LICENSE` na raiz, e as licenças dos componentes de terceiros passam a ser declaradas em `THIRD-PARTY.md`, que separa o que está aprovado para integração do que está efetivamente integrado. Registo em ADR-010. A ortografia foi uniformizada pela forma do Acordo Ortográfico de 1990, que estava misturada entre formas antigas e actuais ao longo dos cinco documentos. |
| 2026-10-20 | 0.1.0 | Resolução dos três riscos residuais que restavam. Incerteza do controlo: a covariância 3×3 passa a ser obrigatória por ponto de controlo, com método, instrumento, data e operador, e a propagação passa a existir de fato, por ensemble sobre a etapa final, com a similaridade de 7 parâmetros ponderada pelas covariâncias; a §15.3 é reescrita porque a incerteza total passa a ter duas partes identificáveis. Marcas de controlo: nova §5.7 especifica o alvo circular e simétrico, o tamanho em píxeis verificado contra a GSD planeada antes do voo, a deteção automática como refinamento local com filtro de consistência e revisão humana; a §8.1 e a nova §8.4 passam a cobrir a deteção e a verificação de acquisibilidade. Refinamento iterativo: a via densa em CPU passa a ser um ciclo com priori da iteração anterior, paragem por autoconvergência, orçamento declarado e retenção da melhor iteração, o que inverte a prioridade dos caminhos quando o requisito é densidade comparável à da via de acelerador. O bloco `control` da configuração ganha a covariância obrigatória e o número de amostras, e nasce um bloco `dense` com o orçamento de iterações. |
| 2026-10-20 | 0.1.0 | Resolução das duas decisões que estavam em aberto. Caminho da reconstrução densa em CPU: três caminhos declarados em §13.1 e em §3.3, com o núcleo 100% permissivo, o motor de MVS externo como adaptador opcional e instalável à parte, e o caminho de acelerador; a escolha passa a ser do planeador, segundo a capacidade do host, e a constar da proveniência de cada produto. Restrição de pontos de controlo: cadeia concreta sobre as ligações Python do motor, com fixação explícita do gauge por três pontos, e a limitação de a incerteza de levantamento não entrar como prior ponderado passa a ser declarada em §10.4, §11.4 e §15.3. Método de controlo por omissão: priors de pose GNSS, com a transformação de similaridade reservada ao último recurso e nunca a originar um estado conforme. §27 reestruturada em decisões já fixadas e decisões por fixar, com os registos ADR-005 e ADR-006 correspondentes. |
