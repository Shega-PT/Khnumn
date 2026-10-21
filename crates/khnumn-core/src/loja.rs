//! Catalogo local do projecto, sobre SQLite.
//!
//! O catalogo e o que torna o projecto recuperavel entre execucoes: sem ele,
//! um projecto e um directorio de ficheiros, e a unica forma de saber o que
//! nele existe e reler tudo.
//!
//! A base e local e portatil: SQLite embebido, sem servidor, sem dependencia
//! de sistema. A escolha do modo local ou servidor decide a dependencia, e o
//! modo local e o omissao de um sistema desenhado para correr localmente.

use std::path::Path;

use rusqlite::{params, Connection, OptionalExtension};

use crate::error::{Erro, Resultado};
use crate::modelo::{Activo, RegistoProveniencia};
use crate::tarefa::{EstadoTarefa, Tarefa};

/// Catalogo local de um projecto.
pub struct Loja {
    ligacao: Connection,
}

impl Loja {
    /// Abre o catalogo, creando o esquema se ainda nao existir.
    pub fn abrir(caminho: &Path) -> Resultado<Self> {
        if let Some(directoria) = caminho.parent() {
            std::fs::create_dir_all(directoria).map_err(|e| Erro::io_ficheiro(directoria, e))?;
        }
        let ligacao = Connection::open(caminho).map_err(|e| Erro::Loja {
            contexto: caminho.display().to_string(),
            origem: e,
        })?;
        let loja = Loja { ligacao };
        loja.criar_esquema()?;
        Ok(loja)
    }

    /// Abre o catalogo em memoria, para testes.
    pub fn em_memoria() -> Resultado<Self> {
        let ligacao = Connection::open_in_memory().map_err(|e| Erro::Loja {
            contexto: "memoria".into(),
            origem: e,
        })?;
        let loja = Loja { ligacao };
        loja.criar_esquema()?;
        Ok(loja)
    }

