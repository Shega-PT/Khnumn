# Khnumn — Modelo de metadados versionado

**Âmbito:** este documento fixa o modelo de dados do Khnumn: o que é um
registo, como é versionado, o que significa a ausência de um campo, e como
se representa a incerteza. Corresponde a etapa `F0.E5` de `docs/ROADMAP.md`,
e à decisão 4 de `docs/Khnumn.md` §27.2.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Decisão datada de 2026-10-21.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-21 · **Idioma:** Português europeu

---

## 1. As quatro decisões que o modelo fixa

| Decisão | Regra | Razão |
|---|---|---|
| **Versão** | Todo o registo carrega `schema_version`, e a versão é semver do esquema | Um registo tem de saber com que versão do contrato foi escrito, ou a evolução do esquema torna os registos antigos ilegíveis |
| **Ausência** | Um campo ausente é `null` e é contado, nunca omitido | A omissão silenciosa de um campo é a forma mais fácil de transformar uma lacuna de dados num resultado plausível |
| **Unidade** | Nenhum valor de incerteza é herdado do CRS das coordenadas | Um sistema geográfico expressa o horizontal em graus e o vertical em metros, e um `0.8` isolado é ambíguo |
| **Certeza** | O que o fornecedor declara é lido e registado como declarado, não como verdade | A diferença entre um valor declarado e um valor verificado é a diferença entre um levantamento e uma opinião |

## 2. Onde vive o contrato

| Elemento | Localização |
|---|---|
| Esquemas | `schemas/*.schema.json`, JSON Schema 2020-12 |
| Validação no núcleo | `crates/khnumn-core/src/schema.rs` |
| Validação na camada científica | `jsonschema` (Python) |
| Referências entre esquemas | Registro de recursos, com o prefixo `https://khnumn.org/esquemas/` |

Os esquemas são **embutidos no binário** com `include_str!`, e não lidos de
um directório ao lado. Um binário que depende de ficheiros externos para
validar é um binário que falha de formas diferentes conforme quem o
instalou, e uma validação que às vezes acontece é pior do que nenhuma.

A consequência prática é que `schemas/` e o binário não podem divergir sem
que a compilação falhe, e a validação funciona a partir de uma cópia
isolada do binário.

### 2.1 Os esquemas

| Esquema | Descreve |
|---|---|
| `activo-v1.schema.json` | Um ficheiro original ingerido: hash, formato, dimensões, captura, exposição, avaliação de qualidade e ponto de controlo associado |
| `controlo-v1.schema.json` | Um ponto de controlo ou de verificação: coordenadas, covariância 3×3, método, instrumento, data e operador |
| `projecto-v1.schema.json` | A configuração versionada de um projecto |
| `produto-v1.schema.json` | Um produto derivado, com CRS, resolução, incerteza e proveniência |

## 3. O registo de um activo

### 3.1 Identidade

| Campo | Tipo | Nota |
|---|---|---|
| `schema_version` | `"1.0.0"` | Versão do esquema com que o registo foi escrito |
| `asset_id` | `a-<16 hex>` | Derivado do SHA-256 do conteúdo. O mesmo conteúdo tem o mesmo identificador, e o mesmo ficheiro com metadados diferentes também: a identidade é do conteúdo |
| `source_uri` | caminho | Relativa ao projecto, ou absoluta quando o ficheiro está fora dele |
| `sha256` | 64 hex | Hash do **original**, que é preservado |
| `media_type` | texto | Determinado pelos bytes mágicos, e não só pela extensão |
| `size_bytes` | inteiro | Tamanho do original |
| `mtime_utc` | instante | Data de modificação do ficheiro. **Não é** tempo de captura |

### 3.2 Ausências

```json
"campos_ausentes": ["position", "orientation", "iso"]
```

A lista é a contagem de tudo o que o ficheiro não traz. Um campo ausente
aparece no registo como `null`, e a sua ausência aparece na lista. São duas
verificações redundantes de propósito: a primeira impede que o registo
mente sobre o que tem, e a segunda permite contar o que falta.

### 3.3 Captura

```json
"capture": {
  "capture_time_utc": "2026-05-12T10:24:31Z",
  "clock_source": "gnss_timestamp",
  "clock_confidence": "alta",
  "sensor_id": "FNX-0001",
  "position": { "...": "..." },
  "orientation": { "source": "exif_orientation", "status": "declared" }
}
```

**A precedência do carimbo temporal** é fixa, e é a ordem da fiabilidade:

| Ordem | Origem | Confiança | Razão |
|---|---|---|---|
| 1 | `gnss_timestamp` | alta | Vem do receptor, com resolução de um segundo |
| 2 | `exif_datetime_original` | média | Vem do relógio da câmara ou do sistema que a configurou |
| 3 | `exif_datetime_original` | baixa | Sem fuso declarado: é uma hora de relógio, não um instante |
| — | `file_mtime` | — | **Nunca é tempo de captura** |

A data de modificação do ficheiro é a data que o utilizador atribui a uma
pasta, e pode divergir do tempo real em horas. Um sistema que a trate como
tempo de captura tem um erro que não aparece no erro de reprojecção, porque
o erro é comum a todas as imagens e o modelo é perfeitamente consistente com
ele (`docs/Khnumn.md` §5.6).

A confiança é `baixa` quando o fuso não está declarado, porque nesse caso o
instante é uma suposição. A suposição é registada, e não disfarçada.

### 3.4 Posição

```json
"position": {
  "crs": "EPSG:4979",
  "coordinates": [-1.2345, 43.21, 120.5],
  "units": { "horizontal": "deg", "vertical": "m" },
  "uncertainty_horizontal": null,
  "uncertainty_vertical": null,
  "source": "GNSS_EXIF",
  "vertical_datum": "elipsoidal_wgs84"
}
```

