//! A fronteira entre o nucleo e a camada cientifica.
//!
//! O nucleo Rust sabe o que e uma tarefa, um esquema e uma proveniencia. A
//! camada Python sabe ler uma imagem, medir a sua nitidez e projectar uma
//! coordenada. A fronteira entre as duas e uma unica, estreita e versionada:
//! uma tarefa de cada vez, JSON na entrada, JSON na saida.
//!
//! A forma da fronteira e a mesma que a dos adaptadores de motores externos
//! (`docs/Khnumn.md` §18.3): `run`, `inspect`, `cancel`, `collect_metrics` e
//! `export`. Nenhum tipo do OpenCV, do PROJ ou do COLMAP atravessa esta
//! fronteira em forma nativa.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::dag::{Motor, ResultadoTarefa};
use crate::error::{Erro, Resultado};
use crate::processo;
use crate::tarefa::{Entrada, EstadoTarefa, Saida, Tarefa};

/// Versao do contrato entre o nucleo e a camada cientifica.
pub const VERSAO_CONTRATO: &str = "khnumn-tarefa-v1";

/// Pedido enviado a camada cientifica.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pedido {
    /// Versao do contrato.
    pub contrato: String,
    /// Algoritmo a executar.
    pub algoritmo: String,
    /// Versao do algoritmo.
    pub versao: String,
    /// Parametros.
    pub parametros: Value,
    /// Entradas.
    pub entradas: Vec<Entrada>,
}

/// Resposta da camada cientifica.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Resposta {
    /// Estado final.
    pub estado: String,
    /// Saidas.
    pub saidas: Vec<Saida>,
    /// Metricas.
    pub metricas: BTreeMap<String, Value>,
    /// Advertencias.
    pub avisos: Vec<String>,
    /// Erro, quando a tarefa falhou.
    pub erro: Option<String>,
}

/// Cliente da camada cientifica.
#[derive(Debug, Clone)]
pub struct CamadaPython {
    interpretador: PathBuf,
    raiz: PathBuf,
}

impl CamadaPython {
    /// Cria um cliente.
    ///
    /// `raiz` e a raiz do codigo, onde vive o pacote `python/khnumn`.
    pub fn nova(interpretador: PathBuf, raiz: PathBuf) -> Self {
        CamadaPython {
            interpretador,
            raiz,
        }
    }

    /// Localiza o codigo e o interpretador.
    ///
    /// A ordem e deliberada. `KHNUMN_HOME` e `KHNUMN_PYTHON` tem prioridade,
    /// porque quem instala o Khnumn sabe onde o pôs. A seguir vem a
    /// deteccao a partir do executavel, que funciona numa construcao a
    /// partir do codigo. E a ultima opcao e o interpretador do sistema, que
    /// e o que menos se quer, porque nao fixa versao de dependencia nenhuma.
    pub fn detectar(raiz: &Path) -> Self {
        let raiz = Self::raiz_codigo(raiz);
        let interpretador = Self::interpretador(&raiz);
        CamadaPython {
            interpretador,
            raiz,
        }
    }

    /// Determina a raiz do codigo.
    pub fn raiz_codigo(fallback: &Path) -> PathBuf {
        if let Ok(home) = std::env::var("KHNUMN_HOME") {
            return PathBuf::from(home);
        }
        if let Ok(executavel) = std::env::current_exe() {
            let mut candidato = executavel.as_path();
            while let Some(directoria) = candidato.parent() {
                if directoria
                    .join("python")
                    .join("khnumn")
                    .join("__init__.py")
                    .exists()
                {
                    return directoria.to_path_buf();
                }
                candidato = directoria;
            }
        }
        let caminho = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .to_path_buf();
        if caminho
            .join("python")
            .join("khnumn")
            .join("__init__.py")
            .exists()
        {
            return caminho.canonicalize().unwrap_or(caminho);
        }
        fallback.to_path_buf()
    }

    /// Determina o interpretador Python.
    pub fn interpretador(raiz: &Path) -> PathBuf {
        if let Ok(variavel) = std::env::var("KHNUMN_PYTHON") {
            return PathBuf::from(variavel);
        }
        let venv = raiz.join(".venv").join("bin").join("python");
        if venv.exists() {
            return venv;
        }
        PathBuf::from("python3")
    }

