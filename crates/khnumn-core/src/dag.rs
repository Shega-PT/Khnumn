//! Grafo aciclico dirigido de tarefas, com cache em memoria.
//!
//! O DAG e a estrutura de controlo desde o inicio, e nao um refinamento
//! tardio (`docs/Khnumn.md` §6.2). O que nao pode ser adiado e a nocao de
//! tarefa versionada e reexecutavel, porque dela dependem a cache, a
//! reprodutibilidade e a testabilidade de cada etapa.
//!
//! Esta implementacao e em memoria: a persistencia e a recuperacao vem na
//! Fase 7, sem alterar o modelo de dados.

use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::{Erro, Resultado};
use crate::tarefa::{Entrada, EstadoTarefa, Saida, Tarefa};

/// Resultado de uma tarefa executada.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoTarefa {
    /// Saidas produzidas, identificadas por hash.
    pub saidas: Vec<Saida>,
    /// Metricas da execucao.
    pub metricas: BTreeMap<String, Value>,
    /// Advertencias registadas.
    pub avisos: Vec<String>,
    /// Pico de memoria medido, em megabytes.
    pub pico_memoria_mb: Option<u64>,
    /// Estado final, `SUCCEEDED` ou `SUCCEEDED_WITH_WARNINGS`.
    pub estado: EstadoTarefa,
}

impl ResultadoTarefa {
    /// Resultado de sucesso, sem avisos.
    pub fn sucesso(saidas: Vec<Saida>) -> Self {
        ResultadoTarefa {
            saidas,
            metricas: BTreeMap::new(),
            avisos: Vec::new(),
            pico_memoria_mb: None,
            estado: EstadoTarefa::Succeeded,
        }
    }
}

/// Motor que executa uma tarefa.
///
/// A abstracao existe para que o grafo possa ser testado sem a camada
/// cientifica: o DAG tem de poder ser verificado em isolamento, e o
/// comportamento da cache tem de ser observavel sem correr um motor real.
pub trait Motor {
    /// Executa a tarefa e devolve o resultado.
    ///
    /// Um erro aqui e uma falha da tarefa, nao uma falha do grafo: o grafo
    /// marca a tarefa como `FAILED` e bloqueia as dependentes, com a causa.
    fn executar(&mut self, tarefa: &Tarefa) -> Resultado<ResultadoTarefa>;
}

/// No do grafo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoTarefa {
    /// A tarefa.
    pub tarefa: Tarefa,
    /// Identificadores das tarefas de que depende.
    pub depende_de: Vec<String>,
}

/// Grafo de tarefas.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Grafo {
    /// Nos do grafo.
    pub nos: Vec<NoTarefa>,
}

impl Grafo {
    /// Cria um grafo vazio.
    pub fn novo() -> Self {
        Grafo { nos: Vec::new() }
    }

    /// Acrescenta um no.
    pub fn adicionar(&mut self, tarefa: Tarefa, depende_de: Vec<String>) {
        self.nos.push(NoTarefa { tarefa, depende_de });
    }

    /// Devolve a ordem topologica dos identificadores de tarefa.
    ///
    /// Um ciclo e um erro, e nao uma ordem parcial: um DAG com ciclo nao e um
    /// grafo aciclico, e fingir que e seria transformar um erro de
    /// modelacao num silencio em tempo de execucao.
    pub fn ordem_topologica(&self) -> Resultado<Vec<String>> {
        let mut grau: HashMap<&str, usize> = HashMap::new();
        let mut seguintes: HashMap<&str, Vec<&str>> = HashMap::new();
        let mut conhecidos: HashSet<&str> = HashSet::new();

        for no in &self.nos {
            conhecidos.insert(no.tarefa.task_id.as_str());
        }

        for no in &self.nos {
            grau.insert(no.tarefa.task_id.as_str(), 0);
            for dependencia in &no.depende_de {
                if !conhecidos.contains(dependencia.as_str()) {
                    return Err(Erro::Estado(format!(
                        "a tarefa {} depende de {}, que nao existe no grafo",
                        no.tarefa.task_id, dependencia
                    )));
                }
                *grau.entry(no.tarefa.task_id.as_str()).or_insert(0) += 1;
                seguintes
                    .entry(dependencia.as_str())
                    .or_default()
                    .push(no.tarefa.task_id.as_str());
            }
        }

        let mut prontas: VecDeque<&str> = grau
            .iter()
            .filter(|(_, &g)| g == 0)
            .map(|(id, _)| *id)
            .collect();
        let mut ordem = Vec::with_capacity(self.nos.len());

        while let Some(atual) = prontas.pop_front() {
            ordem.push(atual.to_string());
            if let Some(seguintes_atual) = seguintes.get(atual) {
                for seguinte in seguintes_atual {
                    let entrada = grau.get_mut(seguinte).expect("no com grau registado");
                    *entrada -= 1;
                    if *entrada == 0 {
                        prontas.push_back(seguinte);
                    }
                }
            }
        }

        if ordem.len() != self.nos.len() {
            let restantes: Vec<&str> = grau
                .iter()
                .filter(|(_, &g)| g > 0)
                .map(|(id, _)| *id)
                .collect();
            return Err(Erro::Estado(format!(
                "o grafo tem um ciclo; tarefas envolvidas: {restantes:?}"
            )));
        }

        Ok(ordem)
    }

