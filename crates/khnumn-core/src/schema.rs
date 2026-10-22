//! Registo de esquemas versionados e validacao de registos.
//!
//! O modelo de dados do Khnumn e um contrato, nao uma convencao. Cada registo
//! que entra no sistema e validado contra um esquema JSON Schema 2020-12
//! versionado, e a rejeicao tem de dizer *onde* e *porque*, para que a
//! correccao seja accionavel sem ler o codigo.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;

use crate::error::{Erro, ErroEsquema, Resultado};

/// Os esquemas embutidos no binario.
///
/// O contrato tem de viajar com o codigo: um binario que precisa de um
/// directorio de esquemas ao lado e um binario que falha de formas
/// diferentes conforme quem o instalou. Os ficheiros em `schemas/` sao a
/// fonte, e `include_str!` garante que o binario e o repositorio nao
/// podem divergir sem que a compilacao falhe.
pub const ESQUEMAS_EMBUTIDOS: &[(&str, &str)] = &[
    (
        "activo-v1.schema.json",
        include_str!("../../../schemas/activo-v1.schema.json"),
    ),
    (
        "controlo-v1.schema.json",
        include_str!("../../../schemas/controlo-v1.schema.json"),
    ),
    (
        "projecto-v1.schema.json",
        include_str!("../../../schemas/projecto-v1.schema.json"),
    ),
    (
        "produto-v1.schema.json",
        include_str!("../../../schemas/produto-v1.schema.json"),
    ),
];

/// URI base dos esquemas do Khnumn.
///
/// Os esquemas referenciam-se uns aos outros por URI relativa, e e este
/// prefixo que resolve as referencias entre o activo e o ponto de controlo.
pub const URI_BASE: &str = "https://khnumn.org/esquemas/";

/// Conjunto de esquemas carregados de um directorio.
///
/// Os esquemas sao carregados uma vez e reutilizados: a validacao e uma
/// operacao quente, e o carregamento do esquema em cada chamada custaria
/// mais do que a propria validacao.
pub struct RegistoEsquemas {
    directoria: Option<PathBuf>,
    registo: referencing::Registry<'static>,
    validadores: HashMap<String, jsonschema::Validator>,
}

impl RegistoEsquemas {
    /// Carrega os esquemas embutidos no binario.
    pub fn embutido() -> Resultado<Self> {
        let mut validadores = HashMap::new();
        let esquemas: Vec<(String, String)> = ESQUEMAS_EMBUTIDOS
            .iter()
            .map(|(nome, texto)| ((*nome).to_string(), (*texto).to_string()))
            .collect();
        let registo = construir_registo(&esquemas)?;
        for (nome, texto) in &esquemas {
            validadores.insert(nome.clone(), compilar(nome, texto, &registo)?);
        }
        Ok(RegistoEsquemas {
            directoria: None,
            registo,
            validadores,
        })
    }

    /// Carrega todos os ficheiros `*.schema.json` de uma directoria.
    ///
    /// Um esquema mal formado e um erro de arranque, e nao um aviso: um
    /// esquema que nao carrega significa que a validacao nao esta a acontecer.
    pub fn abrir(directoria: &Path) -> Resultado<Self> {
        let mut encontrados: Vec<(String, String)> = Vec::new();
        let mut validadores = HashMap::new();

        if !directoria.exists() {
            return Err(Erro::Config(format!(
                "directoria de esquemas inexistente: {}",
                directoria.display()
            )));
        }

        let entradas = fs::read_dir(directoria).map_err(|e| Erro::io_ficheiro(directoria, e))?;
        for entrada in entradas {
            let entrada = entrada.map_err(|e| Erro::io_ficheiro(directoria, e))?;
            let caminho = entrada.path();
            let nome = match caminho.file_name().and_then(|n| n.to_str()) {
                Some(n) if n.ends_with(".schema.json") => n.to_string(),
                _ => continue,
            };

            let texto = fs::read_to_string(&caminho).map_err(|e| Erro::io_ficheiro(&caminho, e))?;
            encontrados.push((nome.clone(), texto.clone()));
        }

        if encontrados.is_empty() {
            return Err(Erro::Config(format!(
                "nenhum esquema encontrado em {}",
                directoria.display()
            )));
        }

        let registo = construir_registo(&encontrados)?;
        for (nome, texto) in &encontrados {
            validadores.insert(nome.clone(), compilar(nome, texto, &registo)?);
        }

        Ok(RegistoEsquemas {
            directoria: Some(directoria.to_path_buf()),
            registo,
            validadores,
        })
    }

