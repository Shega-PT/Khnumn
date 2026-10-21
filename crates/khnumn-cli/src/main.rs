//! Interface de linha de comandos do Khnumn.
//!
//! A CLI e a interface principal para automacao, servidores e depuracao
//! (`docs/Khnumn.md` §19.1). Tudo o que a CLI faz tem de poder ser feito por
//! configuracao versionada, e a saida tem de ser legivel por maquina, com
//! codigos de saida significativos.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use clap::{Parser, Subcommand};
use khnumn_core::canonico::sha256_ficheiro;
use khnumn_core::dag::{Executor, Grafo, RelatorioExecucao};
use khnumn_core::error::{Erro, Resultado};
use khnumn_core::log::{agora_utc, RegistoLog};
use khnumn_core::loja::Loja;
use khnumn_core::modelo::{Activo, Captura, Exposicao, Processamento, Qualidade, VERSAO_METADADOS};
use khnumn_core::processo::pico_memoria_proprio_mb;
use khnumn_core::python::{CamadaPython, MotorPython};
use khnumn_core::schema::RegistoEsquemas;
use khnumn_core::tarefa::{Entrada, Tarefa};
use serde_json::{json, Value};

/// Codigos de saida da CLI.
mod codigos {
    /// Everything ran as expected.
    pub const OK: u8 = 0;
    /// The command was used incorrectly.
    pub const USO: u8 = 1;
    /// A record or configuration did not validate.
    pub const ESQUEMA: u8 = 2;
    /// The data did not meet the project's quality criteria.
    pub const QUALIDADE: u8 = 3;
    /// The execution was blocked and needs human intervention.
    pub const BLOQUEADO: u8 = 4;
    /// An internal error occurred.
    pub const INTERNO: u8 = 5;
}

/// Khnumn - plataforma de evidencia geometrica rastreavel.
#[derive(Debug, Parser)]
#[command(name = "khnumn", version, about, long_about = None)]
struct Cli {
    /// Project directory. Defaults to the current directory.
    #[arg(long, global = true, value_name = "DIR")]
    project: Option<PathBuf>,

    /// Output format: `json` or `text`.
    #[arg(long, global = true, value_name = "FORMATO", default_value = "json")]
    format: FormatoSaida,

    /// Raise verbosity.
    #[arg(short, long, global = true)]
    verbose: bool,

    #[command(subcommand)]
    comando: Comando,
}

/// Output format.
#[derive(Debug, Clone, Copy, PartialEq, Eq, clap::ValueEnum)]
enum FormatoSaida {
    /// Machine-readable JSON.
    Json,
    /// Human-readable text.
    Text,
}

/// Subcommands.
#[derive(Debug, Subcommand)]
enum Comando {
    /// Create the directory structure of a project.
    Init {
        /// Name of the project.
        id: String,
    },
    /// Inventory images, preserving the originals.
    Ingest {
        /// Files or directories to ingest.
        #[arg(required = true)]
        caminhos: Vec<PathBuf>,
    },
    /// Report on missing fields and warnings.
    Report,
    /// Validate the records in the catalogue against the schemas.
    Validate,
    /// Execute the task graph.
    Run,
    /// Show the project state.
    Info,
    /// Run the sparse reconstruction pipeline.
    Sfm {
        /// Files or directories with the images.
        #[arg(required = true)]
        caminhos: Vec<PathBuf>,
        /// Mapper to use.
        #[arg(long, default_value = "incremental", value_name = "MAPEADOR")]
        mapeador: String,
        /// Maximum input image size, in pixels.
        #[arg(long, default_value_t = 1600, value_name = "PIXELS")]
        max_image_size: u32,
        /// Number of threads.
        #[arg(long, default_value_t = 2, value_name = "N")]
        threads: u32,
        /// Maximum number of features per image.
        #[arg(long, default_value_t = 4096, value_name = "N")]
        max_features: u32,
        /// Export the poses and the sparse cloud.
        #[arg(long)]
        exportar: bool,
    },
}

/// Execution context.
struct Contexto {
    project: PathBuf,
    formato: FormatoSaida,
    verboso: bool,
}

