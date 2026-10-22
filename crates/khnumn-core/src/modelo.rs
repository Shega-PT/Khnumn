//! Modelo de dados do Khnumn.
//!
//! Os tipos deste modulo sao a forma executavel do que `docs/Khnumn.md` §7
//! descreve. Duas regras governam o desenho:
//!
//! 1. **Ausencia e um valor, nao um buraco.** Um campo que pode faltar e
//!    serializado como `null` e nao omitido, e o registo lista os campos
//!    ausentes. A omissao silenciosa de um campo e a forma mais facil de
//!    transformar uma lacuna de dados num resultado plausivel.
//! 2. **A incerteza tem sempre unidade.** Nenhum valor de incerteza e herdado
//!    do CRS das coordenadas: um sistema geografico expressa o horizontal em
//!    graus e o vertical em metros, e um `0.8` isolado e ambiguo.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Versao do esquema de metadados de activo.
pub const VERSAO_METADADOS: &str = "1.0.0";

/// Metodo de controlo escolhido para o projecto.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MetodoControlo {
    /// Priors de pose GNSS aplicados no ajuste. Metodo por omissao.
    GnssPosePriors,
    /// Pontos de controlo como observacoes fixas no ajuste.
    GcpObservations,
    /// Transformacao de similaridade aplicada depois da reconstrucao.
    SimilarityTransform,
}

impl MetodoControlo {
    /// Um produto so pode ser declarado conforme com este metodo.
    ///
    /// A similaridade nao propaga incerteza para a geometria, e por isso
    /// nunca origina um estado `PASS` (`docs/Khnumn.md` §10.4).
    pub fn permite_pass(self) -> bool {
        !matches!(self, MetodoControlo::SimilarityTransform)
    }
}

/// Metodo de propagacao da incerteza do controlo.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Propagacao {
    /// Dispersao por ensemble sobre a etapa final.
    Ensemble,
    /// Covariancia analitica da similaridade.
    AnaliticaSimilaridade,
    /// Sem propagacao.
    Nenhuma,
}

/// Caminho de obtencao de superficie.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CaminhoSuperficie {
    /// Triangulacao de Delaunay sobre a nuvem esparsa. CPU, sem copyleft.
    EsparsaDelaunay,
    /// Motor de MVS externo, executado como processo separado.
    DensoCpu,
    /// Motor de referencia em CUDA ou ROCm.
    DensoAcelerador,
}

/// Configuracao do bloco `control` de `docs/Khnumn.md` §24.1.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlConfig {
    /// Metodo de controlo efectivamente usado.
    pub method: MetodoControlo,
    /// Ficheiro de pontos de controlo, quando existe.
    pub gcp_file: Option<String>,
    /// Incerteza GNSS assumida nos priors de pose, em metros.
    pub prior_position_std_m: Option<f64>,
    /// A covariancia 3x3 de cada ponto de controlo e obrigatoria.
    pub covariance_required: bool,
    /// Metodo de propagacao da incerteza do controlo.
    pub propagation: Propagacao,
    /// Numero de execucoes do ensemble.
    pub ensemble_samples: u32,
    /// Numero minimo de amostras declarado.
    pub ensemble_min_samples: u32,
}

/// Configuracao do bloco `dense` de `docs/Khnumn.md` §24.1.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DenseConfig {
    /// Caminho de superficie pedido.
    pub path: String,
    /// Numero maximo de iteracoes do ciclo de refino.
    pub max_iterations: u32,
    /// Limiar de autoconvergencia: ganho minimo de densidade entre iteracoes.
    pub min_density_gain: f64,
    /// Limiar de taxa de outliers que interrompe o ciclo.
    pub max_outlier_rate: f64,
    /// A primeira passagem e feita em resolucao plena.
    pub first_pass_full_resolution: bool,
    /// Retem-se a melhor iteracao, e nao a ultima.
    pub keep_best_iteration: bool,
}

/// Configuracao do bloco `quality` de `docs/Khnumn.md` §24.1.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityConfig {
    /// Exige pontos de verificacao independentes.
    pub independent_checkpoints_required: bool,
    /// Numero minimo de pontos de verificacao (ASPRS ed. 2: trinta).
    pub min_checkpoints: u32,
    /// RMSE horizontal maximo, em metros. `None` significa por fixar.
    pub max_horizontal_rmse_m: Option<f64>,
    /// RMSE vertical maximo, em metros. `None` significa por fixar.
    pub max_vertical_rmse_m: Option<f64>,
    /// Razao maxima entre erro medio e RMSE-alvo (ASPRS ed. 2: 0,25).
    pub max_mean_error_ratio: f64,
    /// Multiplicador do RMSE-alvo acima do qual uma discrepancia e blunder.
    pub blunder_factor: f64,
    /// Referencia normativa aplicada.
    pub acceptance_reference: String,
    /// Exige relatorio de incerteza no produto.
    pub require_uncertainty_report: bool,
    /// Limiares de diagnostico, que nao sao portao de aceitação.
    pub diagnostics: DiagnosticsConfig,
}