    /// Devolve a tarefa de um identificador.
    pub fn tarefa(&self, id: &str) -> Option<&Tarefa> {
        self.nos
            .iter()
            .find(|n| n.tarefa.task_id == id)
            .map(|n| &n.tarefa)
    }
}

/// Execucao de uma tarefa, com o que efectivamente aconteceu.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Execucao {
    /// Identificador da tarefa.
    pub task_id: String,
    /// Algoritmo executado.
    pub algoritmo: String,
    /// Estado final.
    pub estado: EstadoTarefa,
    /// Causa, quando o estado nao e de sucesso.
    pub motivo: Option<String>,
    /// Verdadeiro quando o resultado veio da cache.
    pub reutilizada: bool,
    /// Metricas.
    pub metricas: BTreeMap<String, Value>,
    /// Pico de memoria, em megabytes.
    pub pico_memoria_mb: Option<u64>,
    /// Duracao em milissegundos.
    pub duracao_ms: u128,
}

/// Relatorio de uma execucao do grafo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelatorioExecucao {
    /// Execucoes, por tarefa, na ordem de execucao.
    pub execucoes: Vec<Execucao>,
    /// Numero de tarefas que correram.
    pub executadas: usize,
    /// Numero de tarefas servidas pela cache.
    pub reutilizadas: usize,
    /// Tarefas que nao produziram resultado utilizavel.
    pub falhadas: usize,
    /// Tarefas bloqueadas por falha de dependencia.
    pub bloqueadas: usize,
    /// Verdadeiro se todas as tarefas concluiram com valor.
    pub sucesso: bool,
}

/// Executor com cache em memoria.
#[derive(Debug, Default)]
pub struct Executor {
    cache: HashMap<String, ResultadoTarefa>,
}

impl Executor {
    /// Cria um executor sem cache.
    pub fn novo() -> Self {
        Executor {
            cache: HashMap::new(),
        }
    }

    /// Numero de entradas em cache.
    pub fn entradas_em_cache(&self) -> usize {
        self.cache.len()
    }

    /// Esvazia a cache.
    pub fn limpar_cache(&mut self) {
        self.cache.clear();
    }