impl Contexto {
    fn raiz(&self) -> PathBuf {
        self.project.clone()
    }

    fn loja(&self) -> Resultado<Loja> {
        Loja::abrir(&self.project.join("catalogo").join("catalogo.sqlite"))
    }

    fn esquemas(&self) -> Resultado<RegistoEsquemas> {
        // Os esquemas vao embutidos no binario, para que o contrato viaje
        // com o codigo. Uma directoria externa, se existir, sobrepoe-se.
        let externos = self.raiz().join("schemas");
        if externos.is_dir() {
            RegistoEsquemas::abrir(&externos)
        } else {
            RegistoEsquemas::embutido()
        }
    }

    /// O orcamento de memoria por tarefa, lido da configuracao do projecto.
    fn orcamento_memoria_mb(&self) -> u64 {
        let caminho = self.project.join("projecto.json");
        let Ok(texto) = std::fs::read_to_string(caminho) else {
            return 500;
        };
        let Ok(valor) = serde_json::from_str::<Value>(&texto) else {
            return 500;
        };
        valor
            .get("resources")
            .and_then(|r| r.get("memory_budget_mb"))
            .and_then(|v| v.as_u64())
            .unwrap_or(500)
    }

    fn registo(&self) -> Resultado<RegistoLog> {
        let caminho = self.project.join("registos").join("khnumn.jsonl");
        if self.verboso {
            RegistoLog::abrir(&caminho)
        } else {
            Ok(RegistoLog::sem_ficheiro())
        }
    }

    fn imprime(&self, valor: &Value) {
        match self.formato {
            FormatoSaida::Json => println!(
                "{}",
                serde_json::to_string_pretty(valor).unwrap_or_default()
            ),
            FormatoSaida::Text => imprime_texto(valor, 0),
        }
    }
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    let project = cli.project.clone().unwrap_or_else(|| PathBuf::from("."));
    let contexto = Contexto {
        project,
        formato: cli.format,
        verboso: cli.verbose,
    };

    match executar(&contexto, cli.comando) {
        Ok(codigo) => ExitCode::from(codigo),
        Err(erro) => {
            let saida = json!({
                "estado": "erro",
                "erro": erro.to_string(),
                "tipo": tipo_erro(&erro),
            });
            match contexto.formato {
                FormatoSaida::Json => println!(
                    "{}",
                    serde_json::to_string_pretty(&saida).unwrap_or_default()
                ),
                FormatoSaida::Text => eprintln!("erro: {erro}"),
            }
            ExitCode::from(codigo_para_erro(&erro))
        }
    }
}

fn executar(contexto: &Contexto, comando: Comando) -> Resultado<u8> {
    match comando {
        Comando::Init { id } => cmd_init(contexto, &id),
        Comando::Ingest { caminhos } => cmd_ingest(contexto, &caminhos),
        Comando::Report => cmd_report(contexto),
        Comando::Validate => cmd_validate(contexto),
        Comando::Run => cmd_run(contexto),
        Comando::Info => cmd_info(contexto),
        Comando::Sfm {
            caminhos,
            mapeador,
            max_image_size,
            threads,
            max_features,
            exportar,
        } => cmd_sfm(
            contexto,
            &caminhos,
            &mapeador,
            max_image_size,
            threads,
            max_features,
            exportar,
        ),
    }
}

fn cmd_init(contexto: &Contexto, id: &str) -> Resultado<u8> {
    let raiz = contexto.raiz();
    for directorio in [
        "activos",
        "produtos",
        "relatorios",
        "tarefas",
        "catalogo",
        "registos",
    ] {
        std::fs::create_dir_all(raiz.join(directorio))
            .map_err(|e| Erro::io_ficheiro(&raiz.join(directorio), e))?;
    }

    let loja = contexto.loja()?;
    loja.guardar_meta("projecto_id", id)?;
    loja.guardar_meta("schema_version", VERSAO_METADADOS)?;
    loja.guardar_meta("criado_utc", &agora_utc())?;

    let config = configuracao_por_omissao(id);
    let caminho_config = raiz.join("projecto.json");
    std::fs::write(
        &caminho_config,
        serde_json::to_string_pretty(&config).map_err(|e| Erro::json("configuracao", e))?,
    )
    .map_err(|e| Erro::io_ficheiro(&caminho_config, e))?;

    contexto.imprime(&json!({
        "estado": "criado",
        "projecto": id,
        "raiz": raiz.display().to_string(),
        "configuracao": caminho_config.display().to_string(),
    }));
    Ok(codigos::OK)
}