    /// Devolve a directoria de onde os esquemas foram carregados, quando
    /// vieram do disco.
    pub fn directoria(&self) -> Option<&Path> {
        self.directoria.as_deref()
    }

    /// Nomes dos esquemas disponiveis.
    pub fn nomes(&self) -> Vec<&str> {
        let mut nomes: Vec<&str> = self.validadores.keys().map(|s| s.as_str()).collect();
        nomes.sort_unstable();
        nomes
    }

    /// Indica se um esquema esta registado pelo seu URI.
    pub fn contem(&self, uri: &str) -> bool {
        self.registo.contains_resource(uri)
    }

    /// Valida um registo contra um esquema.
    ///
    /// Devolve todos os erros encontrados, e nao apenas o primeiro: quem
    /// corrige um registo desconhecido quantas vezes precisa de errar para
    /// os corrigir todos.
    pub fn validar(&self, esquema: &str, instancia: &Value) -> Resultado<Vec<ErroEsquema>> {
        let validador = self.validadores.get(esquema).ok_or_else(|| {
            Erro::Config(format!(
                "esquema desconhecido '{esquema}'; disponiveis: {:?}",
                self.nomes()
            ))
        })?;

        let erros: Vec<ErroEsquema> = validador
            .iter_errors(instancia)
            .map(|e| ErroEsquema {
                caminho: format!("{}", e.instance_path()),
                esquema: format!("{}", e.schema_path()),
                mensagem: e.to_string(),
            })
            .collect();

        if erros.is_empty() {
            Ok(Vec::new())
        } else {
            Err(Erro::Esquema {
                esquema: esquema.to_string(),
                erros,
            })
        }
    }

    /// Valida e converte o erro em resultado, para uso directo.
    pub fn validar_ou_erro(&self, esquema: &str, instancia: &Value) -> Resultado<()> {
        match self.validar(esquema, instancia) {
            Ok(_) => Ok(()),
            Err(Erro::Esquema { esquema, erros }) => Err(Erro::Esquema { esquema, erros }),
            Err(outro) => Err(outro),
        }
    }
}

/// Compila um esquema JSON.
///
/// O registo de recursos permite que um esquema referencie outro por URI
/// relativa, sem que a validacao tente ir a rede. Uma validacao que depende
/// da rede e uma validacao que falha por motivos que nao tem com o
/// registo validado.
fn compilar(
    nome: &str,
    texto: &str,
    registo: &referencing::Registry<'static>,
) -> Resultado<jsonschema::Validator> {
    let esquema: Value =
        serde_json::from_str(texto).map_err(|e| Erro::json(format!("esquema {nome}"), e))?;
    let opcoes = jsonschema::draft202012::options().with_registry(registo);
    opcoes
        .build(&esquema)
        .map_err(|e| Erro::Config(format!("esquema invalido {nome}: {e}")))
}

/// Constroi o registo de recursos com todos os esquemas.
///
/// Os esquemas sao registados pelo seu URI, o que permite que as referencias
/// relativas entre eles resolvam sem acesso a disco ou a rede.
fn construir_registo(esquemas: &[(String, String)]) -> Resultado<referencing::Registry<'static>> {
    let mut registo = referencing::Registry::new();
    for (nome, texto) in esquemas {
        let esquema: Value =
            serde_json::from_str(texto).map_err(|e| Erro::json(format!("esquema {nome}"), e))?;
        let recurso = referencing::Resource::from_contents(esquema);
        registo = registo
            .add(format!("{URI_BASE}{nome}"), recurso)
            .map_err(|e| Erro::Config(format!("esquema {nome} invalido: {e}")))?;
    }
    registo
        .prepare()
        .map_err(|e| Erro::Config(format!("registo de esquemas invalido: {e}")))
}

