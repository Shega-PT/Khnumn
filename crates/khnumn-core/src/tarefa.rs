//! Contrato de tarefa.
//!
//! Cada tarefa tem entradas imutaveis, parametros explicitos, versao do
//! algoritmo, limites de recursos e saidas identificadas por hash. Sem esse
//! contrato, a cache nao e uma cache, e a reprodutibilidade e uma promessa.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::canonico::hash_json;

/// Estado de uma tarefa.
///
/// Os estados e as transicoes sao os de `docs/Khnumn.md` §24.4.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EstadoTarefa {
    /// Aguarda dependencias.
    Pending,
    /// Todas as dependencias estao satisfeitas.
    Ready,
    /// A executar.
    Running,
    /// A aguardar antes de nova tentativa.
    RetryWait,
    /// Concluida com sucesso.
    Succeeded,
    /// Concluida com produtos utilizaveis e advertencias registadas.
    SucceededWithWarnings,
    /// Falhou.
    Failed,
    /// Cancelada.
    Cancelled,
    /// Bloqueada por intervencao humana.
    Blocked,
}

impl EstadoTarefa {
    /// Verdadeiro quando a tarefa produziu produtos utilizaveis.
    pub fn concluida_com_valor(self) -> bool {
        matches!(
            self,
            EstadoTarefa::Succeeded | EstadoTarefa::SucceededWithWarnings
        )
    }
}

/// Entrada de uma tarefa.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Entrada {
    /// Papel da entrada: `activo`, `produto`, `pontos_controlo` e outros.
    pub papel: String,
    /// URI da entrada, relativa ao projecto.
    pub uri: String,
    /// Hash do conteudo, quando conhecido.
    pub sha256: Option<String>,
}

/// Saida de uma tarefa.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Saida {
    /// Papel da saida.
    pub papel: String,
    /// URI da saida, relativa ao projecto.
    pub uri: String,
    /// Hash do conteudo, quando conhecido.
    pub sha256: Option<String>,
    /// Tamanho em bytes, quando conhecido.
    pub bytes: Option<u64>,
}

/// Tarefa do grafo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tarefa {
    /// Identificador estavel, derivado do conteudo.
    pub task_id: String,
    /// Identificador do algoritmo.
    pub algoritmo: String,
    /// Versao do algoritmo. A mudanca de versao invalida a cache.
    pub versao: String,
    /// Parametros explicitos e versionados.
    pub parametros: Value,
    /// Entradas imutaveis.
    pub entradas: Vec<Entrada>,
    /// Saidas identificadas por hash.
    pub saidas: Vec<Saida>,
    /// Estado actual.
    pub estado: EstadoTarefa,
    /// Motivo do estado, quando nao for `SUCCEEDED`.
    pub motivo: Option<String>,
    /// Metricas da tarefa.
    pub metricas: BTreeMap<String, Value>,
    /// Limite de memoria declarado, em megabytes.
    pub limite_memoria_mb: Option<u64>,
    /// Pico de memoria medido, em megabytes.
    pub pico_memoria_mb: Option<u64>,
    /// Instante de inicio, em UTC.
    pub inicio_utc: Option<String>,
    /// Instante de fim, em UTC.
    pub fim_utc: Option<String>,
    /// Semente aleatoria, quando a tarefa usa aleatoriedade.
    pub semente: Option<u64>,
    /// Identificador da versao do ambiente, que participa na identidade.
    pub versao_ambiente: String,
}

impl Tarefa {
    /// Cria uma tarefa a partir dos seus elementos constitutivos.
    ///
    /// O identificador e a chave de cache sao derivados do conteudo, e nao
    /// fornecidos de fora: duas tarefas com o mesmo conteudo sao a mesma
    /// tarefa, e nao duas tarefas parecidas.
    pub fn nova(
        algoritmo: impl Into<String>,
        versao: impl Into<String>,
        parametros: Value,
        entradas: Vec<Entrada>,
        versao_ambiente: impl Into<String>,
    ) -> Self {
        let mut tarefa = Tarefa {
            task_id: String::new(),
            algoritmo: algoritmo.into(),
            versao: versao.into(),
            parametros,
            entradas,
            saidas: Vec::new(),
            estado: EstadoTarefa::Pending,
            motivo: None,
            metricas: BTreeMap::new(),
            limite_memoria_mb: None,
            pico_memoria_mb: None,
            inicio_utc: None,
            fim_utc: None,
            semente: None,
            versao_ambiente: versao_ambiente.into(),
        };
        let chave = tarefa.chave();
        tarefa.task_id = format!("t-{}", &chave[..16]);
        tarefa
    }

