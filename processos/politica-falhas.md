# Khnumn — Política de falhas

**Âmbito:** este registo fixa quando uma execução pode continuar com
advertências, quando tem de parar, e o que cada estado significa. Corresponde
a etapa `F0.E6` de `docs/ROADMAP.md`, e a decisão 6 de `docs/Khnumn.md`
§27.2.
**Convenção de referências:** as menções a outros documentos deste repositório
usam o caminho relativo à raiz do repositório.

**Estado:** fixado. Decisão datada de 2026-10-21.

**Versão do registo:** 0.1.0 · **Data:** 2026-10-21 · **Idioma:** Português europeu

---

## 1. Os dois conjuntos de estados

O Khnumn tem dois vocabulários de estado, e confundi-los é uma fonte
clássica de relatórios enganadores.

| Conjunto | Pergunta que responde | Onde vive |
|---|---|---|
| **Estado de tarefa** | O que aconteceu a esta etapa da execução? | §2 deste documento |
| **Estado de produto** | Este produto pode ser usado, e com que garanties? | §3 deste documento |

Uma tarefa pode ter sucesso e o produto pode não ser conforme. Uma tarefa
pode falhar e nenhum produto ser afectado. Os dois vocabulários não se
substituem.

## 2. Estado de tarefa

Os estados são os de `docs/Khnumn.md` §24.4.

| Estado | Significado | Pode ser retido? |
|---|---|---|
| `PENDING` | Aguarda dependências | Não |
| `READY` | Dependências satisfeitas | Não |
| `RUNNING` | A executar | Não |
| `RETRY_WAIT` | Aguarda nova tentativa | Não |
| `SUCCEEDED` | Concluída sem reservas | Sim |
| `SUCCEEDED_WITH_WARNINGS` | Concluída, com produtos utilizáveis e advertências registadas | Sim |
| `FAILED` | Falhou, com causa | Não |
| `CANCELLED` | Cancelada | Não |
| `BLOCKED` | Não executada porque uma dependência falhou | Não |

### 2.1 Regras de transição

1. `SUCCEEDED_WITH_WARNINGS` **exige** produtos utilizáveis e advertências
   registadas. Não pode ser usado para tapar a ausência de uma etapa
   obrigatória.
2. Uma tarefa cuja dependência falhou é `BLOCKED`, e não `FAILED`. A falha
   não é dela, e atribuí-la seria mentir sobre a causa.
3. Uma tarefa que falha não produz sucesso parcial sem marcar os produtos
   afectados (`docs/Khnumn.md` §6.2).
4. `BLOCKED` e `FAILED` exigem causa, sempre, e a causa é escrita, não
   codificada.

### 2.2 Códigos de saída da CLI

| Código | Significado |
|---|---|
| 0 | Execução concluída com sucesso |
| 1 | Uso incorrecto da linha de comandos |
| 2 | Registo ou configuração inválido segundo o esquema |
| 3 | Execução concluída, mas com falhas de qualidade nos dados |
| 4 | Execução bloqueada, requer intervenção humana |
| 5 | Erro interno |

O código de saída é derivado do estado, e o relatório JSON diz sempre qual
dos dois aconteceu.

## 3. Estado de produto

Os estados são os de `docs/Khnumn.md` §15.4, e são emitidos com a causa
concreta que os dispara.

| Estado | Significado | Quando se aplica |
|---|---|---|
| `PASS` | O produto satisfaz as tolerâncias declaradas da classe | Exige pontos de verificação independentes em número suficiente e medidos |
| `PASS_WITH_WARNINGS` | O produto satisfaz as tolerâncias, mas há ressalvas | Advertências que não invalidam o resultado, com a ressalva escrita |
| `FAIL` | O produto não satisfaz as tolerâncias | Um valor fora do limiar, com o valor medido e o limiar no relatório |
| `NOT_VALIDATED` | O produto não foi validado de forma independente | É o estado por omissão quando não há referência independente |

### 3.1 As regras que não se negociam

Estas regras são a razão de a política existir. Cada uma corresponde a uma
maneira concreta de um sistema de fotogrametria enganar quem o usa.