fn configuracao_por_omissao(id: &str) -> Value {
    json!({
        "schema_version": "1.0.0",
        "id": id,
        "target_crs": "EPSG:4979",
        "scenario": "auto",
        "allow_manual_override": true,
        "capture_instant": "exposure_middle",
        "control": {
            "method": "gnss_pose_priors",
            "gcp_file": null,
            "prior_position_std_m": null,
            "covariance_required": true,
            "propagation": "ensemble",
            "ensemble_samples": 50,
            "ensemble_min_samples": 20
        },
        "dense": {
            "path": "auto",
            "max_iterations": 5,
            "min_density_gain": 0.05,
            "max_outlier_rate": 0.10,
            "first_pass_full_resolution": true,
            "keep_best_iteration": true
        },
        "quality": {
            "independent_checkpoints_required": true,
            "min_checkpoints": 30,
            "max_horizontal_rmse_m": null,
            "max_vertical_rmse_m": null,
            "max_mean_error_ratio": 0.25,
            "blunder_factor": 3.0,
            "acceptance_reference": "ASPRS Positional Accuracy Standards, ed. 2 (2023)",
            "require_uncertainty_report": true,
            "diagnostics": { "max_reprojection_error_px": 1.5 }
        },
        "resources": {
            "execution_mode": "cpu_first",
            "max_workers": 2,
            "memory_budget_mb": 500,
            "temporary_storage_policy": "bounded",
            "gpu": "optional"
        },
        "processing": {
            "preserve_originals": true,
            "image_pyramid": true,
            "sparse_reconstruction": true,
            "dense_reconstruction": false,
            "build_mesh": false,
            "build_orthoimage": false
        },
        "reproducibility": {
            "record_software_versions": true,
            "record_parameters": true,
            "hash_inputs_and_outputs": true
        }
    })
}

fn cmd_ingest(contexto: &Contexto, caminhos: &[PathBuf]) -> Resultado<u8> {
    let mut registo = contexto.registo()?;
    let loja = contexto.loja()?;
    let esquemas = contexto.esquemas()?;
    let camada = CamadaPython::detectar(&CamadaPython::raiz_codigo(&contexto.raiz()));

    let ficheiros = recolher_ficheiros(caminhos)?;
    if ficheiros.is_empty() {
        return Err(Erro::Config(
            "nenhum ficheiro encontrado nos caminhos indicados".into(),
        ));
    }

    let mut ingeridos = 0usize;
    let mut duplicados = 0usize;
    let mut falhados: Vec<Value> = Vec::new();

    for caminho in &ficheiros {
        match ingerir(caminho, &loja, &esquemas, &camada, &mut registo) {
            Ok(Ingestao::Ingerido) => ingeridos += 1,
            Ok(Ingestao::Duplicado) => duplicados += 1,
            Err(erro) => {
                registo.erro("ingestao_falhada", &erro.to_string());
                falhados.push(json!({
                    "caminho": caminho.display().to_string(),
                    "erro": erro.to_string(),
                }));
            }
        }
    }

    let pico = pico_memoria_proprio_mb();
    contexto.imprime(&json!({
        "estado": "concluido",
        "ingeridos": ingeridos,
        "duplicados": duplicados,
        "falhados": falhados.len(),
        "detalhe_falhas": falhados,
        "pico_memoria_mb": pico,
    }));

    if !falhados.is_empty() {
        return Ok(codigos::QUALIDADE);
    }
    Ok(codigos::OK)
}

enum Ingestao {
    Ingerido,
    Duplicado,
}

