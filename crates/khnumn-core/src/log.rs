//! Logs estruturados, uma linha JSON por evento.
//!
//! A observabilidade e um tema transversal (`docs/ROADMAP.md` §5): cada tarefa
//! tem de deixar rasto do que fez, do que mediu e do que falhou. Um log em
//! texto livre nao e legivel por maquina, e um log estruturado sem indices
//! nao e pesquisavel.

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::Path;

use serde_json::{json, Value};

use crate::error::{Erro, Resultado};

/// Instante actual em UTC, com resolucao de milissegundos.
pub fn agora_utc() -> String {
    let agora = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    format_unix_millis(agora.as_millis() as i64)
}

/// Formata milissegundos desde a epoca como instante UTC ISO 8601.
pub fn format_unix_millis(millis: i64) -> String {
    let segundos = millis.div_euclid(1000);
    let resto = millis.rem_euclid(1000);
    let dias = segundos.div_euclid(86_400);
    let dentro_do_dia = segundos.rem_euclid(86_400);
    let (ano, mes, dia) = civil_de_dias(dias);
    let hora = dentro_do_dia / 3600;
    let minuto = (dentro_do_dia % 3600) / 60;
    let segundo = dentro_do_dia % 60;
    format!("{ano:04}-{mes:02}-{dia:02}T{hora:02}:{minuto:02}:{segundo:02}.{resto:03}Z")
}

/// Converte dias desde 1970-01-01 em ano, mes e dia, no calendario proleptico
/// gregoriano.
pub fn civil_de_dias(dias: i64) -> (i64, u32, u32) {
    let z = dias + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let ano = if m <= 2 { y + 1 } else { y };
    (ano, m as u32, d as u32)
}

/// Registo de eventos estruturados.
pub struct RegistoLog {
    ficheiro: Option<File>,
    verboso: bool,
}

impl RegistoLog {
    /// Cria um registo sem ficheiro, que apenas escreve em caso de erro.
    pub fn sem_ficheiro() -> Self {
        RegistoLog {
            ficheiro: None,
            verboso: false,
        }
    }

    /// Abre um registo que anexa a um ficheiro.
    pub fn abrir(caminho: &Path) -> Resultado<Self> {
        if let Some(directoria) = caminho.parent() {
            std::fs::create_dir_all(directoria).map_err(|e| Erro::io_ficheiro(directoria, e))?;
        }
        let ficheiro = OpenOptions::new()
            .create(true)
            .append(true)
            .open(caminho)
            .map_err(|e| Erro::io_ficheiro(caminho, e))?;
        Ok(RegistoLog {
            ficheiro: Some(ficheiro),
            verboso: true,
        })
    }

    /// Regista um evento.
    pub fn evento(&mut self, evento: &str, campos: BTreeMap<String, Value>) {
        if !self.verboso {
            return;
        }
        let mut registo = json!({
            "instante_utc": agora_utc(),
            "evento": evento,
        });
        if let Some(mapa) = registo.as_object_mut() {
            for (chave, valor) in campos {
                mapa.insert(chave, valor);
            }
        }
        if let Some(ficheiro) = self.ficheiro.as_mut() {
            if let Ok(texto) = serde_json::to_string(&registo) {
                let _ = writeln!(ficheiro, "{texto}");
                let _ = ficheiro.flush();
            }
        }
    }

    /// Regista um evento de erro.
    pub fn erro(&mut self, evento: &str, mensagem: &str) {
        let mut campos = BTreeMap::new();
        campos.insert("erro".to_string(), Value::String(mensagem.to_string()));
        self.evento(evento, campos);
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn a_data_civil_esta_correcta() {
        assert_eq!(civil_de_dias(0), (1970, 1, 1));
        assert_eq!(civil_de_dias(19_723), (2024, 1, 1));
        assert_eq!(format_unix_millis(0), "1970-01-01T00:00:00.000Z");
        assert_eq!(
            format_unix_millis(1_767_225_871_125),
            "2026-01-01T00:04:31.125Z"
        );
    }

    #[test]
    fn o_registo_escreve_uma_linha_json_por_evento() {
        let dir = tempfile::tempdir().unwrap();
        let caminho = dir.path().join("registos.jsonl");
        let mut registo = RegistoLog::abrir(&caminho).unwrap();

        let mut campos = BTreeMap::new();
        campos.insert("tarefa".to_string(), json!("t-1"));
        registo.evento("tarefa_iniciada", campos);
        registo.erro("tarefa_falhada", "motivo");

        let conteudo = std::fs::read_to_string(&caminho).unwrap();
        let linhas: Vec<&str> = conteudo.lines().collect();
        assert_eq!(linhas.len(), 2);

        let primeiro: Value = serde_json::from_str(linhas[0]).unwrap();
        assert_eq!(primeiro["evento"], "tarefa_iniciada");
        assert_eq!(primeiro["tarefa"], "t-1");
        assert!(primeiro["instante_utc"].as_str().unwrap().ends_with('Z'));

        let segundo: Value = serde_json::from_str(linhas[1]).unwrap();
        assert_eq!(segundo["erro"], "motivo");
    }
}