| Regra | Origem |
|---|---|
| `NOT_VALIDATED` é preferível a um `PASS` injustificado | `docs/Khnumn.md` §15.4, §27.2 |
| Sem checkpoints independentes, o estado é `NOT_VALIDATED` e não `PASS` | `docs/Khnumn.md` §15.2 |
| Com menos de 30 pontos de verificação, o estado não pode ser `PASS` | ASPRS ed. 2, `docs/Khnumn.md` §15.5 |
| O método `similarity_transform` nunca origina `PASS` | `docs/Khnumn.md` §10.4, ADR-006 |
| `gcp_observations` sem ficheiro de pontos de controlo é um **erro de configuração**, não uma advertência | `docs/Khnumn.md` §24.1 |
| Um ponto de controlo sem covariância 3×3 é um **erro de configuração**, não uma omissão tolerada | `docs/Khnumn.md` §7.1, ADR-007 |
| O erro de reprojecção é diagnóstico; não é portão de aceitação | `docs/Khnumn.md` §15.4 |
| Uma discrepância acima de 3 × o `RMSE` alvo é *blunder*: investigada, explicada e registada, nunca descartada em silêncio | ASPRS ed. 2, `processos/protocolo-benchmark.md` §4.6 |
| Um produto sem estimativa de incerteza declara essa ausência | `docs/Khnumn.md` §3.2 |
| Um produto cuja densidade efectiva é menor do que a nominal declara a origem da superfície | `docs/Khnumn.md` §13.1 |
| Exceder o orçamento de memória de uma tarefa interrompe a tarefa | `processos/hardware-referencia.md` §2 |

### 3.2 A regra do produto sem referência

Este caso merece a sua própria secção, porque é o caso mais frequente na
Fase 2 e o mais fácil de dar errado.

Uma reconstrução SfM sobre um conjunto público é internamente consistente e
pode ter poses correctas **no referencial da cena**. Isso não é
georreferenciação, e não é exactidão absoluta. Sem pontos de verificação
independentes, o estado do produto é `NOT_VALIDATED`, com a causa escrita:
`"sem referência independente; exactidão absoluta não avaliada"`.

Um relatório que diga `PASS` a uma reconstrução sem checkpoints está a
declarar uma exactidão que não mediu.

## 4. Quando a execução para e quando continua

| Situação | Comportamento |
|---|---|
| Ficheiro de pontos de controlo ausente com `method: gcp_observations` | **Para**, com erro de configuração |
| Ponto de controlo sem covariância | **Para**, com erro de configuração |
| Menos de 30 pontos de verificação | **Continua**, com estado `NOT_VALIDATED` e a contagem declarada |
| Marcas de controlo não visíveis em número suficiente | **Para**, com a causa comunicada: um controlo parcialmente detectado degrada a georreferenciação de forma difícil de distinguir de um erro de ajuste (`docs/Khnumn.md` §8.4) |
| Ficheiro não-imagem dentro do conjunto ingerido | **Continua**, registado e declarado como não avaliável |
| Imagem com nitidez, exposição ou ruído fora do limiar | **Continua**, com advertência no quality gate e no relatório de lacunas |
| Ausência de carimbo temporal GNSS | **Continua**, com o instante de captura marcado como ausente e a origem do carimbo declarada |
| Tarefa acima do orçamento de memória | **Interrompe a tarefa**, que é marcada `FAILED` com a causa |
| Dependência de uma tarefa que falhou | **Não executa** a dependente, que fica `BLOCKED` com a causa |
| Duas execuções com a mesma chave de tarefa | **Reutiliza** o resultado da cache, e a execução é marcada como reutilizada |

### 4.1 O padrão comum

Todas as linhas da tabela acima seguem o mesmo princípio, que é o princípio
de `docs/Khnumn.md` §3.1: **a ausência de evidência suficiente produz um
estado explícito, não um resultado plausível.** Uma falha de configuração
para a execução, porque corrigi-la é do utilizador. Uma limitação dos dados
continua, porque os dados são o que são, e o que se pode fazer é declará-la.

## 5. Registo

| Item | Valor |
|---|---|
| Decisão | Estados de tarefa e de produto, com as regras de §3.1 e a tabela de §4 |
| Data | 2026-10-21 |
| Etapa | `F0.E6` de `docs/ROADMAP.md` |
| Referência | `docs/Khnumn.md` §27.2 item 6, §15.4, §24.4 |
| Efeito no roadmap | Nenhum na ordem; fixa o que `F1.E8` e `F3.E11` têm de implementar |

---

**Nota de âmbito:** uma política de falhas não torna um sistema correcto.
Torna as falhas visíveis, e é isso que permite decidir o que fazer a seguir.
