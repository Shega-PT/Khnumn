//! Erros do nucleo, com mensagens accionaveis.
//!
//! Um erro que nao diz o que falhou e o que fazer e um erro que obriga a
//! investigates. Cada variante transporta contexto suficiente para que a
//! mensagem seja util sem abrir o codigo.

use std::fmt;
use std::path::Path;

/// Erro do nucleo do Khnumn.
#[derive(Debug)]
pub enum Erro {
    /// Falha de leitura, escrita ou permissao.
    Io {
        contexto: String,
        origem: std::io::Error,
    },
    /// Documento JSON mal formado.
    Json {
        contexto: String,
        origem: serde_json::Error,
    },
    /// Documento que nao cumpre o esquema versionado.
    Esquema {
        esquema: String,
        erros: Vec<ErroEsquema>,
    },
    /// Falha na base de dados local do projecto.
    Loja {
        contexto: String,
        origem: rusqlite::Error,
    },
    /// Configuracao de projecto invalida ou incompleta.
    Config(String),
    /// Contrato violado entre modulos, ou ordem de execucao invalida.
    Estado(String),
    /// A camada Python nao respondeu, ou respondeu de forma invalida.
    Python(String),
}

impl Erro {
    /// Contextualiza um erro de sistema de ficheiros.
    pub fn io(contexto: impl Into<String>, origem: std::io::Error) -> Self {
        Erro::Io {
            contexto: contexto.into(),
            origem,
        }
    }

    /// Contextualiza um erro de leitura de ficheiro, incluindo o caminho.
    pub fn io_ficheiro(caminho: &Path, origem: std::io::Error) -> Self {
        Erro::Io {
            contexto: format!("{}", caminho.display()),
            origem,
        }
    }

    /// Contextualiza um erro de JSON.
    pub fn json(contexto: impl Into<String>, origem: serde_json::Error) -> Self {
        Erro::Json {
            contexto: contexto.into(),
            origem,
        }
    }
}

impl fmt::Display for Erro {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Erro::Io { contexto, origem } => {
                write!(f, "erro de leitura ou escrita em {contexto}: {origem}")
            }
            Erro::Json { contexto, origem } => write!(f, "JSON invalido em {contexto}: {origem}"),
            Erro::Esquema { esquema, erros } => {
                write!(f, "registo invalido segundo o esquema {esquema}:")?;
                for e in erros {
                    write!(f, "\n  - {}: {}", e.caminho, e.mensagem)?;
                }
                Ok(())
            }
            Erro::Loja { contexto, origem } => {
                write!(f, "falha no catalogo local em {contexto}: {origem}")
            }
            Erro::Config(m) => write!(f, "configuracao invalida: {m}"),
            Erro::Estado(m) => write!(f, "estado invalido: {m}"),
            Erro::Python(m) => write!(f, "falha na camada scientifica: {m}"),
        }
    }
}

impl std::error::Error for Erro {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Erro::Io { origem, .. } => Some(origem),
            Erro::Json { origem, .. } => Some(origem),
            Erro::Loja { origem, .. } => Some(origem),
            _ => None,
        }
    }
}

impl From<serde_json::Error> for Erro {
    fn from(origem: serde_json::Error) -> Self {
        Erro::Json {
            contexto: "documento JSON".into(),
            origem,
        }
    }
}

impl From<rusqlite::Error> for Erro {
    fn from(origem: rusqlite::Error) -> Self {
        Erro::Loja {
            contexto: "catalogo".into(),
            origem,
        }
    }
}

/// Erro de validacao contra um esquema, com caminho e mensagem.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ErroEsquema {
    /// Caminho JSON Pointer do campo que falhou.
    pub caminho: String,
    /// Caminho da palavra-chave do esquema que falhou.
    pub esquema: String,
    /// Descricao legivel do problema.
    pub mensagem: String,
}

/// Resultado do nucleo.
pub type Resultado<T> = Result<T, Erro>;
