//! Nucleo do Khnumn.
//!
//! O nucleo sabe o que e um registo valido, uma tarefa versionada, um grafo
//! aciclico, um catalogo e uma proveniencia. Nao sabe ler uma imagem, nem
//! projectar uma coordenada, nem reconstruir uma cena: essas coisas pertencem
//! a camada cientifica e aos motores externos, e entram por contratos.
//!
//! A division e deliberada. O nucleo e a parte que tem de sobreviver a
//! qualquer escolha de motor, e por isso e a parte que fica livre de
//! copyleft forte.

pub mod canonico;
pub mod dag;
pub mod error;
pub mod log;
pub mod loja;
pub mod modelo;
pub mod processo;
pub mod python;
pub mod rasterizador;
pub mod schema;
pub mod tarefa;

pub use error::{Erro, ErroEsquema, Resultado};
pub use modelo::{
    Activo, Captura, ControlConfig, Covariancia, DenseConfig, Exposicao, MetodoControlo,
    Orientacao, PontoControlo, Processamento, Projecto, Propagacao, Qualidade, RegistoProveniencia,
    Unidades, VERSAO_METADADOS,
};
pub use schema::RegistoEsquemas;
pub use tarefa::{Entrada, EstadoTarefa, Saida, Tarefa};

/// Versao do nucleo.
pub const VERSAO: &str = env!("CARGO_PKG_VERSION");

/// Versao do ambiente de execucao, que participa na identidade das tarefas.
///
/// Quando uma dependencia muda de versao, a cache das tarefas cujas saidas
/// dependem dela tem de ser invalidada. Incluir a versao do ambiente na
/// chave da tarefa e o que faz essa invalidacao acontecer sem disciplina
/// manual.
pub fn versao_ambiente() -> String {
    format!("khnumn-core/{VERSAO};contrato={}", python::VERSAO_CONTRATO)
}