Três decisões:

1. **O CRS é declarado e a coordenada fica no CRS de origem.** A conversão
   para um referencial local ENU em metros é feita para o cálculo, e o
   referencial local é registado com a sua origem (`docs/Khnumn.md` §7.2).
2. **A incerteza do receptor é nula, e não estimada a partir do DOP.** O
   `GPSHPositioningError` do EXIF é um factor de diluição de precisão, não
   uma incerteza: convertê-lo em incerteza seria inventar uma que não existe.
   O DOP é registado nos metadados do fornecedor, e a incerteza fica nula
   até haver um modelo de erro que a suporte.
3. **O datum vertical é declarado, e distingue elipsoidal de geoidal.** Uma
   altitude EXIF não é usada sem verificar datum, tipo e origem
   (`docs/Khnumn.md` §8.2). Quando o EXIF declara altitude geoidal sem
   identificar o geóide, o registo diz `geoidico_nao_declarado`: a
   incerteza é declarada como parte do datum, e não escondida.

### 3.5 Exposição

| Campo | Unidade | Nota |
|---|---|---|
| `shutter_speed_s` | s | |
| `exposure_time_s` | s | Igual ao anterior, por compatibilidade com a nomenclatura de §24.1 |
| `aperture` | f | Número f |
| `iso` | — | |
| `focal_length_mm` | mm | |

## 4. O ponto de controlo

O esquema `controlo-v1.schema.json` é a parte mais restritiva do modelo, e
é-o de propósito.

| Campo | Obrigatório | Razão |
|---|---|---|
| `role` | sim | `control` ou `checkpoint`. O papel é um compromisso de carga, e não uma convenção do operador |
| `coordinates` | sim | Três componentes, no CRS declarado |
| `covariance` | sim | Matriz 3×3, com unidade explícita. Um escalar não descreve uma incerteza anisotrópica e correlacionada |
| `method` | sim | O método de medição não é decorativo: é o que permite avaliar mais tarde se a incerteza declarada é a adequada para aquele aparelho naquele dia |
| `instrument` | sim | O mesmo, com mais precisão |
| `measured_utc` | sim | A mesma incerteza noutro dia não é a mesma incerteza |
| `operator` | sim | Quem mediu é parte do registo de proveniência da medição |

**Um ponto sem covariância é um erro de configuração**, e não uma omissão
tolerada (`docs/Khnumn.md` §7.1, ADR-007). A covariância é validada contra
a exactidão-alvo do projecto: uma covariância de ordem de grandeza
incompatível com as tolerâncias declaradas é um erro de configuração, porque
determina se o produto vai ser limitado pelo controlo.

## 5. A incerteza como dado

A incerteza é um dado de primeira classe, e nunca é herdada do CRS
(`docs/Khnumn.md` §3.2).

| Tipo | Onde | Forma |
|---|---|---|
| Incerteza escalar | Posição, com unidade explícita | `{"value": 0.8, "unit": "m", "confidence": "1sigma"}` |
| Covariância | Ponto de controlo | Matriz 3×3 com unidade |
| Incerteza de produto | `produto-v1.schema.json` | `estimated` booleano, com valor, unidade e método — **ou** a declaração de que não foi estimada |

A distinção entre "não estimado" e "estimado em zero" é o que separa um
produto honesto de um produto que esconde uma lacuna. O esquema do produto
exige `estimated`, e o seu valor é `false` com uma declaração; um produto sem
incerteza não pode ser serializado sem essa declaração.

## 6. A proveniência

Cada produto conserva a ligação até às fontes e às operações que o
produziram (`docs/Khnumn.md` §7.3). A registo de proveniência é composta por:

- o URI de origem, quando o produto vem de um ficheiro;
- a lista ordenada de operações, cada uma com o identificador da tarefa, o
  algoritmo, a versão e as entradas;
- as versões de software e de bibliotecas;
- a classificação do dado em `medido`, `estimado`, `interpolado` ou
  `inferido_por_modelo`.

A última é a que impede que um produto derivado seja lido como medição. Um
modelo de superfície é `estimado`, mesmo quando os seus pontos são medidos,
e a distinção é o que permite ao relatório dizer o que a exatidão do produto
significa.

## 7. Formato de serialização

JSON, com uma versão de esquema por registo.

A razão de não ser YAML: o contrato é validado por JSON Schema, e
serializar em JSON evita uma segunda gramática com as suas próprias
arredondamentos, as suas próprias datas e as suas próprias surpresas. A
configuração de projecto é JSON pelo mesmo motivo, e a ilustração YAML de
`docs/Khnumn.md` §24.1 é declaradamente ilustrativa.

## 8. Registo

| Item | Valor |
|---|---|
| Decisão | JSON Schema 2020-12, embutido no binário; ausência explícita; unidade explícita; declaração como verdade separada de valor verificado |
| Data | 2026-10-21 |
| Etapa | `F0.E5` de `docs/ROADMAP.md` |
| Referência | `docs/Khnumn.md` §27.2 item 4, §7.1, §7.2, §7.3, §5.6, §8.2, §3.2 |
| Implementado em | `F1.E1`, com o núcleo em `crates/khnumn-core/src/schema.rs` e o modelo em `crates/khnumn-core/src/modelo.rs` |
| Efeito no roadmap | Nenhum na ordem; fixa o contrato de `F1.E1` |

---

**Nota de âmbito:** o modelo de metadados fixa o que o sistema sabe dizer
sobre os dados. Não o faz tornar o sistema correcto: a qualidade da
georreferenciação depende da qualidade do levantamento, e a do levantamento
depende do que foi medido no campo.
