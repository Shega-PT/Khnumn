# Khnumn — Auditoria de licenças e matriz de motores

**Âmbito:** este registo fixa a auditoria de licenças efectivamente realizada
sobre a árvore de dependências compilada, a decisão sobre a obtaining de cada
dependência, e as alterações à matriz de motores de
`processos/decisoes-motores.md`. Corresponde a etapa `F0.E7` de
`docs/ROADMAP.md`, e à decisão 5 de `docs/Khnumn.md` §27.2.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Decisão datada de 2026-10-21.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-21 · **Idioma:** Português europeu

**Resultado da auditoria:** o núcleo distribuível é **livre de copyleft
forte**. A verificação é reproduzível com
`python scripts/auditar-licencas.py`, e o inventário está em
`processos/sbom.json`.

---

## 1. A restrição que fixou as decisões

O ambiente não permite instalar pacotes de sistema: não há `sudo` disponível,
e a instalação de software de sistema é uma operação manual fora do alcance
do fluxo de trabalho automatizado.

A consequência é uma regra de decisão de dependências que este registo fixa:

> **Nenhuma dependência de sistema entra no caminho de código. Toda a
> dependência é uma wheel ou um crate, com versão e hash fixados, instalada
> num ambiente próprio do projecto.**

As alternativas foram consideradas:

| Alternativa | Decisão | Motivo |
|---|---|---|
| Pedir a instalação de `exiftool`, `gdal-bin`, `proj` e `colmap` pelo pacote de sistema | **Rejeitada** | Torna a instalação dependente de privilégios e de uma máquina específica, e introduz componentes de sistema com as suas próprias dependências transitivas, que a auditoria tem de cobrir e que ninguém controla |
| Vendorizar binários compilados no repositório | **Rejeitada** | Um binário versionado no Git não tem SBOM, não tem provenance verificável, e é um artefacto opaco para quem recebe a distribuição |
| Embutir o motor num contentor | **Adiada** | Resolve o problema da instalação, mas traz uma dependência de contentor para um sistema que deve correr num computador modesto; a decisão fica para quando houver necessidade de distribuição |
| Wheels e crates permissivos, com versões fixadas | **Adotada** | A licença é auditável, o SBOM é exacto, e a instalação é `pip install -r requirements.lock` mais `cargo build --locked` |

### 1.1 A consequência que não é menor: a leitura de metadados é própria

Sem `exiftool` no caminho de código, a leitura de EXIF e de XMP passa a ser
implementação própria, sobre `Pillow`, `piexif` e `defusedxml`.

Isto é exactamente o que §18.1 e a matriz de motores já admitiam — a matriz dizia
"Ingestão e inventário: Própria" e "Extracção de metadados: ExifTool ou
biblioteca EXIF dedicada" — e o que a política de núcleo livre de copyleft
exige. A diferença é que a decisão deixou de ser uma preferência e passou a
ser uma consequência da restrição de instalação.

O `ExifTool` (Perl Artistic) mantém-se disponível como **ferramenta
externa de QA**, opcional, nunca invocado pelo código. Uma auditoria cruzada
com uma segunda implementação é o que dá confiança a um leitor de EXIF
próprio, e a ferramenta existe para esse fim.

## 2. Resultado da auditoria

A auditoria corre sobre a árvore de dependências compilada, e o seu resultado
automático está em `processos/auditoria-licencas-automatico.md`, com o
inventário em `processos/sbom.json`.

### 2.1 Dependências Python

| Componente | Versão | Licença | Classificação | Papel |
|---|---|---|---|---|
| `pycolmap` | 4.2.1 | BSD-3-Clause | permissiva | Motor de SfM, por adaptor |
| `pyproj` | 3.8.0 | MIT | permissiva | Geodesia e CRS, por PROJ 9.8.1 embebido |
| `numpy` | 2.5.4 | BSD-3-Clause AND MIT AND Zlib AND CC0-1.0 | permissiva | Cálculo numérico |
| `opencv-python-headless` | 5.0.0.93 | Apache-2.0 | permissiva | Processamento de imagem e estimadores geométricos |
| `pillow` | 13.0.0 | MIT-CMU | permissiva | Leitura de imagem e cabeçalhos |
| `piexif` | 1.1.3 | MIT | permissiva | Leitura de EXIF, com GPS e IFDs de exposição |
| `defusedxml` | 0.7.1 | PSF-2.0 | permissiva | Leitura de XMP sem expansão de entidades |
| `jsonschema` | 4.26.0 | MIT | permissiva | Validação de esquemas do lado Python |
| `referencing` | 0.37.0 | MIT | permissiva | Resolução de `$ref` entre esquemas |
| `pytest` | 9.1.1 | MIT | permissiva | Testes |

### 2.2 Dependências Rust

As 238 dependências transitivas de `Cargo.lock` foram verificadas uma a uma.
**Nenhuma é de copyleft forte.** As de copyleft fraco:

