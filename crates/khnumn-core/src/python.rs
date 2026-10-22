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
/// accionavel, e nao um pedido que falha dentro do processo filho. Cada
/// algoritmo e identificado pelo seu nome de contrato e pela versao do
/// algoritmo que o implementa; a mudanca de versao invalida a cache de
/// tarefa e obriga a reexecucao.
pub const ALGORITMOS: &[(&str, &str)] = &[
    // Fase 1 — ingestao e inventario.
    ("metadados.extrair", "1.0.0"),
    ("qualidade.imagem", "1.0.0"),
    ("qualidade.duplicados", "1.0.0"),
    // Fase 2 — primeiro pipeline SfM.
    ("sfm.reconstruir", "1.0.0"),
    ("sfm.extrair", "1.0.0"),
    ("sfm.corresponder", "1.0.0"),
    ("sfm.mapear", "1.0.0"),
    ("sfm.exportar", "1.0.0"),
    // Fase 3 — controlo, georreferenciação e validacao.
    ("marcas.detectar", "1.0.0"),
    ("marcas.filtrar", "1.0.0"),
    ("marcas.verificar_acquisibilidade", "1.0.0"),
    ("marcas.rever", "1.0.0"),
    ("controlo.ingerir", "1.0.0"),
    ("controlo.checkpoints", "1.0.0"),
    ("controlo.similaridade", "1.0.0"),
    ("controlo.ajustar", "1.0.0"),
    ("controlo.ensemble", "1.0.0"),
    ("controlo.gnss_priors", "1.0.0"),
    ("controlo.escrever_prior_gnss", "1.0.0"),
    ("validacao.metricas", "1.0.0"),
    ("validacao.incerteza", "1.0.0"),
    ("raster.residuos", "1.0.0"),
    // Fase 4 — reconstrucao densa e produtos 3D.
    ("superficie.triangulacao_esparsa", "1.0.0"),
    ("superficie.reconstrucao_densa", "1.0.0"),
    ("superficie.fundir_nuvens", "1.0.0"),
    ("superficie.processar_blocos", "1.0.0"),
    ("superficie.malha_textura", "1.0.0"),
    ("superficie.refinamento_iterativo", "1.0.0"),
    ("ortoimagem.gerar", "1.0.0"),
    ("dtm.gerar", "1.0.0"),
    ("validacao_denso.comparar", "1.0.0"),
    ("cobertura.gerar", "1.0.0"),
    ("cobertura.incerteza", "1.0.0"),
    // Fase 5 — planeador e deteçao de cenario.
    ("cenario.classificar", "1.0.0"),
    ("cenario.corrigir", "1.0.0"),
    ("planeador.planear", "1.0.0"),
    ("planeador.com_orcamento", "1.0.0"),
    ("planeador.guardar_plano", "1.0.0"),
    // Fase 6 — vídeo e sensores auxiliares.
    ("tempo.sincronizar_relogios", "1.0.0"),
    ("tempo.convenir_instante", "1.0.0"),
    ("video.selecionar_fotogramas", "1.0.0"),
    ("rolling_shutter.modelo_tempo_linha", "1.0.0"),
    ("lidar.ingerir_nuvem", "1.0.0"),
    ("lidar.aplicar_calibracao", "1.0.0"),
    ("radiometria.aplicar_perfil_icc", "1.0.0"),
    ("radiometria.corrigir_vinheta", "1.0.0"),
    ("radiometria.calibrar_reflectancia", "1.0.0"),
    ("satelite.identificar_modelo", "1.0.0"),
    ("satelite.corrigir_rpc", "1.0.0"),
    ("satelite.coregistrar", "1.0.0"),
    ("gnss_imu.integrar_poses", "1.0.0"),
    ("gnss_imu.medir_residuos", "1.0.0"),
    // Fase 7 — distribuição.
    ("persistencia.gravar_grafo", "1.0.0"),
    ("persistencia.recuperar_grafo", "1.0.0"),
    ("scheduler.agendar", "1.0.0"),
    ("worker_remoto.registar", "1.0.0"),
    ("worker_remoto.despachar", "1.0.0"),
    ("retry.registar_tentativa", "1.0.0"),
    ("checkpoint.gravar", "1.0.0"),
    ("checkpoint.verificar_integridade", "1.0.0"),
    ("reprodutibilidade.nivel", "1.0.0"),
    ("reprodutibilidade.comparar", "1.0.0"),
    ("seguranca.autenticar", "1.0.0"),
    ("seguranca.proteger_transporte", "1.0.0"),
    // Fase 8 — fusão heterogénea avançada.
    ("evidencia.agrupar_por_celula", "1.0.0"),
    ("alinhamento.fontes", "1.0.0"),
    ("compatibilidade_temporal.janela", "1.0.0"),
    ("compatibilidade_temporal.marcar_mudancas", "1.0.0"),
    ("decisao_evidencia.aplicar", "1.0.0"),
    ("benchmark_fusao.comparar", "1.0.0"),
    ("verificacao_multivista.acumular", "1.0.0"),
    // Fase 9 — rasterização de superfície e registo de produtos.
    ("catalogo.registar_produto", "1.0.0"),
    ("catalogo.consultar_produto", "1.0.0"),
    ("rasterizador.pontos", "1.0.0"),
    ("rasterizador.hash", "1.0.0"),
    ("cog.publicar", "1.0.0"),
    ("renderizacao.sequencia", "1.0.0"),
    // Etapas desbloqueadas pela Fase 9.
    ("residuos.calcular", "1.0.0"),
    ("cobertura.gerar_cog", "1.0.0"),
    ("cobertura.gerar_incerteza_cog", "1.0.0"),
    ("verificacao_multivista.verificar_completa", "1.0.0"),
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