fn ingerir(
    caminho: &Path,
    loja: &Loja,
    esquemas: &RegistoEsquemas,
    camada: &CamadaPython,
    registo: &mut RegistoLog,
) -> Resultado<Ingestao> {
    let sha256 = sha256_ficheiro(caminho).map_err(|e| Erro::io_ficheiro(caminho, e))?;

    if loja.activo_por_hash(&sha256)?.is_some() {
        return Ok(Ingestao::Duplicado);
    }

    let metadados = std::fs::metadata(caminho).map_err(|e| Erro::io_ficheiro(caminho, e))?;
    let mtime_utc = mtime_utc(
        metadados
            .modified()
            .map_err(|e| Erro::io_ficheiro(caminho, e))?,
    );

    let entradas = vec![Entrada {
        papel: "activo".into(),
        uri: caminho.display().to_string(),
        sha256: Some(sha256.clone()),
    }];

    let resultado = camada.invocar(
        "metadados.extrair",
        "1.0.0",
        json!({ "caminho": caminho.display().to_string() }),
        entradas,
        Some(500),
    )?;

    let bruto = resultado
        .metricas
        .get("metadados")
        .cloned()
        .unwrap_or(json!({}));
    let activo = construir_activo(
        caminho,
        &sha256,
        metadados.len(),
        &mtime_utc,
        &bruto,
        &resultado.avisos,
    )?;

    let valor = serde_json::to_value(&activo)
        .map_err(|e| Erro::json(format!("activo {}", activo.asset_id), e))?;
    esquemas.validar_ou_erro("activo-v1.schema.json", &valor)?;

    loja.gravar_activo(&activo)?;
    registo.evento(
        "activo_ingerido",
        BTreeMap::from([
            ("asset_id".to_string(), json!(activo.asset_id)),
            ("sha256".to_string(), json!(activo.sha256)),
        ]),
    );
    Ok(Ingestao::Ingerido)
}

fn construir_activo(
    caminho: &Path,
    sha256: &str,
    tamanho: u64,
    mtime_utc: &str,
    metadados: &Value,
    avisos: &[String],
) -> Resultado<Activo> {
    let asset_id = format!("a-{}", &sha256[..16]);
    let campos_ausentes: Vec<String> = metadados
        .get("campos_ausentes")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    Ok(Activo {
        schema_version: VERSAO_METADADOS.to_string(),
        asset_id,
        source_uri: caminho.display().to_string(),
        sha256: sha256.to_string(),
        media_type: metadados
            .get("media_type")
            .and_then(|v| v.as_str())
            .unwrap_or("application/octet-stream")
            .to_string(),
        size_bytes: tamanho,
        mtime_utc: mtime_utc.to_string(),
        campos_ausentes,
        avisos: avisos.to_vec(),
        capture: Captura {
            capture_time_utc: metadados
                .get("capture_time_utc")
                .and_then(|v| v.as_str())
                .map(String::from),
            clock_source: metadados
                .get("clock_source")
                .and_then(|v| v.as_str())
                .unwrap_or("ausente")
                .to_string(),
            clock_confidence: metadados
                .get("clock_confidence")
                .and_then(|v| v.as_str())
                .unwrap_or("nenhuma")
                .to_string(),
            sensor_id: metadados
                .get("sensor_id")
                .and_then(|v| v.as_str())
                .map(String::from),
            position: None,
            orientation: None,
        },
        exposure: Exposicao {
            shutter_speed_s: metadados.get("shutter_speed_s").and_then(|v| v.as_f64()),
            aperture: metadados.get("aperture").and_then(|v| v.as_f64()),
            iso: metadados
                .get("iso")
                .and_then(|v| v.as_u64())
                .map(|v| v as u32),
            focal_length_mm: metadados.get("focal_length_mm").and_then(|v| v.as_f64()),
            exposure_time_s: metadados.get("exposure_time_s").and_then(|v| v.as_f64()),
        },
        width: metadados
            .get("width")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32),
        height: metadados
            .get("height")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32),
        processing: Processamento {
            original_preserved: true,
            normalization_profile: "photo-v1".into(),
        },
        quality: None,
        control_point: None,
        vendor_metadata: metadados.get("vendor_metadata").cloned(),
    })
}