    /// Chave de identidade da tarefa, usada como chave de cache.
    ///
    /// A chave cobre o algoritmo, a versao, os parametros, as entradas e a
    /// versao do ambiente. Alterar qualquer um destes elementos produz uma
    /// chave diferente, e portanto uma reexecucao. Nao alterar nenhum
    /// produz a mesma chave, e portanto uma reutilizacao.
    pub fn chave(&self) -> String {
        let mut entradas = self.entradas.clone();
        entradas.sort_by(|a, b| (&a.papel, &a.uri, &a.sha256).cmp(&(&b.papel, &b.uri, &b.sha256)));
        hash_json(&serde_json::json!({
            "algoritmo": self.algoritmo,
            "versao": self.versao,
            "parametros": self.parametros,
            "entradas": entradas,
            "ambiente": self.versao_ambiente,
        }))
    }

    /// Marca a tarefa como iniciada.
    pub fn iniciar(&mut self, inicio_utc: impl Into<String>) {
        self.estado = EstadoTarefa::Running;
        self.inicio_utc = Some(inicio_utc.into());
    }

    /// Marca a tarefa como concluida com sucesso.
    pub fn concluir(&mut self, fim_utc: impl Into<String>) {
        self.estado = EstadoTarefa::Succeeded;
        self.fim_utc = Some(fim_utc.into());
    }

    /// Marca a tarefa como falhada, com a causa.
    pub fn falhar(&mut self, motivo: impl Into<String>, fim_utc: impl Into<String>) {
        self.estado = EstadoTarefa::Failed;
        self.motivo = Some(motivo.into());
        self.fim_utc = Some(fim_utc.into());
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use serde_json::json;

    fn entrada(nome: &str) -> Entrada {
        Entrada {
            papel: "activo".into(),
            uri: nome.into(),
            sha256: Some("abc".into()),
        }
    }

    #[test]
    fn a_chave_nao_depende_da_ordem_das_entradas() {
        let a = Tarefa::nova("a", "1", json!({}), vec![entrada("x"), entrada("y")], "env");
        let b = Tarefa::nova("a", "1", json!({}), vec![entrada("y"), entrada("x")], "env");
        assert_eq!(a.chave(), b.chave());
        assert_eq!(a.task_id, b.task_id);
    }

    #[test]
    fn alterar_parametros_altera_a_chave() {
        let a = Tarefa::nova("a", "1", json!({"p": 1}), vec![], "env");
        let b = Tarefa::nova("a", "1", json!({"p": 2}), vec![], "env");
        assert_ne!(a.chave(), b.chave());
    }

    #[test]
    fn alterar_a_entrada_altera_a_chave() {
        let a = Tarefa::nova("a", "1", json!({}), vec![entrada("x")], "env");
        let b = Tarefa::nova("a", "1", json!({}), vec![entrada("z")], "env");
        assert_ne!(a.chave(), b.chave());
    }

    #[test]
    fn alterar_a_versao_altera_a_chave() {
        let a = Tarefa::nova("a", "1", json!({}), vec![], "env");
        let b = Tarefa::nova("a", "2", json!({}), vec![], "env");
        assert_ne!(a.chave(), b.chave());
    }

    #[test]
    fn alterar_o_ambiente_altera_a_chave() {
        let a = Tarefa::nova("a", "1", json!({}), vec![], "env-1");
        let b = Tarefa::nova("a", "1", json!({}), vec![], "env-2");
        assert_ne!(a.chave(), b.chave());
    }
}