| Componente | Versão | Licença | Nota |
|---|---|---|---|
| `r-efi` | 5.3.0, 6.0.0 | MIT OR Apache-2.0 OR LGPL-2.1-or-later | A opção MIT ou Apache-2.0 é a que se aplica, e é permissiva |

As dependências directas são `serde`, `serde_json`, `sha2`, `jsonschema`,
`referencing`, `rusqlite` e `clap`, todas MIT ou Apache-2.0.

### 2.3 O ponto sensível: o motor embebido

O wheel do `pycolmap` embute o COLMAP compilado estaticamente, o que
significa que embute também as suas dependências transitivas. A auditoria
inventariou o que é transportado:

| Biblioteca embebida | Bytes | Leitura |
|---|---|---|
| `libgfortran-83c28eba.so.5.0.0` | 8 426 449 | Runtime Fortran do GCC; licença GPL-3.0 **com excepção de ligação**, que permite a linkage com código proprietário |
| `libgomp-e985bcbb.so.1.0.0` | 2 114 857 | Runtime OpenMP do GCC; mesma excepção |
| `libquadmath-2284e583.so.0.0.0` | 2 100 929 | Runtime de aritmética de precisão quádrupla do GCC; mesma excepção |

Estas três bibliotecas são de runtime de compilador, e a sua licença é a GPL
**com excepção de linkage**, o que as exclui da definição de copyleft forte
para efeitos de distribuição de binários. A constatação é registada aqui
porque é exactamente o tipo de coisa que uma política de núcleo exige que
seja verificada e não presumida.

**Pendência de auditoria contínua:** a excepção de linkage do GCC é uma
condição que se aplica ao código do runtime, e não ao binário que o
distribui. A verificação por inspecção do binário distribuído, e não por
convenção, é o que confirma a política; e essa inspecção é feita sobre cada
versão integrada, e não uma vez.

### 2.4 A dependência que fica de fora

O `PDAL` não tem wheel no PyPI, e a sua distribuição oficial é por
`conda`. Como o ambiente não permite esse caminho, **a filtragem de solo e o
processamento de nuvens de pontos da etapa `F4.E8` serão implementação
própria**, sobre `Open3D` (MIT) e utilidades numéricas.

Esta consequência está alinhada com o que a especificação já exige: a
filtragem de solo não é coberta por nenhum motor de SfM ou MVS, e o Khnumn
tem de a compor e documentar como etapa autónoma (`docs/Khnumn.md` §13.3).
A decisão de detalhe fica em `F4.E8`; o registo aqui é da restrição.

### 2.5 A árvore transitiva dos wheels, e uma regra que daí resulta

A auditoria lê `requirements.lock` e `Cargo.lock`, e **lê o requisito
directo**, não a árvore que ele transporta. Isso é suficiente enquanto as
dependências são bibliotecas de código com as suas dependências declaradas
nos metadados do pacote, e deixa de ser suficiente no momento em que entra um
wheel que embute uma biblioteca nativa completa.

O `rasterio`, que a §18.2 de `docs/Khnumn.md` escolhe para a ortoimagem de
§13.5 e para a publicação dos rasters de §13.6, é o primeiro caso. O wheel
embute o **GDAL**, que é MIT, e o GDAL embute por sua vez o PROJ, o GEOS, o
libpng, o libtiff, o SQLite e outros. A licença do GDAL é MIT, e o inventário
do `rasterio` no PyPI declara-a, mas **o `rasterio` declara a sua, e a do GDAL
vem dentro do wheel**.

A regra que daí resulta, e que passa a valer a partir da integração do
`rasterio`:

> **A auditoria tem de cobrir a árvore transitiva do wheel, e não apenas o
> requisito declarado.** Uma dependência que embute uma biblioteca nativa
> obriga a inventariar o que é transportado, do mesmo modo que o §2.3 já
> inventaria o que o wheel do `pycolmap` embute. A verificação por inspecção do
> binário distribuído, e não por convenção, é o que confirma a política, e essa
> inspecção é feita sobre cada versão integrada, e não uma vez.

Enquanto essa verificação não estiver feita, o `rasterio` fica na §2.2 de
`THIRD-PARTY.md` — aprovado e ainda não integrado — e não na §2.1, que é a
secção do que está efectivamente no produto. A regra de §4.3 de
`THIRD-PARTY.md` não se contorna por ser um wheel: ela diz que a licença de
uma dependência transitiva pode diferir da licença da biblioteca que a invoca,
e que a auditoria é feita sobre a árvore de dependências compilada.

## 3. Matriz de motores: alterações

As alterações à matriz de `processos/decisoes-motores.md` §2, com a causa de
cada uma:

| Função | Decisão anterior | Decisão agora | Causa |
|---|---|---|---|
| Extracção de metadados | ExifTool ou biblioteca EXIF dedicada | **Própria, sobre `Pillow` + `piexif` + `defusedxml`**; ExifTool como QA externo opcional | Sem instalação de sistema no caminho de código (§1) |
| Correspondência e SfM | COLMAP | **COLMAP 4.2.1, por `pycolmap`** | O wheel `pycolmap` é a via de distribuição auditável; o `apt` oferece COLMAP 3.9.1, fora do ADR-001 e sem `pycolmap` para Python 3.12 |
| Geodesia e CRS | PROJ | **PROJ 9.8.1, por `pyproj`** | A geodesia passa obrigatoriamente pela PROJ (`docs/Khnumn.md` §18.1), e o `pyproj` embute-a sem instalação de sistema |
| Superfície em CPU, núcleo permissivo | COLMAP `delaunay_mesher` | **Inalterada** | Já é permissiva e é CPU-only |
| Reconstrução densa, caminho CPU | Motor de MVS externo (OpenMVS) | **Inalterada** | Continua a exigir instalação pelo utilizador, e a instalação é declarada como custo de adopção |
| Reconstrução densa, caminho GPU | COLMAP `patch_match_stereo` | **Inalterada** | Não é executável neste ambiente (§2 de `processos/hardware-referencia.md`) |
| DTM e filtragem de solo | PDAL | **Implementação própria, sobre Open3D** | O PDAL não tem wheel e não há `conda` no ambiente (§2.4) |
| Nuvens de pontos, registo | PDAL e Open3D | **Open3D** | Mesma causa |
| Ortoimagem | GDAL ou Rasterio | **`rasterio` (BSD-3-Clause)**, que embute o GDAL | Wheel disponível, sem instalação de sistema; decisão a confirmar em `F4.E7` |
| Rasterização de superfície | Open3D e CloudCompare, para visualização | **Implementação própria em Rust, no núcleo** | As duas primeiras têm interface gráfica e a segunda é copyleft forte; um motor de GPU violaria o princípio CPU-first. Registo em ADR-012 |
| Escrita de rasters geoespaciais | GDAL de sistema | **`rasterio`**, também para a publicação dos rasters de §13.6 | Mesma causa da linha da ortoimagem; a árvore transitiva do wheel tem de ser auditada (§2.5) |
| TIFF intermédio | — | **crate `tiff`, em Rust, sem features de compressão** | Para zero dependências transitivas; a compressão final é a do COG. Registo em ADR-013 |

## 4. Regras que passam a valer

| Regra | Onde |
|---|---|
| Nenhuma dependência de sistema no caminho de código | Este registo, §1 |
| Toda a dependência tem versão fixa e hash: `requirements.lock` e `Cargo.lock` versionados | `.gitignore`, `docs/Khnumn.md` §20 |
| A auditoria de licenças corre **por build**, e o resultado é versionado em `processos/sbom.json` | `THIRD-PARTY.md` §4.3 |
| A auditoria cobre a **árvore transitiva do wheel**, e não só o requisito declarado | Este registo, §2.5 |
| Uma dependência com licença desconhecida é tratada como desconhecida, e não como permissiva | `THIRD-PARTY.md` §4.4 |
| A data de verificação é obrigatória em cada linha da shortlist | `THIRD-PARTY.md` §4.4 |
| A componente copyleft exige aviso no primeiro uso, e o aviso é reproduzível a partir da configuração | `THIRD-PARTY.md` §4.5 |

## 5. Como repetir a auditoria

```
.venv/bin/python scripts/auditar-licencas.py          # com rede
.venv/bin/python scripts/auditar-licencas.py --offline  # sem rede
```

O relatório automático é `processos/auditoria-licencas-automatico.md` e o
inventário é `processos/sbom.json`. A primeira execução de cada nova
versão de dependência tem de ser lida, e não apenas gerada.

## 6. Registo

| Item | Valor |
|---|---|
| Decisão | Somente wheels e crates permissivos; leitura de metadados própria; `PDAL` fora do caminho de código; a árvore transitiva dos wheels é auditada, e não só o requisito declarado |
| Data | 2026-10-21; revisto em 2026-10-22 |
| Etapa | `F0.E7` de `docs/ROADMAP.md`; revisão em `F9.E2` e `F9.E3` |
| Referência | `docs/Khnumn.md` §27.2 item 5, §18.2, §13.6; `THIRD-PARTY.md` §4; ADR-001, ADR-002, ADR-003, ADR-010, ADR-012, ADR-013 |
| Resultado da auditoria | Núcleo livre de copyleft forte, verificado sobre a árvore compilada |
| Revisão de 2026-10-22 | Acrescentada a regra de auditoria da árvore transitiva do wheel, com o `rasterio` como primeiro caso (§2.5) |
| Efeito no roadmap | Nenhum na ordem; altera a matriz de motores de `processos/decisoes-motores.md` §2 |

---

**Nota de âmbito:** esta auditoria não é um parecer jurídico. Ela verifica o
que a árvore de dependências efectivamente transporta, à data de hoje, e
demonstra a ausência de copyleft forte. Qualquer componente copyleft continua
a exigir revisão jurídica antes de ser adotado, e a fronteira entre
agregação simples e obra derivada continua a depender dos facto.