fn cmd_report(contexto: &Contexto) -> Resultado<u8> {
    let loja = contexto.loja()?;
    let activos = loja.listar_activos()?;

    let mut por_campo: BTreeMap<String, usize> = BTreeMap::new();
    let mut sem_qualidade = 0usize;
    for activo in &activos {
        for campo in &activo.campos_ausentes {
            *por_campo.entry(campo.clone()).or_insert(0) += 1;
        }
        if activo.quality.is_none() {
            sem_qualidade += 1;
        }
    }

    let qualidade = Qualidade {
        metrics: BTreeMap::new(),
        criterios: BTreeMap::new(),
        resumo: format!("{} activos ingeridos", activos.len()),
    };

    let relatorio = json!({
        "schema_version": "1.0.0",
        "gerado_utc": agora_utc(),
        "projecto": contexto.raiz().display().to_string(),
        "activos": activos.len(),
        "campos_ausentes": por_campo,
        "activos_sem_avaliacao_qualidade": sem_qualidade,
        "qualidade": qualidade,
        "aviso": "Nenhum campo ausente e omitido: cada ausencia esta contada acima.",
    });

    let caminho = contexto.raiz().join("relatorios").join("lacunas.json");
    std::fs::create_dir_all(caminho.parent().unwrap())
        .map_err(|e| Erro::io_ficheiro(caminho.parent().unwrap(), e))?;
    std::fs::write(
        &caminho,
        serde_json::to_string_pretty(&relatorio).map_err(|e| Erro::json("relatorio", e))?,
    )
    .map_err(|e| Erro::io_ficheiro(&caminho, e))?;

    contexto.imprime(&relatorio);
    Ok(codigos::OK)
}

fn cmd_validate(contexto: &Contexto) -> Resultado<u8> {
    let loja = contexto.loja()?;
    let esquemas = contexto.esquemas()?;
    let activos = loja.listar_activos()?;

    let mut invalidos = Vec::new();
    for activo in &activos {
        let valor = serde_json::to_value(activo)
            .map_err(|e| Erro::json(format!("activo {}", activo.asset_id), e))?;
        if let Err(erro) = esquemas.validar_ou_erro("activo-v1.schema.json", &valor) {
            invalidos.push(json!({ "asset_id": activo.asset_id, "erro": erro.to_string() }));
        }
    }

    let resultado = json!({
        "estado": if invalidos.is_empty() { "PASS" } else { "FAIL" },
        "validados": activos.len() - invalidos.len(),
        "invalidos": invalidos,
    });
    contexto.imprime(&resultado);

    if invalidos.is_empty() {
        Ok(codigos::OK)
    } else {
        Ok(codigos::ESQUEMA)
    }
}

fn cmd_run(contexto: &Contexto) -> Resultado<u8> {
    let loja = contexto.loja()?;
    let camada = CamadaPython::detectar(&CamadaPython::raiz_codigo(&contexto.raiz()));
    let mut motor = MotorPython::nova(camada);
    let mut grafo = Grafo::novo();

    let activos = loja.listar_activos()?;
    let mut nao_avaliaveis: Vec<Value> = Vec::new();
    for activo in &activos {
        if !activo.media_type.starts_with("image/") {
            // Um ficheiro que nao e imagem fica registado e declarado, e nao
            // silenciosamente ignorado: e o que permite saber que o
            // inventario nao o perdeu.
            nao_avaliaveis.push(json!({
                "asset_id": activo.asset_id,
                "media_type": activo.media_type,
                "motivo": "nao e uma imagem: o quality gate de imagem nao se aplica",
            }));
            continue;
        }
        let mut tarefa = Tarefa::nova(
            "qualidade.imagem",
            "1.0.0",
            json!({}),
            vec![Entrada {
                papel: "activo".into(),
                uri: activo.source_uri.clone(),
                sha256: Some(activo.sha256.clone()),
            }],
            khnumn_core::versao_ambiente(),
        );
        tarefa.limite_memoria_mb = Some(khnumn_core::processo::pico_admissivel_mb(
            contexto.orcamento_memoria_mb(),
        ));
        grafo.adicionar(tarefa, Vec::new());
    }

    let relatorio = Executor::novo().executar(&grafo, &mut motor)?;
    let actualizados = gravar_qualidades(&loja, &relatorio, &grafo);
    let mut saida = relatorio_para_json(&relatorio);
    if let Some(mapa) = saida.as_object_mut() {
        mapa.insert("qualidade_gravada".to_string(), json!(actualizados));
    }
    if let Some(mapa) = saida.as_object_mut() {
        mapa.insert("nao_avaliaveis".to_string(), json!(nao_avaliaveis));
    }
    contexto.imprime(&saida);

    if relatorio.sucesso {
        Ok(codigos::OK)
    } else if relatorio.bloqueadas > 0 && relatorio.falhadas == 0 {
        Ok(codigos::BLOQUEADO)
    } else {
        Ok(codigos::QUALIDADE)
    }
}

