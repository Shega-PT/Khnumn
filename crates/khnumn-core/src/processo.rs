//! Execucao de processos externos, com medicao de memoria e orcamento.
//!
//! O ambiente de referencia tem um orcamento de memoria, e esse orcamento so
//! e respeitado se for medido. A medicao feita aqui e do pico de memoria
//! residente do processo filho, lido de `/proc/<pid>/status`.
//!
//! A leitura e amostrada, e por isso o valor observado e um limite inferior
//! do pico real. A resolucao da amostragem esta declarada, e a medicao e
//! sempre acompanhada do metodo, para que dois numeros possam ser comparados.

use std::io::{Read, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::error::{Erro, Resultado};

/// Intervalo entre amostras do pico de memoria.
pub const INTERVALO_AMOSTRAGEM: Duration = Duration::from_millis(50);

/// Folga sobre o orcamento de trabalho, em megabytes.
///
/// O orcamento de 500 MiB e a memoria de trabalho que uma tarefa pode
/// usar sem ser uma excepcao. A folga de 300 MiB e o que uma tarefa pode
/// tocar sem ser interrompida. A distincao importa: um orcamento que
/// interrompe ao primeiro pico transitorio obriga a escolher resolucoes
/// mais conservadoras do que a qualidade exige, e um orcamento sem folga
/// interrompe rotineiramente.
pub const FOLGA_MEMORIA_MB: u64 = 300;

/// Pico admissivel, em megabytes, para um orcamento de trabalho dado.
pub fn pico_admissivel_mb(orcamento_mb: u64) -> u64 {
    orcamento_mb + FOLGA_MEMORIA_MB
}

/// Resultado da execucao de um processo.
#[derive(Debug, Clone)]
pub struct ExecucaoProcesso {
    /// Codigo de saida, quando o processo terminou normalmente.
    pub codigo_saida: Option<i32>,
    /// saida standard.
    pub stdout: String,
    /// saida de erro.
    pub stderr: String,
    /// Pico de memoria residente amostrado, em megabytes.
    pub pico_memoria_mb: Option<u64>,
    /// Verdadeiro quando o processo foi terminado por exceder o orcamento.
    pub excedeu_orcamento: bool,
}

/// Executa um comando com uma entrada, medindo o pico de memoria.
///
/// Quando `limite_memoria_mb` e excedido, o processo e terminado e a
/// execucao devolve um erro com a causa. Um orcamento que nao interrompe o
/// processo e uma anotacao, nao um orcamento.
pub fn executar(
    comando: &Path,
    argumentos: &[&str],
    ambiente: &[(String, String)],
    entrada: &str,
    limite_memoria_mb: Option<u64>,
) -> Resultado<ExecucaoProcesso> {
    let mut cmd = Command::new(comando);
    cmd.args(argumentos)
        .envs(ambiente.iter().cloned())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut filho = cmd.spawn().map_err(|e| Erro::io_ficheiro(comando, e))?;
    let pid = filho.id();

    if let Some(mut stdin) = filho.stdin.take() {
        stdin
            .write_all(entrada.as_bytes())
            .map_err(|e| Erro::io(contexto("escrita na entrada do processo"), e))?;
    }

    let pico = Arc::new(AtomicU64::new(0));
    let excedeu = Arc::new(AtomicBool::new(false));
    let parar = Arc::new(AtomicBool::new(false));

    let monitor = {
        let pico = Arc::clone(&pico);
        let excedeu = Arc::clone(&excedeu);
        let parar = Arc::clone(&parar);
        thread::spawn(move || {
            while !parar.load(Ordering::Relaxed) {
                if let Some(mb) = ler_pico_memoria_mb(pid) {
                    pico.fetch_max(mb, Ordering::Relaxed);
                    if let Some(limite) = limite_memoria_mb {
                        if mb > limite {
                            excedeu.store(true, Ordering::Relaxed);
                            break;
                        }
                    }
                }
                thread::sleep(INTERVALO_AMOSTRAGEM);
            }
        })
    };

    let mut stdout = String::new();
    let mut stderr = String::new();
    if let Some(mut fluxo) = filho.stdout.take() {
        let _ = fluxo.read_to_string(&mut stdout);
    }
    if let Some(mut fluxo) = filho.stderr.take() {
        let _ = fluxo.read_to_string(&mut stderr);
    }

    let status = filho
        .wait()
        .map_err(|e| Erro::io(contexto("espera pelo processo"), e))?;
    parar.store(true, Ordering::Relaxed);
    let _ = monitor.join();

    // Ultima leitura possivel do pico, antes de o processo desaparecer.
    if let Some(mb) = ler_pico_memoria_mb(pid) {
        pico.fetch_max(mb, Ordering::Relaxed);
    }

    let excedeu_orcamento = excedeu.load(Ordering::Relaxed);
    // O contador ja esta em megabytes: `ler_pico_memoria_mb` converte.
    let pico_memoria_mb = pico.load(Ordering::Relaxed);

    if excedeu_orcamento {
        return Err(Erro::Estado(format!(
            "orcamento de memoria excedido: processo {comando:?} ultrapassou {} MiB (pico amostrado: {} MiB)",
            limite_memoria_mb.unwrap_or(0),
            pico_memoria_mb
        )));
    }

    Ok(ExecucaoProcesso {
        codigo_saida: status.code(),
        stdout,
        stderr,
        pico_memoria_mb: Some(pico_memoria_mb),
        excedeu_orcamento,
    })
}

/// Le o pico de memoria residente de um processo, em megabytes.
pub fn ler_pico_memoria_mb(pid: u32) -> Option<u64> {
    let conteudo = std::fs::read_to_string(format!("/proc/{pid}/status")).ok()?;
    for linha in conteudo.lines() {
        if let Some(restante) = linha.strip_prefix("VmHWM:") {
            let quilobytes: u64 = restante
                .trim()
                .trim_end_matches(" kB")
                .trim()
                .parse()
                .ok()?;
            return Some(quilobytes / 1024);
        }
    }
    None
}

/// Le o pico de memoria residente do processo actual, em megabytes.
pub fn pico_memoria_proprio_mb() -> Option<u64> {
    ler_pico_memoria_mb(std::process::id())
}

fn contexto(texto: &str) -> String {
    texto.to_string()
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn o_pico_de_memoria_proprio_e_legivel() {
        let pico = pico_memoria_proprio_mb().expect("VmHWM legivel em /proc/self/status");
        assert!(pico < 4096, "pico inesperado: {pico} MiB");
    }

    #[test]
    fn um_processo_que_sai_bem_devolve_o_codigo_de_saida() {
        let python = caminho_interpretador();
        let resultado = executar(
            &python,
            &["-c", "import sys; sys.stdout.write('ok')"],
            &[],
            "",
            Some(512),
        )
        .unwrap();
        assert_eq!(resultado.codigo_saida, Some(0));
        assert_eq!(resultado.stdout, "ok");
        assert!(resultado.pico_memoria_mb.is_some());
    }

    #[test]
    fn a_entrada_e_encaminhada_para_a_entrada_standard() {
        let python = caminho_interpretador();
        let resultado = executar(
            &python,
            &[
                "-c",
                "import sys; sys.stdout.write(sys.stdin.read().upper())",
            ],
            &[],
            "ola",
            Some(512),
        )
        .unwrap();
        assert_eq!(resultado.stdout, "OLA");
    }

    #[test]
    fn o_pico_admissivel_e_o_orcamento_mais_a_folga() {
        assert_eq!(super::pico_admissivel_mb(500), 800);
        assert_eq!(super::pico_admissivel_mb(1800), 2100);
    }

    #[test]
    fn exceder_o_orcamento_interrompe_o_processo_e_reporta_a_causa() {
        let python = caminho_interpretador();
        let erro = executar(
            &python,
            &["-c", "x = bytearray(200 * 1024 * 1024)"],
            &[],
            "",
            Some(64),
        )
        .unwrap_err();
        assert!(
            erro.to_string().contains("orcamento de memoria excedido"),
            "{erro}"
        );
    }

    fn caminho_interpretador() -> std::path::PathBuf {
        if let Ok(python) = std::env::var("KHNUMN_TEST_PYTHON") {
            return std::path::PathBuf::from(python);
        }
        std::path::PathBuf::from("python3")
    }
}
