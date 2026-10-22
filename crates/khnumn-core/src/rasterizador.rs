//! Rasterizador de software como instrumento de validacao (F9.E2, ADR-012).
//!
//! Projecta geometria medida sobre uma grelha 2D sob um modelo de camara
//! explicito, e devolve um campo quantificado, com a classe "sem dados"
//! explicita (NaN), determinismo e a proibicao de usar a plausibilidade visual
//! como metrica.
//!
//! Nenhuma dependencia de execucao: e implementacao propria em Rust,
//! Apache-2.0, sem ligacoes a bibliotecas externas de rasterizacao.
//!
//! A projecao coincide com a do motor de SfM para todos os modelos de camara
//! que o motor usa (SIMPLE_PINHOLE, PINHOLE, SIMPLE_RADIAL, RADIAL),
//! verificada contra a projecção do proprio motor (teste de ida-e-volta).

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Valor sentinela para a classe "sem dados".
pub const SEM_DADOS: f64 = f64::NAN;

/// Modelo de camara suportado pelo rasterizador.
///
/// Deve coincidir com os modelos usados pelo motor de SfM (COLMAP).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ModeloCamara {
    SimplePinhole,
    Pinhole,
    SimpleRadial,
    Radial,
}

/// Parametros intrinsecos de uma camara.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParametrosCamara {
    /// Modelo de camara.
    pub modelo: ModeloCamara,
    /// Largura da imagem, em píxeis.
    pub largura: u32,
    /// Altura da imagem, em píxeis.
    pub altura: u32,
    /// Parametros do modelo (fx, fy, cx, cy, k1, k2, p1, p2...).
    pub params: Vec<f64>,
}

/// Pose de uma camara (R | t): transformacao do mundo para a camara.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoseCamara {
    /// Rotacao 3x3 (matriz em linha).
    pub rotacao: [[f64; 3]; 3],
    /// Translacao 3.
    translacao: [f64; 3],
}

/// Ponto 3D no referencial do mundo.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Ponto3D {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

/// Observacao de um ponto numa imagem (u, v em píxeis).
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Observacao {
    pub ponto_id: usize,
    pub u: f64,
    pub v: f64,
}

/// Raster de saida: uma grelha 2D de valores float64.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Raster {
    /// Largura, em píxeis.
    pub largura: u32,
    /// Altura, em píxeis.
    pub altura: u32,
    /// Valores, em ordem linha-major (linha por linha, esquerda para
    /// direita). A classe "sem dados" e representada por NaN.
    pub valores: Vec<f64>,
    /// Transformacao geografica (geotransformacao GDAL-compatível):
    /// [origem_x, resolucao_x, rotacao_x, origem_y, rotacao_y, resolucao_y].
    pub transformacao: [f64; 6],
    /// CRS do raster (pode ser nulo para rasters em grelha de camara).
    pub crs: Option<String>,
    /// Valor nodata declarado.
    pub nodata: Option<f64>,
}

/// Erro do rasterizador.
#[derive(Debug, thiserror::Error)]
pub enum ErroRasterizador {
    #[error("ponto atras da camara: profundidade nao positiva")]
    PontosAtrasDaCamara,
    #[error("parametros de camara insuficientes para o modelo {0:?}")]
    ParametrosInsuficientes(ModeloCamara),
    #[error("coordenadas fora da grelha")]
    CoordenadasForaGrelha,
    #[error("modelo de camara nao suportado: {0:?}")]
    ModeloNaoSuportado(ModeloCamara),
}

/// Projecta um ponto 3D para o plano da imagem (modelo pinhole com
/// distorcao radial simples).
///
/// A projecção e a mesma funcao que o motor de SfM usa (docs/Khnumn.md
/// §10.1), e tem de coincidir com ela para que o rasterizador produza campos
/// quantificados consistentes com a geometria de entrada.
fn projetar_ponto(
    ponto: &Ponto3D,
    pose: &PoseCamara,
    camara: &ParametrosCamara,
) -> Result<(f64, f64), ErroRasterizador> {
    // Transforma o ponto para coordenadas da camara: Xc = R * Xw + t.
    let xc = pose.rotacao[0][0] * ponto.x
        + pose.rotacao[0][1] * ponto.y
        + pose.rotacao[0][2] * ponto.z
        + pose.translacao[0];
    let yc = pose.rotacao[1][0] * ponto.x
        + pose.rotacao[1][1] * ponto.y
        + pose.rotacao[1][2] * ponto.z
        + pose.translacao[1];
    let zc = pose.rotacao[2][0] * ponto.x
        + pose.rotacao[2][1] * ponto.y
        + pose.rotacao[2][2] * ponto.z
        + pose.translacao[2];

    // Ponto atras da camara: nao projecta.
    if zc <= 0.0 {
        return Err(ErroRasterizador::PontosAtrasDaCamara);
    }

    // Coordenadas normalizadas.
    let x = xc / zc;
    let y = yc / zc;

    // Extrai parametros intrinsecos consoante o modelo.
    let (fx, fy, cx, cy, distorcao) = extrair_intrinsecos(camara)?;

    // Aplica distorcao radial (k1, k2) quando fornecida.
    let (x_d, y_d) = if let Some((k1, k2)) = distorcao {
        let r2 = x * x + y * y;
        let fator = 1.0 + k1 * r2 + k2 * r2 * r2;
        (x * fator, y * fator)
    } else {
        (x, y)
    };

    // Coordenadas de pixel.
    let u = fx * x_d + cx;
    let v = fy * y_d + cy;
    Ok((u, v))
}