/// Limiares de diagnostico interno.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticsConfig {
    /// Erro de reprojecao maximo, em pixeis. Diagnostico, nao portao.
    pub max_reprojection_error_px: f64,
}

/// Configuracao do bloco `resources`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceConfig {
    /// Modo de execucao.
    pub execution_mode: String,
    /// Numero maximo de trabalhadores.
    pub max_workers: u32,
    /// Orcamento de memoria, em megabytes.
    pub memory_budget_mb: u64,
    /// Politica de armazenamento temporario.
    pub temporary_storage_policy: String,
    /// Uso de acelerador: `optional`, `required` ou `forbidden`.
    pub gpu: String,
}

/// Configuracao do bloco `processing`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingConfig {
    /// Preserva os originais.
    pub preserve_originals: bool,
    /// Constroi a piramide de imagem.
    pub image_pyramid: bool,
    /// Executa a reconstrucao esparsa.
    pub sparse_reconstruction: bool,
    /// Executa a reconstrucao densa.
    pub dense_reconstruction: bool,
    /// Constroi a malha.
    pub build_mesh: bool,
    /// Constroi a ortoimagem.
    pub build_orthoimage: bool,
    /// Constroi os mapas de diagnóstico, por rasterização de superfície.
    pub build_diagnostic_maps: bool,
}

/// Configuracao do bloco `reproducibility`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReproducibilityConfig {
    /// Regista versoes de software.
    pub record_software_versions: bool,
    /// Regista parametros.
    pub record_parameters: bool,
    /// Regista hashes de entradas e saidas.
    pub hash_inputs_and_outputs: bool,
}

/// Configuracao de um projecto.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Projecto {
    /// Versao do esquema de configuracao.
    pub schema_version: String,
    /// Identificador do projecto.
    pub id: String,
    /// CRS de destino.
    pub target_crs: String,
    /// Cenario detectado ou imposto.
    pub scenario: String,
    /// Permite sobrepor a deteccao automatica.
    pub allow_manual_override: bool,
    /// Bloco de controlo.
    pub control: ControlConfig,
    /// Bloco de superficie densa.
    pub dense: DenseConfig,
    /// Bloco de qualidade e aceitação.
    pub quality: QualityConfig,
    /// Bloco de recursos.
    pub resources: ResourceConfig,
    /// Bloco de processamento.
    pub processing: ProcessingConfig,
    /// Bloco de reprodutibilidade.
    pub reproducibility: ReproducibilityConfig,
    /// Convencao de instante de captura: `exposure_start`, `exposure_middle`
    /// ou `exposure_end`.
    pub capture_instant: String,
}

/// Incerteza escalar com unidade explicita.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Incerteza {
    /// Valor da incerteza.
    pub value: f64,
    /// Unidade do valor.
    pub unit: String,
    /// Nivel de confianca, quando conhecido.
    pub confidence: Option<String>,
}

/// Posicao geografica de uma captura.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Posicao {
    /// CRS das coordenadas.
    pub crs: String,
    /// Coordenadas no CRS declarado.
    pub coordinates: [f64; 3],
    /// Unidades por eixo.
    pub units: Unidades,
    /// Incerteza horizontal, se declarada.
    pub uncertainty_horizontal: Option<Incerteza>,
    /// Incerteza vertical, se declarada.
    pub uncertainty_vertical: Option<Incerteza>,
    /// Origem do valor.
    pub source: String,
    /// Datum vertical, quando aplicavel.
    pub vertical_datum: Option<String>,
}

/// Unidades por eixo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Unidades {
    /// Unidade horizontal.
    pub horizontal: String,
    /// Unidade vertical.
    pub vertical: String,
}

/// Orientacao declarada de uma captura.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Orientacao {
    /// Origem do valor.
    pub source: String,
    /// Estado da verificacao.
    pub status: String,
}

/// Captura de uma imagem.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Captura {
    /// Instante de captura em UTC, no formato ISO 8601.
    pub capture_time_utc: Option<String>,
    /// Origem do carimbo temporal.
    pub clock_source: String,
    /// Confianca na origem do carimbo temporal.
    pub clock_confidence: String,
    /// Identificador do sensor.
    pub sensor_id: Option<String>,
    /// Posicao conhecida, se existir.
    pub position: Option<Posicao>,
    /// Orientacao, se existir.
    pub orientation: Option<Orientacao>,
}

/// Metadados de exposicao e de captura.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Exposicao {
    /// Velocidade do obturador, em segundos.
    pub shutter_speed_s: Option<f64>,
    /// Numero f.
    pub aperture: Option<f64>,
    /// ISO.
    pub iso: Option<u32>,
    /// Distancia focal, em milimetros.
    pub focal_length_mm: Option<f64>,
    /// Tempo de exposicao, em segundos.
    pub exposure_time_s: Option<f64>,
}

/// Estado do processamento de um activo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Processamento {
    /// O original foi preservado.
    pub original_preserved: bool,
    /// Perfil de normalizacao aplicado.
    pub normalization_profile: String,
}