#[cfg(test)]
mod testes {
    use super::*;
    use serde_json::json;

    fn directoria_temporaria() -> tempfile::TempDir {
        let dir = tempfile::tempdir().unwrap();
        let esquema = json!({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["id", "valor"],
            "properties": {
                "id": { "type": "string", "minLength": 1 },
                "valor": { "type": "number" }
            },
            "additionalProperties": false
        });
        fs::write(
            dir.path().join("exemplo.schema.json"),
            serde_json::to_string_pretty(&esquema).unwrap(),
        )
        .unwrap();
        dir
    }

    #[test]
    fn um_registo_valido_nao_produz_erros() {
        let dir = directoria_temporaria();
        let registo = RegistoEsquemas::abrir(dir.path()).unwrap();
        let erros = registo
            .validar("exemplo.schema.json", &json!({"id": "a", "valor": 1.0}))
            .unwrap();
        assert!(erros.is_empty());
    }

    #[test]
    fn a_rejeicao_diz_o_caminho_e_a_causa() {
        let dir = directoria_temporaria();
        let registo = RegistoEsquemas::abrir(dir.path()).unwrap();
        let erro = registo
            .validar("exemplo.schema.json", &json!({"id": "", "valor": "x"}))
            .unwrap_err();

        let texto = erro.to_string();
        assert!(texto.contains("exemplo.schema.json"), "mensagem: {texto}");
        assert!(texto.contains("/id"), "mensagem: {texto}");
        assert!(texto.contains("/valor"), "mensagem: {texto}");
    }

    #[test]
    fn todos_os_erros_sao_devolvidos() {
        let dir = directoria_temporaria();
        let registo = RegistoEsquemas::abrir(dir.path()).unwrap();
        let erro = registo
            .validar("exemplo.schema.json", &json!({"id": 1, "valor": "x"}))
            .unwrap_err();
        match erro {
            Erro::Esquema { erros, .. } => assert_eq!(erros.len(), 2),
            outro => panic!("erro inesperado: {outro}"),
        }
    }