#[allow(clippy::too_many_arguments)]
fn cmd_sfm(
    contexto: &Contexto,
    caminhos: &[PathBuf],
    mapeador: &str,
    max_image_size: u32,
    threads: u32,
    max_features: u32,
    exportar: bool,
) -> Resultado<u8> {
    let camada = CamadaPython::detectar(&CamadaPython::raiz_codigo(&contexto.raiz()));

    let ficheiros: Vec<PathBuf> = recolher_ficheiros(caminhos)?
        .into_iter()
        .filter(|caminho| {
            matches!(
                caminho
                    .extension()
                    .and_then(|e| e.to_str())
                    .map(|e| e.to_lowercase())
                    .as_deref(),
                Some("jpg") | Some("jpeg") | Some("png") | Some("tif") | Some("tiff")
            )
        })
        .collect();

    if ficheiros.is_empty() {
        return Err(Erro::Config(
            "nenhuma imagem encontrada nos caminhos indicados".into(),
        ));
    }

    let imagens: Vec<String> = ficheiros
        .iter()
        .map(|caminho| caminho.display().to_string())
        .collect();

    let base = contexto.raiz().join("tarefas").join("sfm");
    // O par inicial e declarado, e nao escolhido pelo motor: e o que fixa o
    // gauge por construcao, e a sua fixacao tem de estar na parametrizacao
    // e no registo.
    let par_inicial: Vec<String> = imagens
        .iter()
        .take(2)
        .map(|caminho| {
            Path::new(caminho)
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or(caminho)
                .to_string()
        })
        .collect();

    let motor = json!({
        "mapeador": mapeador,
        "max_image_size": max_image_size,
        "num_threads": threads,
        "max_num_features": max_features,
        "use_gpu": false,
        "par_inicial": if par_inicial.len() == 2 { json!(par_inicial) } else { json!(null) },
        "fixar_gauge": true,
        "semente": 0,
    });
    let orcamento = contexto.orcamento_memoria_mb();
    let pico_admissivel = khnumn_core::processo::pico_admissivel_mb(orcamento);

    // As tres fases do motor sao tres tarefas do grafo, e nao uma so. O
    // pico de memoria de cada fase e independente, e uma execucao que fizesse
    // as tres no mesmo processo pagaria a soma.
    let extrair = Tarefa::nova(
        "sfm.extrair",
        "1.0.0",
        json!({ "imagens": imagens, "base": base.display().to_string(), "motor": motor }),
        Vec::new(),
        khnumn_core::versao_ambiente(),
    );
    let id_extrair = extrair.task_id.clone();

    let corresponder = Tarefa::nova(
        "sfm.corresponder",
        "1.0.0",
        json!({ "base": base.display().to_string(), "motor": motor }),
        vec![Entrada {
            papel: "base".into(),
            uri: id_extrair.clone(),
            sha256: None,
        }],
        khnumn_core::versao_ambiente(),
    );
    let id_corresponder = corresponder.task_id.clone();

    let mapear = Tarefa::nova(
        "sfm.mapear",
        "1.0.0",
        json!({ "base": base.display().to_string(), "motor": motor }),
        vec![Entrada {
            papel: "base".into(),
            uri: id_corresponder.clone(),
            sha256: None,
        }],
        khnumn_core::versao_ambiente(),
    );

    // Cada tarefa declara o seu limite de memoria. E o que permite ao
    // executor interromper a tarefa que o excede, em vez de o descobrir
    // quando a maquina fica sem memoria.
    let mut extrair = extrair;
    let mut corresponder = corresponder;
    let mut mapear = mapear;
    extrair.limite_memoria_mb = Some(pico_admissivel);
    corresponder.limite_memoria_mb = Some(pico_admissivel);
    mapear.limite_memoria_mb = Some(pico_admissivel);

    let mut grafo = Grafo::novo();
    grafo.adicionar(extrair, Vec::new());
    grafo.adicionar(corresponder, vec![id_extrair]);
    grafo.adicionar(mapear, vec![id_corresponder]);

    let mut motor_task = MotorPython::nova(camada.clone());
    let relatorio = Executor::novo().executar(&grafo, &mut motor_task)?;

    let mut saida = relatorio_para_json(&relatorio);
    let sfm = relatorio
        .execucoes
        .iter()
        .find(|e| e.algoritmo == "sfm.mapear")
        .and_then(|e| e.metricas.get("sfm").cloned())
        .unwrap_or_else(|| json!({}));

    let mut exportado = serde_json::Value::Null;
    if exportar && relatorio.sucesso {
        let exportacao = camada.invocar(
            "sfm.exportar",
            "1.0.0",
            json!({
                "modelo": base.join("sparse").display().to_string(),
                "destino": contexto.raiz().join("produtos").display().to_string(),
            }),
            Vec::new(),
            Some(pico_admissivel),
        )?;
        exportado = exportacao
            .metricas
            .get("exportacao")
            .and_then(|e| e.get("saidas"))
            .cloned()
            .unwrap_or_else(|| json!([]));
    }

    if let Some(mapa) = saida.as_object_mut() {
        mapa.insert("sfm".to_string(), sfm);
        mapa.insert("exportado".to_string(), exportado);
    }
    contexto.imprime(&saida);

    if relatorio.sucesso {
        Ok(codigos::OK)
    } else if relatorio.bloqueadas > 0 && relatorio.falhadas == 0 {
        Ok(codigos::BLOQUEADO)
    } else {
        Ok(codigos::QUALIDADE)
    }
}

