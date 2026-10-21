//! Serializacao canonica e hashing.
//!
//! A identidade de um produto, de uma tarefa e de uma cache depende de que a
//! mesma informacao produza sempre a mesma sequencia de bytes. Isso exige uma
//! forma canonica de serializar JSON, e nao a ordem de insercao de um mapa.
//!
//! `serde_json` usa `BTreeMap` para objectos por omissao, o que ja ordena as
//! chaves lexicograficamente, e escreve numeros na forma mais curta que
//! reconstrói o valor. A serializacao de `serde_json::Value` e, por isso,
//! canonica sem configuracao adicional. O que esta modulo faz e fixar essa
//! propriedade em testes, para que uma mudanca de comportamento do `serde_json`
//! nao altere silenciosamente a identidade de nenhum produto.

use std::fs::File;
use std::io::{self, Read};
use std::path::Path;

use serde_json::Value;
use sha2::{Digest, Sha256};

/// Serializa um valor JSON de forma canonica.
pub fn json_canonico(valor: &Value) -> String {
    serde_json::to_string(valor).expect("serializacao de Value nunca falha")
}

/// Calcula o SHA-256 de uma sequencia de bytes, em hexadecimal.
pub fn sha256_bytes(dados: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(dados);
    hex(&hasher.finalize())
}

/// Calcula o SHA-256 de um ficheiro, em leitura encadeada.
///
/// O ficheiro nao e carregado em memoria: o limite de RAM do ambiente de
/// referencia aplica-se tambem a esta operacao.
pub fn sha256_ficheiro(caminho: &Path) -> io::Result<String> {
    let mut ficheiro = File::open(caminho)?;
    let mut hasher = Sha256::new();
    let mut bloco = vec![0u8; 128 * 1024];
    loop {
        let lidos = ficheiro.read(&mut bloco)?;
        if lidos == 0 {
            break;
        }
        hasher.update(&bloco[..lidos]);
    }
    Ok(hex(&hasher.finalize()))
}

/// Calcula o hash de um valor JSON, segundo a forma canonica.
pub fn hash_json(valor: &Value) -> String {
    sha256_bytes(json_canonico(valor).as_bytes())
}

/// Codifica bytes em hexadecimal, em minusculas.
pub fn hex(dados: &[u8]) -> String {
    let mut resultado = String::with_capacity(dados.len() * 2);
    for byte in dados {
        resultado.push_str(&format!("{byte:02x}"));
    }
    resultado
}

#[cfg(test)]
mod testes {
    use super::*;
    use serde_json::json;

    #[test]
    fn a_ordem_das_chaves_nao_altera_o_hash() {
        let a = json!({"b": 1, "a": {"z": 2, "y": 3}});
        let b = json!({"a": {"y": 3, "z": 2}, "b": 1});
        assert_eq!(hash_json(&a), hash_json(&b));
    }

    #[test]
    fn valores_diferentes_tem_hashes_diferentes() {
        assert_ne!(hash_json(&json!({"a": 1})), hash_json(&json!({"a": 2})));
    }

    #[test]
    fn o_hash_de_ficheiro_corresponde_ao_hash_dos_bytes() {
        let dir = tempfile::tempdir().unwrap();
        let caminho = dir.path().join("dados.bin");
        let conteudo: Vec<u8> = (0..300_000u32).map(|i| (i % 251) as u8).collect();
        std::fs::write(&caminho, &conteudo).unwrap();

        let por_ficheiro = sha256_ficheiro(&caminho).unwrap();
        let por_bytes = sha256_bytes(&conteudo);
        assert_eq!(por_ficheiro, por_bytes);
    }
}