    /// Executa o grafo.
    ///
    /// A ordem e topologica, a cache e por chave de tarefa, e uma tarefa
    /// cujas dependencias falharam fica `BLOCKED` com a causa, e nao
    /// `FAILED`: a falha nao e dela, e atribuí-la seria mentir sobre a causa.
    pub fn executar(
        &mut self,
        grafo: &Grafo,
        motor: &mut dyn Motor,
    ) -> Resultado<RelatorioExecucao> {
        let ordem = grafo.ordem_topologica()?;
        let mut estados: HashMap<String, EstadoTarefa> = HashMap::new();
        let mut execucoes: Vec<Execucao> = Vec::with_capacity(ordem.len());
        let mut executadas = 0usize;
        let mut reutilizadas = 0usize;
        let mut falhadas = 0usize;
        let mut bloqueadas = 0usize;

        for id in &ordem {
            let no = grafo
                .nos
                .iter()
                .find(|n| &n.tarefa.task_id == id)
                .ok_or_else(|| Erro::Estado(format!("tarefa {id} desapareceu do grafo")))?;

            let dependencia_rota = no.depende_de.iter().find_map(|d| match estados.get(d) {
                Some(EstadoTarefa::Succeeded) | Some(EstadoTarefa::SucceededWithWarnings) => None,
                Some(_) => Some(format!(
                    "a dependencia {d} nao produziu resultado utilizavel"
                )),
                None => Some(format!("a dependencia {d} nao foi executada")),
            });

            if let Some(motivo) = dependencia_rota {
                bloqueadas += 1;
                estados.insert(id.clone(), EstadoTarefa::Blocked);
                execucoes.push(Execucao {
                    task_id: id.clone(),
                    algoritmo: no.tarefa.algoritmo.clone(),
                    estado: EstadoTarefa::Blocked,
                    motivo: Some(motivo),
                    reutilizada: false,
                    metricas: BTreeMap::new(),
                    pico_memoria_mb: None,
                    duracao_ms: 0,
                });
                continue;
            }

            let chave = no.tarefa.chave();
            if let Some(resultado) = self.cache.get(&chave) {
                reutilizadas += 1;
                estados.insert(id.clone(), resultado.estado);
                execucoes.push(Execucao {
                    task_id: id.clone(),
                    algoritmo: no.tarefa.algoritmo.clone(),
                    estado: resultado.estado,
                    motivo: None,
                    reutilizada: true,
                    metricas: resultado.metricas.clone(),
                    pico_memoria_mb: resultado.pico_memoria_mb,
                    duracao_ms: 0,
                });
                continue;
            }

            let inicio = std::time::Instant::now();
            executadas += 1;
            let mut tarefa = no.tarefa.clone();
            tarefa.estado = EstadoTarefa::Running;

            match motor.executar(&tarefa) {
                Ok(resultado) => {
                    let duracao_ms = inicio.elapsed().as_millis();
                    let estado = resultado.estado;
                    let motivo = if estado == EstadoTarefa::SucceededWithWarnings
                        && resultado.avisos.is_empty()
                    {
                        Some("estado de sucesso com advertencias, mas sem avisos registados".into())
                    } else {
                        None
                    };
                    estados.insert(id.clone(), estado);
                    self.cache.insert(chave, resultado.clone());
                    execucoes.push(Execucao {
                        task_id: id.clone(),
                        algoritmo: tarefa.algoritmo.clone(),
                        estado,
                        motivo,
                        reutilizada: false,
                        metricas: resultado.metricas,
                        pico_memoria_mb: resultado.pico_memoria_mb,
                        duracao_ms,
                    });
                }
                Err(erro) => {
                    let duracao_ms = inicio.elapsed().as_millis();
                    falhadas += 1;
                    estados.insert(id.clone(), EstadoTarefa::Failed);
                    execucoes.push(Execucao {
                        task_id: id.clone(),
                        algoritmo: tarefa.algoritmo.clone(),
                        estado: EstadoTarefa::Failed,
                        motivo: Some(erro.to_string()),
                        reutilizada: false,
                        metricas: BTreeMap::new(),
                        pico_memoria_mb: None,
                        duracao_ms,
                    });
                }
            }
        }

        let sucesso = falhadas == 0 && bloqueadas == 0;
        Ok(RelatorioExecucao {
            execucoes,
            executadas,
            reutilizadas,
            falhadas,
            bloqueadas,
            sucesso,
        })
    }
}

/// Construtor de grafo, para uso legivel nos testes e na CLI.
pub fn grafo_de(tarefas: Vec<(Tarefa, Vec<&str>)>) -> Grafo {
    let mut grafo = Grafo::novo();
    for (tarefa, depende_de) in tarefas {
        grafo.adicionar(
            tarefa,
            depende_de.into_iter().map(|s| s.to_string()).collect(),
        );
    }
    grafo
}

/// Entrada vazia, para tarefas sem ficheiros de entrada.
pub fn sem_entradas() -> Vec<Entrada> {
    Vec::new()
}

#[cfg(test)]
mod testes {
    use super::*;
    use serde_json::json;

    /// Motor de teste, que devolve um resultado fixo e conta as execucoes.
    struct MotorFalso {
        chamadas: usize,
        falhar_em: Option<String>,
    }