fn cmd_info(contexto: &Contexto) -> Resultado<u8> {
    let loja = contexto.loja()?;
    let project_id = loja
        .ler_meta("projecto_id")?
        .unwrap_or_else(|| "desconhecido".into());
    let activos = loja.numero_activos()?;
    let tarefas = loja.listar_tarefas()?;

    contexto.imprime(&json!({
        "projecto": project_id,
        "raiz": contexto.raiz().display().to_string(),
        "activos": activos,
        "tarefas": tarefas.len(),
        "schemas": contexto.esquemas()?.nomes(),
        "versao_nucleo": khnumn_core::VERSAO,
        "pico_memoria_mb": pico_memoria_proprio_mb(),
    }));
    Ok(codigos::OK)
}

/// Grava a avaliacao de qualidade no registo do activo.
///
/// A qualidade de uma imagem e uma propriedade do activo, e nao um
/// resultado descartavel de uma tarefa: se nao for gravada, o relatorio de
/// lacunas nao a ve, e a proxima execucao volta a pagar o mesmo trabalho.
fn gravar_qualidades(loja: &Loja, relatorio: &RelatorioExecucao, grafo: &Grafo) -> usize {
    let mut gravados = 0usize;
    for execucao in &relatorio.execucoes {
        if !execucao.estado.concluida_com_valor() {
            continue;
        }
        let Some(qualidade) = execucao.metricas.get("qualidade") else {
            continue;
        };
        let Some(tarefa) = grafo.tarefa(&execucao.task_id) else {
            continue;
        };
        let Some(entrada) = tarefa.entradas.first() else {
            continue;
        };
        let Ok(algum) = loja.listar_activos() else {
            continue;
        };
        let Some(mut activo) = algum.into_iter().find(|a| a.source_uri == entrada.uri) else {
            continue;
        };
        activo.quality = Some(khnumn_core::modelo::Qualidade {
            metrics: qualidade
                .get("metrics")
                .and_then(|v| v.as_object())
                .map(|m| {
                    m.iter()
                        .filter_map(|(k, v)| v.as_f64().map(|f| (k.clone(), f)))
                        .collect()
                })
                .unwrap_or_default(),
            criterios: qualidade
                .get("criterios")
                .and_then(|v| v.as_object())
                .map(|m| {
                    m.iter()
                        .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                        .collect()
                })
                .unwrap_or_default(),
            resumo: qualidade
                .get("resumo")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string(),
        });
        if loja.gravar_activo(&activo).is_ok() {
            gravados += 1;
        }
    }
    gravados
}