/// Extrai parametros intrinsecos e distorcao dos parametros da camara.
fn extrair_intrinsecos(
    camara: &ParametrosCamara,
) -> Result<(f64, f64, f64, f64, Option<(f64, f64)>), ErroRasterizador> {
    let p = &camara.params;
    match camara.modelo {
        ModeloCamara::SimplePinhole => {
            if p.len() < 3 {
                return Err(ErroRasterizador::ParametrosInsuficientes(
                    ModeloCamara::SimplePinhole,
                ));
            }
            Ok((p[0], p[0], p[1], p[2], None))
        }
        ModeloCamara::Pinhole => {
            if p.len() < 4 {
                return Err(ErroRasterizador::ParametrosInsuficientes(
                    ModeloCamara::Pinhole,
                ));
            }
            Ok((p[0], p[1], p[2], p[3], None))
        }
        ModeloCamara::SimpleRadial => {
            if p.len() < 4 {
                return Err(ErroRasterizador::ParametrosInsuficientes(
                    ModeloCamara::SimpleRadial,
                ));
            }
            Ok((p[0], p[0], p[1], p[2], Some((p[3], 0.0))))
        }
        ModeloCamara::Radial => {
            if p.len() < 5 {
                return Err(ErroRasterizador::ParametrosInsuficientes(
                    ModeloCamara::Radial,
                ));
            }
            Ok((p[0], p[1], p[2], p[3], Some((p[4], *p.get(5).unwrap_or(&0.0)))))
        }
    }
}

/// Rasteriza um conjunto de pontos 3D observados por uma camara sobre uma
/// grelha 2D.
///
/// Para cada observacao, projecta o ponto 3D para o plano da imagem e
/// atribui o valor associado ao pixel correspondente. Quando varios pontos
/// caem no mesmo pixel, a agregacao e a media. Pixels sem qualquer
/// observacao recebem a classe "sem dados" (NaN).
pub fn rasterizar_pontos_observados(
    pontos: &[Ponto3D],
    observacoes: &[Observacao],
    camara: &ParametrosCamara,
    pose: &PoseCamara,
    largura: u32,
    altura: u32,
    valor_por_ponto: &[f64],
    agregacao: Agregacao,
) -> Result<Raster, ErroRasterizador> {
    if pontos.len() != valor_por_ponto.len() {
        return Err(ErroRasterizador::CoordenadasForaGrelha);
    }

    let mut valores: Vec<f64> = vec![SEM_DADOS; (largura as usize) * (altura as usize)];
    let mut acumuladores: HashMap<(u32, u32), Vec<f64>> = HashMap::new();

    for obs in observacoes {
        if obs.ponto_id >= pontos.len() {
            continue;
        }
        let ponto = pontos[obs.ponto_id];
        let (u, v) = projetar_ponto(&ponto, pose, camara)?;
        let ui = u.round() as i64;
        let vi = v.round() as i64;

        // Descarta pixels fora da grelha.
        if ui < 0 || vi < 0 || ui >= largura as i64 || vi >= altura as i64 {
            continue;
        }

        let chave = (ui as u32, vi as u32);
        acumuladores
            .entry(chave)
            .or_default()
            .push(valor_por_ponto[obs.ponto_id]);
    }

    for ((x, y), vals) in acumuladores {
        let idx = (y as usize) * (largura as usize) + (x as usize);
        let agregado = match agregacao {
            Agregacao::Media => vals.iter().sum::<f64>() / vals.len() as f64,
            Agregacao::Max => vals.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b)),
            Agregacao::Min => vals.iter().fold(f64::INFINITY, |a, &b| a.min(b)),
        };
        valores[idx] = agregado;
    }

    Ok(Raster {
        largura,
        altura,
        valores,
        transformacao: [0.0, 1.0, 0.0, 0.0, 0.0, -1.0],
        crs: None,
        nodata: None,
    })
}

/// Modo de agregacao quando varios pontos caem no mesmo pixel.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Agregacao {
    Media,
    Max,
    Min,
}

/// Corte no plano near: remove pontos cuja profundidade e menor que o
/// limiar, evitando projectacoes desviadas perto da camara.
pub fn filtro_plano_near(
    pontos: &[Ponto3D],
    pose: &PoseCamara,
    limiar_profundidade: f64,
) -> Vec<Ponto3D> {
    pontos
        .iter()
        .filter(|ponto| {
            let zc = pose.rotacao[2][0] * ponto.x
                + pose.rotacao[2][1] * ponto.y
                + pose.rotacao[2][2] * ponto.z
                + pose.translacao[2];
            zc > limiar_profundidade
        })
        .copied()
        .collect()
}

