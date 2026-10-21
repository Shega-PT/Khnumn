# Khnumn — Declaração de componentes de terceiros

**Âmbito:** este ficheiro declara as licenças dos componentes de terceiros que o Khnumn utiliza, ou está aprovado para utilizar. **Não** é a licença do projeto: essa é a [Apache License 2.0](LICENSE), e é a única que se aplica ao código do Khnumn.

**Estado:** proposta para fixação na Fase 0. O projeto ainda não tem implementação, e por isso a seção de componentes integrados está vazia — ver §3.

**Versão do ficheiro:** 0.1.0 · **Data:** 2026-10-20 · **Idioma:** Português europeu

**Convenção de referências:** as menções a outros documentos deste repositório usam o caminho relativo à raiz do repositório.

---

## Índice

1. [Política](#1-política)
2. [Componentes aprovados para integração](#2-componentes-aprovados-para-integração)
3. [Componentes integrados nesta versão](#3-componentes-integrados-nesta-versão)
4. [Regra de manutenção](#4-regra-de-manutenção)

---

## 1. Política

O **núcleo distribuível do Khnumn** é livre de copyleft forte. Componentes sob licença AGPL ou GPL podem ser executados como processos externos opacos, comunicando por um protocolo documentado e sem ligação de código, mas **não** são ligados ao núcleo nem aos seus adaptadores. A verificação faz-se por inspeção das dependências do binário distribuído, e não por convenção.

A distinção entre o que é linkage e o que é agregação simples depende dos fato e não apenas da forma da distribuição, e não é uma questão que este repositório possa resolver por conta própria. Qualquer componente com licença copyleft passa por revisão jurídica antes de ser adotado.

Esta política está registada em ADR-001, ADR-002 e ADR-003, em [`processos/decisoes-motores.md`](processos/decisoes-motores.md), e a matriz completa de motores com as suas licenças está em [`docs/Khnumn.md` §18.2](docs/Khnumn.md).

**A licença do projeto é única e é a Apache-2.0.** As licenças dos componentes de terceiros não se aplicam ao projeto, e não são combinadas com a dele: cada componente é usado sob a sua própria licença, e a sua declaração aqui é o que permite a quem distribui o Khnumn saber com que obrigações conta.

## 2. Componentes aprovados para integração

A lista abaixo é a **shortlist aprovada**. Não é a lista do que está instalado: é a lista do que está autorizado a entrar, com a licença verificada e o papel definido. A distinção entre as duas é o que impede este ficheiro de mentir.

**Data de verificação de todas as linhas abaixo: 2026-10-21.** A regra de §4.4 exige reverificação anual, e uma licença com mais de um ano sem reverificar é tratada como desconhecida.

### 2.1 Componentes integrados no núcleo

| Componente | Versão | Papel | Licença | Tipo de integração | Hash do artefacto instalado |
|---|---|---|---|---|---|
| pycolmap | 4.2.1 | Motor de SfM, MVS e malha; superfície de integração principal | BSD-3-Clause | Núcleo, por adaptador | `4dfff8d1530cb9c299b61988b4d265c0d0bef63b6aac8a800cb17601ecbf60b3` |
| pyproj | 3.8.0 | Geodesia e CRS, sobre PROJ 9.8.1 embebido | MIT | Núcleo | `eca0388eb28354c2a185131134df407e2c17ec3018610651ecd5e17dfdb583c7` |
| numpy | 2.5.4 | Cálculo numérico | BSD-3-Clause AND MIT AND Zlib AND CC0-1.0 | Núcleo | `09295a80660f17925ae23765ce8cbd7ff7ceae968d5f2f89349f1cb74c0b9e11` |
| opencv-python-headless | 5.0.0.93 | Processamento de imagem e estimadores geométricos | Apache-2.0 | Núcleo, por adaptador | `69192904dead3ada37c8b305ee850ac7474924730881a9d5e0b2390944eb5aae` |
| pillow | 13.0.0 | Leitura de imagem e cabeçalhos | MIT-CMU | Núcleo | `7361b6ad3878589affe5956e4a4da24d71398b0891fd3a8c15e9362217b4ca01` |
| piexif | 1.1.3 | Leitura de EXIF, com GPS e IFDs de exposição | MIT | Núcleo | `55a4520f113c92ce9db48b792f570ba5dcc7ade14ae3b9e5639144540eaf8b5e` |
| defusedxml | 0.7.1 | Leitura de XMP sem expansão de entidades | PSF-2.0 | Núcleo | `45ccde695246eb8a76160cb58e50b36ee45d72110f9c468206bc6093c249fe93` |
| jsonschema | 4.26.0 | Validação de esquemas do lado Python | MIT | Núcleo | `a7e470e134bfd0e3c76482722260d6b1d5a099de823d61cc5cbabb06e4314c67` |
| serde, serde_json, sha2, jsonschema, referencing, rusqlite, clap | ver `Cargo.lock` | Núcleo de orquestração, esquema, hashing, catálogo, DAG e CLI | MIT OU Apache-2.0 | Núcleo | `Cargo.lock` versionado |

### 2.2 Componentes aprovados, ainda não integrados

| Componente | Papel | Licença | Tipo de integração | Quando entra |
|---|---|---|---|---|
| Open3D | Processamento de nuvens de pontos, registo e visualização | MIT | Ferramenta de protótipo, e base da filtragem de solo | `F4.E8` |
| rasterio | API Python para rasters geoespaciais, sobre GDAL embebido | BSD-3-Clause | Núcleo, opcional | `F4.E7` |
| ONNX Runtime | Execução de descritores e correspondentes aprendidos | MIT | Transitivo, opcional | `F2.E2`, se a medição justificar |
| Ceres Solver | Otimização não linear e ajuste de feixes | New BSD | Transitivo, via o motor de SfM | Já incluído no motor embebido |
| OpenMVG | SfM e visão geométrica | MPL-2.0 | Alternativa de referência | Em avaliação |
| AliceVision | SfM, MVS, meshing e texturização | MPL-2.0 | Alternativa de referência | Em avaliação |
| hloc | Correspondência e recuperação de imagens | Apache-2.0 | Alternativa de referência | Em avaliação |
| OpenMVS | Reconstrução densa, malhas e texturas | **AGPL-3.0** | **Processo externo**, fora do caminho de código | `F4.E1`, instalado pelo utilizador |
| CMVS / PMVS2 | Particionamento de cena e MVS em CPU | **GPL-3.0** | **Processo externo**, fora do caminho de código | Alternativa ao OpenMVS |
| OpenDroneMap | Pipeline de fotogrametria de ponta a ponta | **GPL-3.0** | **Baseline externo**, fora do caminho de código | Baseline de comparação |
| CloudCompare | Inspecção e comparação de nuvens | **GPL-3.0** | **Ferramenta externa de QA** | Ferramenta de QA |
| ExifTool | Leitura de metadados, como referência cruzada | Perl Artistic 1.0 | **Ferramenta externa de QA**, nunca no caminho de código | Opcional, instalado pelo utilizador |
| PDAL | Processamento de nuvens de pontos | BSD | Fora do caminho de código neste ambiente: sem wheel no PyPI e sem `conda` | Substituído por implementação própria em `F4.E8` |

### 2.3 A regra que a lista acima impõe

Nenhuma dependência de sistema entra no caminho de código. A justificação
está em [`processos/auditoria-licencas.md`](processos/auditoria-licencas.md)
e a consequência prática é que o núcleo se instala com
`pip install -r requirements.lock` e `cargo build --locked`, sem privilégios
e sem pacotes de sistema.

## 3. Componentes integrados nesta versão

A secção tem de coincidir com o SBOM. O SBOM gerado pela auditoria é
[`processos/sbom.json`](processos/sbom.json), e a lista de §2.1 é a sua
correspondência em termos de papel. A auditoria é reproduzível com
`python scripts/auditar-licencas.py`, e o resultado é versionado.

**Estado:** o núcleo existe e é auditado, mas ainda não há uma versão
distribuível. A secção passa a descrever a primeira distribuição quando
existir binário, e a regra de ouro continua a ser a mesma: **um componente
que não esteja listado aqui não faz parte do que é distribuído**, e um
componente listado aqui e ausente da distribuição é um erro de ficheiro a
corrigir.

Para a primeira versão, a secção tem de declarar, por componente integrado:
a versão exata, o URL de origem, o hash do artefacto, a licença verificada
nessa versão, e o tipo de integração. A §2.1 já tem a versão, a licença, o
tipo e o hash; falta o URL de origem, que é registado em
`processos/sbom.json` na versão seguinte do ficheiro.

## 4. Regra de manutenção

1. **A tabela muda por adição explícita.** Um componente só entra na §2 depois de a sua licença estar verificada e a integração decidida, e a decisão tem de estar registada em `processos/decisoes-motores.md`.
2. **A §3 tem de coincidir com o SBOM.** O inventário de licenças exigido por [`docs/Khnumn.md` §20](docs/Khnumn.md) e esta seção descrevem o mesmo conjunto de componentes. Se divergirem, é a §3 que está errada.
3. **A licença verifica-se por build.** A licença de uma dependência transitiva pode diferir da licença da biblioteca que a invoca, e a auditoria é feita sobre a árvore de dependências compilada, não sobre a lista declarada.
4. **A data de verificação é obrigatória.** Toda a linha da §2 tem uma data de verificação, e uma licença com mais de um ano sem reverificar é tratada como desconhecida.
5. **A componente copyleft exige aviso no primeiro uso.** Um utilizador que invoque um componente com licença copyleft tem de ser avisado da licença antes da primeira execução, e o aviso tem de ser reproduzível a partir da configuração.
6. **O texto completo de cada licença acompanha a distribuição.** A seção 4(a) da licença do projeto exige que os destinatários recebam uma cópia da licença, e a §4(d) exige que os avisos de atribuição sejam preservados. Nenhuma das duas se cumpre por referência a um URL.

---

**Este ficheiro não é uma auditoria jurídica.** Antes de incorporar qualquer dependência, verificar a licença do código, dos modelos treinados, dos dados de exemplo, dos plugins, das bibliotecas transitivas e dos binários distribuídos, e confirmar também os termos de utilização dos dados de origem.