fn relatorio_para_json(relatorio: &RelatorioExecucao) -> Value {
    json!({
        "estado": if relatorio.sucesso { "PASS" } else { "FAIL" },
        "executadas": relatorio.executadas,
        "reutilizadas": relatorio.reutilizadas,
        "falhadas": relatorio.falhadas,
        "bloqueadas": relatorio.bloqueadas,
        "execucoes": relatorio.execucoes,
    })
}

fn recolher_ficheiros(caminhos: &[PathBuf]) -> Resultado<Vec<PathBuf>> {
    let mut ficheiros = Vec::new();
    for caminho in caminhos {
        if caminho.is_file() {
            ficheiros.push(caminho.clone());
        } else if caminho.is_dir() {
            for entrada in walkdir(caminho)? {
                ficheiros.push(entrada);
            }
        } else {
            return Err(Erro::Config(format!(
                "caminho inexistente: {}",
                caminho.display()
            )));
        }
    }
    ficheiros.sort();
    Ok(ficheiros)
}

fn walkdir(raiz: &Path) -> Resultado<Vec<PathBuf>> {
    let mut ficheiros = Vec::new();
    let mut pilha = vec![raiz.to_path_buf()];
    while let Some(directoria) = pilha.pop() {
        let entradas =
            std::fs::read_dir(&directoria).map_err(|e| Erro::io_ficheiro(&directoria, e))?;
        for entrada in entradas {
            let entrada = entrada.map_err(|e| Erro::io_ficheiro(&directoria, e))?;
            let caminho = entrada.path();
            if caminho.is_dir() {
                pilha.push(caminho);
            } else if caminho.is_file() {
                ficheiros.push(caminho);
            }
        }
    }
    Ok(ficheiros)
}

fn mtime_utc(tempo: std::time::SystemTime) -> String {
    let duracao = tempo
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    khnumn_core::log::format_unix_millis(duracao.as_millis() as i64)
}

fn tipo_erro(erro: &Erro) -> &'static str {
    match erro {
        Erro::Esquema { .. } => "esquema",
        Erro::Config(_) => "configuracao",
        Erro::Estado(_) => "estado",
        Erro::Python(_) => "camada_cientifica",
        Erro::Io { .. } => "io",
        Erro::Json { .. } => "json",
        Erro::Loja { .. } => "catalogo",
    }
}

fn codigo_para_erro(erro: &Erro) -> u8 {
    match erro {
        Erro::Esquema { .. } => codigos::ESQUEMA,
        Erro::Config(_) => codigos::USO,
        Erro::Estado(_) => codigos::BLOQUEADO,
        Erro::Python(_) => codigos::INTERNO,
        _ => codigos::INTERNO,
    }
}

fn imprime_texto(valor: &Value, nivel: usize) {
    let indentacao = "  ".repeat(nivel);
    match valor {
        Value::Object(mapa) => {
            for (chave, item) in mapa {
                match item {
                    Value::Object(_) | Value::Array(_) => {
                        println!("{indentacao}{chave}:");
                        imprime_texto(item, nivel + 1);
                    }
                    outro => println!("{indentacao}{chave}: {outro}"),
                }
            }
        }
        Value::Array(lista) => {
            for item in lista {
                match item {
                    Value::Object(_) | Value::Array(_) => imprime_texto(item, nivel),
                    outro => println!("{indentacao}- {outro}"),
                }
            }
        }
        outro => println!("{indentacao}{outro}"),
    }
}