    fn criar_esquema(&self) -> Resultado<()> {
        self.ligacao
            .execute_batch(
                "
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS meta (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS activos (
                    asset_id   TEXT PRIMARY KEY,
                    sha256     TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    media_type TEXT,
                    size_bytes INTEGER,
                    mtime_utc  TEXT,
                    registo    TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS activos_sha256 ON activos(sha256);

                CREATE TABLE IF NOT EXISTS tarefas (
                    task_id   TEXT PRIMARY KEY,
                    algoritmo TEXT NOT NULL,
                    versao    TEXT NOT NULL,
                    chave     TEXT NOT NULL,
                    estado    TEXT NOT NULL,
                    registo   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS produtos (
                    product_id TEXT PRIMARY KEY,
                    tipo       TEXT NOT NULL,
                    registo    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proveniencia (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT,
                    registo    TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS proveniencia_produto ON proveniencia(product_id);
                ",
            )
            .map_err(|e| Erro::Loja {
                contexto: "criacao do esquema".into(),
                origem: e,
            })?;
        Ok(())
    }

    /// Guarda um valor na tabela de metadados.
    pub fn guardar_meta(&self, chave: &str, valor: &str) -> Resultado<()> {
        self.ligacao
            .execute(
                "INSERT INTO meta(chave, valor) VALUES (?1, ?2)
                 ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                params![chave, valor],
            )
            .map_err(|e| Erro::Loja {
                contexto: "meta".into(),
                origem: e,
            })?;
        Ok(())
    }

    /// Le um valor da tabela de metadados.
    pub fn ler_meta(&self, chave: &str) -> Resultado<Option<String>> {
        self.ligacao
            .query_row(
                "SELECT valor FROM meta WHERE chave = ?1",
                params![chave],
                |linha| linha.get::<_, String>(0),
            )
            .optional()
            .map_err(|e| Erro::Loja {
                contexto: "meta".into(),
                origem: e,
            })
    }

    /// Grava um activo, substituindo o registo anterior com o mesmo id.
    pub fn gravar_activo(&self, activo: &Activo) -> Resultado<()> {
        let registo = serde_json::to_string(activo)
            .map_err(|e| Erro::json(format!("activo {}", activo.asset_id), e))?;
        self.ligacao
            .execute(
                "INSERT INTO activos(asset_id, sha256, source_uri, media_type, size_bytes, mtime_utc, registo)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
                 ON CONFLICT(asset_id) DO UPDATE SET
                     sha256 = excluded.sha256,
                     source_uri = excluded.source_uri,
                     media_type = excluded.media_type,
                     size_bytes = excluded.size_bytes,
                     mtime_utc = excluded.mtime_utc,
                     registo = excluded.registo",
                params![
                    activo.asset_id,
                    activo.sha256,
                    activo.source_uri,
                    activo.media_type,
                    activo.size_bytes as i64,
                    activo.mtime_utc,
                    registo
                ],
            )
            .map_err(|e| Erro::Loja { contexto: "activos".into(), origem: e })?;
        Ok(())
    }

    /// Devolve um activo pelo identificador.
    pub fn activo(&self, asset_id: &str) -> Resultado<Option<Activo>> {
        let texto: Option<String> = self
            .ligacao
            .query_row(
                "SELECT registo FROM activos WHERE asset_id = ?1",
                params![asset_id],
                |linha| linha.get::<_, String>(0),
            )
            .optional()
            .map_err(|e| Erro::Loja {
                contexto: "activos".into(),
                origem: e,
            })?;

        match texto {
            Some(t) => {
                Ok(Some(serde_json::from_str(&t).map_err(|e| {
                    Erro::json(format!("activo {asset_id}"), e)
                })?))
            }
            None => Ok(None),
        }
    }

    /// Devolve o activo com um dado hash, se existir.
    ///
    /// E a consulta que torna a deteccao de duplicados exactos possivel sem
    /// reler os ficheiros.
    pub fn activo_por_hash(&self, sha256: &str) -> Resultado<Option<Activo>> {
        let asset_id: Option<String> = self
            .ligacao
            .query_row(
                "SELECT asset_id FROM activos WHERE sha256 = ?1 LIMIT 1",
                params![sha256],
                |linha| linha.get::<_, String>(0),
            )
            .optional()
            .map_err(|e| Erro::Loja {
                contexto: "activos".into(),
                origem: e,
            })?;

        match asset_id {
            Some(id) => self.activo(&id),
            None => Ok(None),
        }
    }

    /// Lista todos os activos, ordenados por URI de origem.
    pub fn listar_activos(&self) -> Resultado<Vec<Activo>> {
        let mut consulta = self
            .ligacao
            .prepare("SELECT registo FROM activos ORDER BY source_uri")
            .map_err(|e| Erro::Loja {
                contexto: "activos".into(),
                origem: e,
            })?;

        let linhas = consulta
            .query_map([], |linha| linha.get::<_, String>(0))
            .map_err(|e| Erro::Loja {
                contexto: "activos".into(),
                origem: e,
            })?;

        let mut activos = Vec::new();
        for linha in linhas {
            let texto = linha.map_err(|e| Erro::Loja {
                contexto: "activos".into(),
                origem: e,
            })?;
            activos.push(serde_json::from_str(&texto).map_err(|e| Erro::json("activo", e))?);
        }
        Ok(activos)
    }

    /// Numero de activos no catalogo.
    pub fn numero_activos(&self) -> Resultado<i64> {
        self.ligacao
            .query_row("SELECT COUNT(*) FROM activos", [], |linha| {
                linha.get::<_, i64>(0)
            })
            .map_err(|e| Erro::Loja {
                contexto: "activos".into(),
                origem: e,
            })
    }

    /// Grava o estado de uma tarefa.
    pub fn gravar_tarefa(&self, tarefa: &Tarefa) -> Resultado<()> {
        let registo = serde_json::to_string(tarefa)
            .map_err(|e| Erro::json(format!("tarefa {}", tarefa.task_id), e))?;
        self.ligacao
            .execute(
                "INSERT INTO tarefas(task_id, algoritmo, versao, chave, estado, registo)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                 ON CONFLICT(task_id) DO UPDATE SET
                     estado = excluded.estado,
                     registo = excluded.registo",
                params![
                    tarefa.task_id,
                    tarefa.algoritmo,
                    tarefa.versao,
                    tarefa.chave(),
                    estado_para_texto(tarefa.estado),
                    registo
                ],
            )
            .map_err(|e| Erro::Loja {
                contexto: "tarefas".into(),
                origem: e,
            })?;
        Ok(())
    }

    /// Lista as tarefas registadas.
    pub fn listar_tarefas(&self) -> Resultado<Vec<Tarefa>> {
        let mut consulta = self
            .ligacao
            .prepare("SELECT registo FROM tarefas ORDER BY task_id")
            .map_err(|e| Erro::Loja {
                contexto: "tarefas".into(),
                origem: e,
            })?;

        let linhas = consulta
            .query_map([], |linha| linha.get::<_, String>(0))
            .map_err(|e| Erro::Loja {
                contexto: "tarefas".into(),
                origem: e,
            })?;

        let mut tarefas = Vec::new();
        for linha in linhas {
            let texto = linha.map_err(|e| Erro::Loja {
                contexto: "tarefas".into(),
                origem: e,
            })?;
            tarefas.push(serde_json::from_str(&texto).map_err(|e| Erro::json("tarefa", e))?);
        }
        Ok(tarefas)
    }

    /// Grava um registo de proveniencia.
    pub fn gravar_proveniencia(&self, registo: &RegistoProveniencia) -> Resultado<()> {
        let texto = serde_json::to_string(registo).map_err(|e| Erro::json("proveniencia", e))?;
        self.ligacao
            .execute(
                "INSERT INTO proveniencia(product_id, registo) VALUES (?1, ?2)",
                params![registo.product_id, texto],
            )
            .map_err(|e| Erro::Loja {
                contexto: "proveniencia".into(),
                origem: e,
            })?;
        Ok(())
    }

    /// Lista os registos de proveniencia de um produto.
    pub fn proveniencia_de(&self, product_id: &str) -> Resultado<Vec<RegistoProveniencia>> {
        let mut consulta = self
            .ligacao
            .prepare("SELECT registo FROM proveniencia WHERE product_id = ?1 ORDER BY id")
            .map_err(|e| Erro::Loja {
                contexto: "proveniencia".into(),
                origem: e,
            })?;

        let linhas = consulta
            .query_map(params![product_id], |linha| linha.get::<_, String>(0))
            .map_err(|e| Erro::Loja {
                contexto: "proveniencia".into(),
                origem: e,
            })?;

        let mut registos = Vec::new();
        for linha in linhas {
            let texto = linha.map_err(|e| Erro::Loja {
                contexto: "proveniencia".into(),
                origem: e,
            })?;
            registos.push(serde_json::from_str(&texto).map_err(|e| Erro::json("proveniencia", e))?);
        }
        Ok(registos)
    }
}

fn estado_para_texto(estado: EstadoTarefa) -> String {
    serde_json::to_string(&estado)
        .unwrap_or_else(|_| "PENDING".into())
        .trim_matches('"')
        .to_string()
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::modelo::{Captura, Exposicao, Processamento, Qualidade, Unidades, VERSAO_METADADOS};

    fn activo_de_exemplo() -> Activo {
        Activo {
            schema_version: VERSAO_METADADOS.to_string(),
            asset_id: "a-0001".into(),
            source_uri: "dados/001.jpg".into(),
            sha256: "a".repeat(64),
            media_type: "image/jpeg".into(),
            size_bytes: 1024,
            mtime_utc: "2026-05-12T10:24:31Z".into(),
            campos_ausentes: vec!["position".into()],
            avisos: Vec::new(),
            capture: Captura {
                capture_time_utc: None,
                clock_source: "ausente".into(),
                clock_confidence: "nenhuma".into(),
                sensor_id: None,
                position: None,
                orientation: None,
            },
            exposure: Exposicao {
                shutter_speed_s: None,
                aperture: None,
                iso: None,
                focal_length_mm: None,
                exposure_time_s: None,
            },
            width: Some(4000),
            height: Some(3000),
            processing: Processamento {
                original_preserved: true,
                normalization_profile: "photo-v1".into(),
            },
            quality: None,
            control_point: None,
            vendor_metadata: None,
        }
    }

    #[test]
    fn um_activo_gravado_e_relido_identico() {
        let loja = Loja::em_memoria().unwrap();
        let activo = activo_de_exemplo();
        loja.gravar_activo(&activo).unwrap();

        let relido = loja.activo("a-0001").unwrap().unwrap();
        assert_eq!(relido.sha256, activo.sha256);
        assert_eq!(relido.campos_ausentes, activo.campos_ausentes);
        assert_eq!(loja.numero_activos().unwrap(), 1);
    }

    #[test]
    fn a_consulta_por_hash_encontra_o_activo() {
        let loja = Loja::em_memoria().unwrap();
        loja.gravar_activo(&activo_de_exemplo()).unwrap();
        let encontrado = loja.activo_por_hash(&"a".repeat(64)).unwrap().unwrap();
        assert_eq!(encontrado.asset_id, "a-0001");
    }

    #[test]
    fn a_proveniencia_fica_associada_ao_produto() {
        let loja = Loja::em_memoria().unwrap();
        let registo = RegistoProveniencia {
            product_id: "p-1".into(),
            source_uri: Some("dados/001.jpg".into()),
            operations: Vec::new(),
            versions: [("khnumn".to_string(), "0.1.0".to_string())]
                .into_iter()
                .collect(),
            data_kind: "medido".into(),
            uncertainty_declared: None,
        };
        loja.gravar_proveniencia(&registo).unwrap();
        let lidos = loja.proveniencia_de("p-1").unwrap();
        assert_eq!(lidos.len(), 1);
        assert_eq!(lidos[0].data_kind, "medido");
    }

    #[test]
    fn o_activo_sobrevive_a_reabertura_da_loja() {
        let dir = tempfile::tempdir().unwrap();
        let caminho = dir.path().join("catalogo.sqlite");
        {
            let loja = Loja::abrir(&caminho).unwrap();
            loja.gravar_activo(&activo_de_exemplo()).unwrap();
        }
        let loja = Loja::abrir(&caminho).unwrap();
        assert_eq!(loja.numero_activos().unwrap(), 1);
        let _ = Unidades {
            horizontal: "m".into(),
            vertical: "m".into(),
        };
        let _ = Qualidade {
            metrics: Default::default(),
            criterios: Default::default(),
            resumo: String::new(),
        };
    }
}