/// Covariancia 3x3 de um ponto de controlo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Covariancia {
    /// Unidade dos elementos da matriz.
    pub units: String,
    /// Matriz 3x3.
    pub matrix: [[f64; 3]; 3],
}

/// Ponto de controlo, com papel de controlo ou de verificacao.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PontoControlo {
    /// Identificador do ponto.
    pub id: String,
    /// `control` ou `checkpoint`.
    pub role: String,
    /// CRS das coordenadas.
    pub crs: String,
    /// Coordenadas no CRS declarado.
    pub coordinates: [f64; 3],
    /// Unidades por eixo.
    pub units: Unidades,
    /// Covariancia 3x3, obrigatoria.
    pub covariance: Covariancia,
    /// Metodo de medicao.
    pub method: String,
    /// Instrumento usado.
    pub instrument: String,
    /// Instante da medicao, em UTC.
    pub measured_utc: String,
    /// Quem fez a medicao.
    pub operator: String,
}

/// Avaliacao de qualidade de uma imagem.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Qualidade {
    /// Metricas calculadas.
    pub metrics: BTreeMap<String, f64>,
    /// Avaliacao por criterio.
    pub criterios: BTreeMap<String, String>,
    /// Resumo.
    pub resumo: String,
}

/// Registo de um activo ingerido.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Activo {
    /// Versao do esquema de metadados.
    pub schema_version: String,
    /// Identificador estavel do activo.
    pub asset_id: String,
    /// URI de origem, relativa ao projecto.
    pub source_uri: String,
    /// SHA-256 do ficheiro original.
    pub sha256: String,
    /// Tipo de media.
    pub media_type: String,
    /// Tamanho em bytes.
    pub size_bytes: u64,
    /// Data de modificacao, em UTC.
    pub mtime_utc: String,
    /// Campos que o ficheiro nao traz.
    pub campos_ausentes: Vec<String>,
    /// Advertencias registadas na leitura deste activo.
    pub avisos: Vec<String>,
    /// Dados de captura.
    pub capture: Captura,
    /// Parametros de exposicao.
    pub exposure: Exposicao,
    /// Dimensoes da imagem.
    pub width: Option<u32>,
    /// Dimensoes da imagem.
    pub height: Option<u32>,
    /// Estado do processamento.
    pub processing: Processamento,
    /// Avaliacao de qualidade, quando executada.
    pub quality: Option<Qualidade>,
    /// Ponto de controlo associado, quando aplicavel.
    pub control_point: Option<PontoControlo>,
    /// Metadados brutos do fornecedor, lidos e nao verificados.
    pub vendor_metadata: Option<Value>,
}

/// Registo de proveniencia de um produto.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistoProveniencia {
    /// Identificador do produto.
    pub product_id: String,
    /// URI de origem, quando o produto vem de um ficheiro.
    pub source_uri: Option<String>,
    /// Operacoes que produziram o produto, por ordem.
    pub operations: Vec<Operacao>,
    /// Versoes de software e de bibliotecas.
    pub versions: BTreeMap<String, String>,
    /// Classificacao do dado: `medido`, `estimado`, `interpolado` ou
    /// `inferido_por_modelo`.
    pub data_kind: String,
    /// Declaracao explicita da incerteza, quando nao ha estimativa.
    pub uncertainty_declared: Option<String>,
}

/// Operacao que contribuiu para um produto.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Operacao {
    /// Identificador da tarefa.
    pub task_id: String,
    /// Algoritmo.
    pub algorithm: String,
    /// Versao do algoritmo.
    pub version: String,
    /// Entradas da operacao.
    pub inputs: Vec<String>,
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn a_similaridade_nunca_pode_originar_pass() {
        assert!(!MetodoControlo::SimilarityTransform.permite_pass());
        assert!(MetodoControlo::GcpObservations.permite_pass());
        assert!(MetodoControlo::GnssPosePriors.permite_pass());
    }

    #[test]
    fn os_campos_ausentes_sao_serializados_como_nulo_e_nao_omitidos() {
        let captura = Captura {
            capture_time_utc: None,
            clock_source: "ausente".into(),
            clock_confidence: "nenhuma".into(),
            sensor_id: None,
            position: None,
            orientation: None,
        };
        let texto = serde_json::to_string(&captura).unwrap();
        assert!(texto.contains("\"capture_time_utc\":null"));
        assert!(texto.contains("\"position\":null"));
    }

    #[test]
    fn a_covariancia_e_uma_matriz_tres_por_tres() {
        let covariancia = Covariancia {
            units: "m2".into(),
            matrix: [[0.0004, 0.0, 0.0], [0.0, 0.0004, 0.0], [0.0, 0.0, 0.0025]],
        };
        let valor = serde_json::to_value(&covariancia).unwrap();
        assert_eq!(valor["matrix"].as_array().unwrap().len(), 3);
        assert_eq!(valor["matrix"][2][2], 0.0025);
    }
}