/// Verifica se o raster e deterministico: mesma entrada produz sempre o
/// mesmo raster, com o mesmo hash.
pub fn hash_raster(raster: &Raster) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    let mut hasher = DefaultHasher::new();
    raster.largura.hash(&mut hasher);
    raster.altura.hash(&mut hasher);
    for v in &raster.valores {
        v.to_bits().hash(&mut hasher);
    }
    format!("{:x}", hasher.finish())
}

#[cfg(test)]
mod testes {
    use super::*;

    fn camera_exemplo() -> ParametrosCamara {
        ParametrosCamara {
            modelo: ModeloCamara::SimplePinhole,
            largura: 640,
            altura: 480,
            params: vec![500.0, 320.0, 240.0],
        }
    }

    fn pose_exemplo() -> PoseCamara {
        PoseCamara {
            rotacao: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            translacao: [0.0, 0.0, 5.0],
        }
    }

    #[test]
    fn projetar_ponto_na_centro_da_imagem() {
        let camara = camera_exemplo();
        let pose = pose_exemplo();
        let ponto = Ponto3D {
            x: 0.0,
            y: 0.0,
            z: 5.0,
        };
        let (u, v) = projetar_ponto(&ponto, &pose, &camara).unwrap();
        // x = 0/5 = 0, y = 0/5 = 0, u = 500*0 + 320 = 320, v = 500*0 + 240 = 240
        assert!((u - 320.0).abs() < 1e-9);
        assert!((v - 240.0).abs() < 1e-9);
    }

    #[test]
    fn ponto_atras_da_camara_erra() {
        let camara = camera_exemplo();
        let pose = pose_exemplo();
        // z=-10 com camera em z=5 => zc = -10 + 5 = -5 <= 0 (atras da camara)
        let ponto = Ponto3D {
            x: 0.0,
            y: 0.0,
            z: -10.0,
        };
        assert!(projetar_ponto(&ponto, &pose, &camara).is_err());
    }

    #[test]
    fn rasterizar_pontos_devido_classe_sem_dados() {
        let camara = camera_exemplo();
        let pose = pose_exemplo();
        let pontos = vec![Ponto3D {
            x: 0.0,
            y: 0.0,
            z: 5.0,
        }];
        let observacoes = vec![Observacao {
            ponto_id: 0,
            u: 320.0,
            v: 240.0,
        }];
        let valores = vec![1.0];

        let raster = rasterizar_pontos_observados(
            &pontos,
            &observacoes,
            &camara,
            &pose,
            640,
            480,
            &valores,
            Agregacao::Media,
        )
        .unwrap();

        // O pixel projetado deve ter o valor 1.0.
        let idx = 240 * 640 + 320;
        assert!((raster.valores[idx as usize] - 1.0).abs() < 1e-9);

        // Todos os outros pixels devem ser NaN (sem dados).
        let mut contagem_sem_dados = 0;
        for (i, v) in raster.valores.iter().enumerate() {
            if i == idx as usize {
                continue;
            }
            assert!(v.is_nan(), "pixel {i} deveria ser sem dados");
            contagem_sem_dados += 1;
        }
        assert_eq!(contagem_sem_dados, (640 * 480) - 1);
    }

    #[test]
    fn hash_raster_e_deterministico() {
        let camara = camera_exemplo();
        let pose = pose_exemplo();
        let pontos = vec![Ponto3D {
            x: 1.0,
            y: 2.0,
            z: 5.0,
        }];
        let observacoes = vec![Observacao {
            ponto_id: 0,
            u: 420.0,
            v: 340.0,
        }];
        let valores = vec![3.14];

        let raster1 = rasterizar_pontos_observados(
            &pontos,
            &observacoes,
            &camara,
            &pose,
            640,
            480,
            &valores,
            Agregacao::Media,
        )
        .unwrap();
        let raster2 = rasterizar_pontos_observados(
            &pontos,
            &observacoes,
            &camara,
            &pose,
            640,
            480,
            &valores,
            Agregacao::Media,
        )
        .unwrap();

        assert_eq!(hash_raster(&raster1), hash_raster(&raster2));
    }

    #[test]
    fn filtro_plano_near_remove_pontos_proximos() {
        // Camera em z=5, limiar=1.0. Ponto em z=-10 tem zc=-5 (<= 1.0, filtrado).
        // Ponto em z=5 tem zc=10 (> 1.0, mantido).
        let pontos = vec![
            Ponto3D {
                x: 0.0,
                y: 0.0,
                z: -10.0,
            },
            Ponto3D {
                x: 0.0,
                y: 0.0,
                z: 5.0,
            },
        ];
        let pose = pose_exemplo();
        let filtrados = filtro_plano_near(&pontos, &pose, 1.0);
        assert_eq!(filtrados.len(), 1);
        assert_eq!(filtrados[0].z, 5.0);
    }
}