    #[test]
    fn o_esquema_de_produto_valida_um_produto_completo() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-1",
            "type": "mapa_cobertura",
            "format": "cog",
            "source_uri": "produtos/c.tif",
            "sha256": "a".repeat(64),
            "crs": "EPSG:3763",
            "crs_declaration": "CRS de destino",
            "units": {"horizontal": "m", "vertical": "m"},
            "resolution": {"horizontal": 0.02, "vertical": 0.02, "unit": "m"},
            "data_kind": "estimado",
            "uncertainty": {"estimated": false, "declaration": "a cobertura e uma contagem exacta", "value": null, "unit": null, "method": null},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        let erros = registo.validar("produto-v1.schema.json", &produto).unwrap();
        assert!(erros.is_empty(), "erros: {erros:?}");
    }

    #[test]
    fn o_esquema_de_produto_aceita_crs_nulo_com_declaracao() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-2",
            "type": "mapa_residuos",
            "format": "tiff",
            "source_uri": "produtos/r.tif",
            "sha256": "b".repeat(64),
            "crs": null,
            "crs_declaration": "grelha de camara, sem CRS",
            "units": {"horizontal": "px", "vertical": "px"},
            "resolution": {"horizontal": 1.0, "vertical": 1.0, "unit": "px"},
            "data_kind": "estimado",
            "uncertainty": {"estimated": false, "declaration": "residuo da projecao", "value": null, "unit": null, "method": null},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        let erros = registo.validar("produto-v1.schema.json", &produto).unwrap();
        assert!(erros.is_empty(), "erros: {erros:?}");
    }

    #[test]
    fn o_esquema_de_produto_rejeita_crs_nulo_sem_declaracao() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-3",
            "type": "mapa_residuos",
            "format": "tiff",
            "source_uri": "produtos/r.tif",
            "sha256": "c".repeat(64),
            "crs": null,
            "crs_declaration": null,
            "units": {"horizontal": "px", "vertical": "px"},
            "resolution": {"horizontal": 1.0, "vertical": 1.0, "unit": "px"},
            "data_kind": "estimado",
            "uncertainty": {"estimated": false, "declaration": "residuo da projecao", "value": null, "unit": null, "method": null},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        assert!(registo.validar("produto-v1.schema.json", &produto).is_err());
    }

    #[test]
    fn o_esquema_de_produto_rejeita_incerteza_nao_estimada_sem_declaracao() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-4",
            "type": "mapa_cobertura",
            "format": "cog",
            "source_uri": "produtos/c.tif",
            "sha256": "d".repeat(64),
            "crs": "EPSG:3763",
            "crs_declaration": "CRS de destino",
            "units": {"horizontal": "m", "vertical": "m"},
            "resolution": {"horizontal": 0.02, "vertical": 0.02, "unit": "m"},
            "data_kind": "estimado",
            "uncertainty": {"estimated": false, "declaration": null, "value": null, "unit": null, "method": null},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        assert!(registo.validar("produto-v1.schema.json", &produto).is_err());
    }

    #[test]
    fn o_esquema_de_produto_rejeita_formato_ausente() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-5",
            "type": "poses",
            "source_uri": "produtos/p.csv",
            "sha256": "e".repeat(64),
            "crs": "EPSG:3763",
            "crs_declaration": "CRS de origem",
            "units": {"horizontal": "m", "vertical": "m"},
            "resolution": {"horizontal": 1.0, "vertical": 1.0, "unit": "m"},
            "data_kind": "estimado",
            "uncertainty": {"estimated": false, "declaration": "sem estimativa", "value": null, "unit": null, "method": null},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        assert!(registo.validar("produto-v1.schema.json", &produto).is_err());
    }

    #[test]
    fn o_esquema_de_produto_aceita_um_mapa_com_campo_e_legenda() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-6",
            "type": "mapa_incerteza",
            "format": "cog",
            "source_uri": "produtos/u.tif",
            "sha256": "f".repeat(64),
            "crs": "EPSG:3763",
            "crs_declaration": "CRS de destino",
            "units": {"horizontal": "m", "vertical": "m"},
            "resolution": {"horizontal": 0.02, "vertical": 0.02, "unit": "m"},
            "campo": "incerteza_h",
            "legenda": [{"valor": 0.0, "cor": "000000", "rotulo": "baixa"}, {"valor": 1.0, "cor": "ffffff", "rotulo": "alta"}],
            "data_kind": "inferido_por_modelo",
            "uncertainty": {"estimated": true, "declaration": null, "value": 0.3, "unit": "m", "method": "ensemble"},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        let erros = registo.validar("produto-v1.schema.json", &produto).unwrap();
        assert!(erros.is_empty(), "erros: {erros:?}");
    }

    #[test]
    fn o_esquema_de_produto_rejeita_tipo_desconhecido() {
        let registo = RegistoEsquemas::embutido().unwrap();
        let produto = json!({
            "schema_version": "1.0.0",
            "product_id": "p-7",
            "type": "modelo",
            "format": "json",
            "source_uri": "produtos/m.json",
            "sha256": "7".repeat(64),
            "crs": "EPSG:3763",
            "crs_declaration": "CRS de origem",
            "units": {"horizontal": "m", "vertical": "m"},
            "resolution": {"horizontal": 1.0, "vertical": 1.0, "unit": "m"},
            "data_kind": "estimado",
            "uncertainty": {"estimated": false, "declaration": "sem estimativa", "value": null, "unit": null, "method": null},
            "provenance": {"source_uri": null, "operations": [], "versions": {}}
        });
        assert!(registo.validar("produto-v1.schema.json", &produto).is_err());
    }
}