    impl Motor for MotorFalso {
        fn executar(&mut self, tarefa: &Tarefa) -> Resultado<ResultadoTarefa> {
            self.chamadas += 1;
            if self.falhar_em.as_deref() == Some(tarefa.algoritmo.as_str()) {
                return Err(Erro::Estado("falha induzida".into()));
            }
            Ok(ResultadoTarefa::sucesso(Vec::new()))
        }
    }

    fn tarefa(nome: &str, parametro: i64) -> Tarefa {
        Tarefa::nova(nome, "1", json!({"p": parametro}), Vec::new(), "env")
    }

    #[test]
    fn a_execucao_segue_a_ordem_topologica() {
        let a = tarefa("a", 1);
        let b = tarefa("b", 2);
        let id_a = a.task_id.clone();
        let id_b = b.task_id.clone();
        let grafo = grafo_de(vec![(b, vec![&id_a]), (a, vec![])]);
        let ordem = grafo.ordem_topologica().unwrap();
        assert_eq!(ordem, vec![id_a, id_b]);
    }

    #[test]
    fn um_ciclo_e_um_erro_e_nao_uma_execucao_parcial() {
        let a = tarefa("a", 1);
        let b = tarefa("b", 2);
        let id_a = a.task_id.clone();
        let id_b = b.task_id.clone();
        let grafo = grafo_de(vec![(a, vec![&id_b]), (b, vec![&id_a])]);
        assert!(grafo.ordem_topologica().is_err());
    }

    #[test]
    fn uma_dependencia_inexistente_e_um_erro() {
        let a = tarefa("a", 1);
        let grafo = grafo_de(vec![(a, vec!["nao-existe"])]);
        assert!(grafo.ordem_topologica().is_err());
    }

    #[test]
    fn a_segunda_execucao_reutiliza_a_cache() {
        let a = tarefa("a", 1);
        let grafo = grafo_de(vec![(a, vec![])]);
        let mut motor = MotorFalso {
            chamadas: 0,
            falhar_em: None,
        };

        let mut executor = Executor::novo();
        let primeiro = executor.executar(&grafo, &mut motor).unwrap();
        assert_eq!(primeiro.executadas, 1);
        assert_eq!(primeiro.reutilizadas, 0);

        let segundo = executor.executar(&grafo, &mut motor).unwrap();
        assert_eq!(segundo.executadas, 0);
        assert_eq!(segundo.reutilizadas, 1);
        assert_eq!(
            motor.chamadas, 1,
            "o motor nao devia ter corrido a segunda vez"
        );
    }

    #[test]
    fn alterar_os_parametros_invalida_a_cache() {
        let mut executor = Executor::novo();
        let mut motor = MotorFalso {
            chamadas: 0,
            falhar_em: None,
        };

        let g1 = grafo_de(vec![(tarefa("a", 1), vec![])]);
        let g2 = grafo_de(vec![(tarefa("a", 2), vec![])]);

        executor.executar(&g1, &mut motor).unwrap();
        let segundo = executor.executar(&g2, &mut motor).unwrap();
        assert_eq!(
            segundo.executadas, 1,
            "parametros diferentes sao tarefas diferentes"
        );
        assert_eq!(motor.chamadas, 2);
    }

    #[test]
    fn a_falha_de_uma_tarefa_bloqueia_as_dependentes_sem_as_marcar_como_falhadas() {
        let a = tarefa("a", 1);
        let b = tarefa("b", 2);
        let id_a = a.task_id.clone();
        let grafo = grafo_de(vec![(a, vec![]), (b, vec![&id_a])]);
        let mut motor = MotorFalso {
            chamadas: 0,
            falhar_em: Some("a".into()),
        };

        let relatorio = Executor::novo().executar(&grafo, &mut motor).unwrap();
        assert_eq!(relatorio.falhadas, 1);
        assert_eq!(relatorio.bloqueadas, 1);
        assert!(!relatorio.sucesso);

        let bloqueada = relatorio
            .execucoes
            .iter()
            .find(|e| e.algoritmo == "b")
            .expect("execucao da tarefa dependente");
        assert_eq!(bloqueada.estado, EstadoTarefa::Blocked);
        assert!(bloqueada.motivo.as_deref().unwrap().contains("dependencia"));
    }
}