    /// Executa um algoritmo e devolve o resultado.
    pub fn invocar(
        &self,
        algoritmo: &str,
        versao: &str,
        parametros: Value,
        entradas: Vec<Entrada>,
        limite_memoria_mb: Option<u64>,
    ) -> Resultado<ResultadoTarefa> {
        let pedido = Pedido {
            contrato: VERSAO_CONTRATO.to_string(),
            algoritmo: algoritmo.to_string(),
            versao: versao.to_string(),
            parametros,
            entradas,
        };

        let corpo = serde_json::to_string(&pedido)
            .map_err(|e| Erro::json("pedido a camada cientifica", e))?;

        let caminho_python = self.raiz.join("python");
        let mut ambiente = vec![
            (
                "PYTHONPATH".to_string(),
                caminho_python.display().to_string(),
            ),
            ("PYTHONDONTWRITEBYTECODE".to_string(), "1".to_string()),
            ("PYTHONUNBUFFERED".to_string(), "1".to_string()),
        ];
        if let Ok(caminhos) = std::env::var("KHNUMN_PYTHONPATH") {
            let combined = format!("{}:{caminhos}", caminho_python.display());
            ambiente.retain(|(chave, _)| chave != "PYTHONPATH");
            ambiente.insert(0, ("PYTHONPATH".to_string(), combined));
        }

        let argumentos = ["-m", "khnumn.worker"];
        let execucao = processo::executar(
            &self.interpretador,
            &argumentos,
            &ambiente,
            &corpo,
            limite_memoria_mb,
        )?;

        if execucao.stdout.trim().is_empty() {
            return Err(Erro::Python(format!(
                "a camada cientifica nao devolveu resultado para {algoritmo} (codigo de saida {:?}); stderr: {}",
                execucao.codigo_saida,
                execucao.stderr.trim()
            )));
        }

        let resposta: Resposta = serde_json::from_str(execucao.stdout.trim())
            .map_err(|e| Erro::json("resposta da camada cientifica", e))?;

        if let Some(erro) = resposta.erro {
            return Err(Erro::Python(erro));
        }

        let estado = match resposta.estado.as_str() {
            "SUCCEEDED" => EstadoTarefa::Succeeded,
            "SUCCEEDED_WITH_WARNINGS" => EstadoTarefa::SucceededWithWarnings,
            outra => {
                return Err(Erro::Python(format!(
                    "estado desconhecido devolvido pela camada cientifica: {outra}"
                )))
            }
        };

        Ok(ResultadoTarefa {
            saidas: resposta.saidas,
            metricas: resposta.metricas,
            avisos: resposta.avisos,
            pico_memoria_mb: execucao.pico_memoria_mb,
            estado,
        })
    }
}

/// Motor que executa tarefas pela camada cientifica.
pub struct MotorPython {
    camada: CamadaPython,
}

impl MotorPython {
    /// Cria um motor.
    pub fn nova(camada: CamadaPython) -> Self {
        MotorPython { camada }
    }
}

impl Motor for MotorPython {
    fn executar(&mut self, tarefa: &Tarefa) -> Resultado<ResultadoTarefa> {
        self.camada.invocar(
            &tarefa.algoritmo,
            &tarefa.versao,
            tarefa.parametros.clone(),
            tarefa.entradas.clone(),
            tarefa.limite_memoria_mb,
        )
    }
}

/// Algoritmos conhecidos pela camada cientifica.
///
/// A lista e explicita porque um algoritmo desconhecido tem de ser um erro
/// accionavel, e nao um pedido que falha dentro do processo filho.
pub const ALGORITMOS: &[(&str, &str)] = &[
    ("metadados.extrair", "1.0.0"),
    ("qualidade.imagem", "1.0.0"),
];

/// Devolve a versao declarada de um algoritmo.
pub fn versao_de(algoritmo: &str) -> Option<&'static str> {
    ALGORITMOS
        .iter()
        .find(|(nome, _)| *nome == algoritmo)
        .map(|(_, versao)| *versao)
}

/// Descreve o contrato, para registo em relatorios.
pub fn descricao_contrato() -> Value {
    json!({
        "contrato": VERSAO_CONTRATO,
        "verbos": ["run", "inspect", "cancel", "collect_metrics", "export"],
        "algoritmos": ALGORITMOS
            .iter()
            .map(|(nome, versao)| json!({"algoritmo": nome, "versao": versao}))
            .collect::<Vec<_>>(),
    })
}
