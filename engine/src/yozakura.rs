//! 夜桜附加目标项（NIGHTINGALE_YOZAKURA 指向 JSON 配置时启用；未设置则为 0，旧语义不变）。
//!
//! 每次计算都从当前编码结果全量重算，不依赖增量缓存：
//! - 独占码位：层级集合内的读音，若全码与任一“键位无关签名”不同的读音同码，记一次违例。
//! - 三四码负荷：全码第 3、4 码按频率合并计数，对目标份额单侧超载求平方和；另对 p 类观察键排名设门禁。
//! - 分段当量：第 2→3 码、第 3→4 码，按频率加权平均（当量矩阵）。
//! - 互斥：指定两个读音的指定码位不得同键（虫／鸟）。
use std::collections::HashMap;
use std::sync::OnceLock;

use crate::objectives::default::默认目标函数参数;
use crate::编码信息;

#[derive(serde::Deserialize)]
struct Tier {
    indices: Vec<usize>,
    weight: f64,
    /// true：仅当有更常用（元素序号更小）且签名不同的读音同码才算违例（有效重码口径）
    #[serde(default)]
    effective: bool,
}

#[derive(serde::Deserialize)]
struct Mutex {
    a: usize,
    b: usize,
    position: usize,
    weight: f64,
}

#[derive(serde::Deserialize)]
struct Config {
    /// 参与统计的读音条目数（元素表前 n 条，排除固定简词占位）
    n: usize,
    /// 每条读音的键位无关签名编号（音节 + 首末根组）
    signature: Vec<u32>,
    frequency: Vec<f64>,
    exclusive: Vec<Tier>,
    /// 26 键目标份额（第 3、4 码合并）
    target_share: HashMap<char, f64>,
    overload_weight: f64,
    /// 排名门禁：键 → 最高允许名次（如 p → 21 表示须排第 21 名或更后）
    rank_gate: HashMap<char, usize>,
    rank_gate_weight: f64,
    eq23_weight: f64,
    eq34_weight: f64,
    mutex: Vec<Mutex>,
    matrix: String,
}

struct Data {
    c: Config,
    /// 当量表按键编号展开：eq[a * radix + b]
    eq: Vec<f64>,
    radix: usize,
    /// 目标份额、排名门禁按键编号
    share: Vec<f64>,
    gate: Vec<(usize, usize)>,
    key_of: Vec<char>,
}

static DATA: OnceLock<Option<Data>> = OnceLock::new();

thread_local! {
    static SCRATCH: std::cell::RefCell<rustc_hash::FxHashMap<u64, (usize, u32, usize)>> =
        std::cell::RefCell::new(rustc_hash::FxHashMap::default());
}

fn data(p: &默认目标函数参数) -> Option<&'static Data> {
    DATA.get_or_init(|| {
        let path = std::env::var("NIGHTINGALE_YOZAKURA").ok()?;
        let c: Config = serde_json::from_str(&std::fs::read_to_string(&path).expect("读取夜桜配置失败"))
            .expect("解析夜桜配置失败");
        let raw: HashMap<String, f64> =
            serde_json::from_str(&std::fs::read_to_string(&c.matrix).expect("读取当量矩阵失败"))
                .expect("解析当量矩阵失败");
        assert_eq!(c.signature.len(), c.n);
        assert_eq!(c.frequency.len(), c.n);
        let radix = p.进制 as usize;
        let mut key_of = vec!['\0'; radix];
        for (&d, &k) in &p.数字转键 {
            key_of[d as usize] = k;
        }
        let mut eq = vec![1.3; radix * radix];
        for a in 0..radix {
            for b in 0..radix {
                let mut s = String::new();
                s.push(key_of[a]);
                s.push(key_of[b]);
                if let Some(v) = raw.get(&s) {
                    eq[a * radix + b] = *v;
                }
            }
        }
        let mut share = vec![0.0; radix];
        for d in 0..radix {
            share[d] = c.target_share.get(&key_of[d]).copied().unwrap_or(1.0 / 26.0);
        }
        let gate = c
            .rank_gate
            .iter()
            .map(|(k, &r)| ((0..radix).find(|&d| key_of[d] == *k).unwrap(), r))
            .collect();
        Some(Data { c, eq, radix, share, gate, key_of })
    })
    .as_ref()
}

#[derive(Default, Debug, Clone)]
pub struct 分项 {
    pub exclusive_violations: Vec<usize>,
    pub overload: f64,
    pub rank_excess: f64,
    pub eq23: f64,
    pub eq34: f64,
    pub mutex_violations: usize,
    pub total: f64,
}

pub fn 计算(rows: &[编码信息], p: &默认目标函数参数) -> Option<分项> {
    let d = data(p)?;
    let c = &d.c;
    let r = d.radix as u64;
    let mut out = 分项::default();

    // 独占码位：每个码记 (最小序号 m1, 其签名 s1, 签名不同于 s1 的最小序号 m2)
    SCRATCH.with(|cell| {
        let mut map = cell.borrow_mut();
        map.clear();
        for i in 0..c.n {
            let code = rows[i].全码.原始编码;
            let si = c.signature[i];
            map.entry(code)
                .and_modify(|e| {
                    if e.2 == usize::MAX && si != e.1 {
                        e.2 = i;
                    }
                })
                .or_insert((i, si, usize::MAX));
        }
        for tier in &c.exclusive {
            let mut v = 0usize;
            for &i in &tier.indices {
                let (m1, s1, m2) = map[&rows[i].全码.原始编码];
                let si = c.signature[i];
                let hit = if si != s1 {
                    // 最小序号者签名不同，且必在 i 之前
                    let _ = m1;
                    true
                } else if tier.effective {
                    m2 < i
                } else {
                    m2 != usize::MAX
                };
                if hit {
                    v += 1;
                }
            }
            out.exclusive_violations.push(v);
            out.total += tier.weight * v as f64;
        }
    });

    // 三四码负荷与分段当量（全码四位：个位为第 1 码）
    let mut use_ = vec![0.0f64; d.radix];
    let (mut e23, mut e34, mut w) = (0.0, 0.0, 0.0);
    for i in 0..c.n {
        let code = rows[i].全码.原始编码;
        if code < r * r * r {
            continue;
        }
        let k2 = ((code / r) % r) as usize;
        let k3 = ((code / (r * r)) % r) as usize;
        let k4 = ((code / (r * r * r)) % r) as usize;
        let f = c.frequency[i];
        use_[k3] += f;
        use_[k4] += f;
        e23 += f * d.eq[k2 * d.radix + k3];
        e34 += f * d.eq[k3 * d.radix + k4];
        w += f;
    }
    if w > 0.0 {
        out.eq23 = e23 / w;
        out.eq34 = e34 / w;
        let mut shares: Vec<(usize, f64)> = (0..d.radix)
            .filter(|&k| d.key_of[k].is_ascii_lowercase())
            .map(|k| (k, use_[k] / (2.0 * w)))
            .collect();
        for &(k, u) in &shares {
            let excess = (u - d.share[k]).max(0.0);
            out.overload += excess * excess;
        }
        if !d.gate.is_empty() {
            shares.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
            for &(k, min_rank) in &d.gate {
                let u = shares.iter().find(|x| x.0 == k).unwrap().1;
                let bar = shares[min_rank - 1].1;
                out.rank_excess += (u - bar).max(0.0);
            }
        }
    }
    out.total += c.overload_weight * out.overload * 1e4
        + c.rank_gate_weight * out.rank_excess * 1e2
        + c.eq23_weight * out.eq23
        + c.eq34_weight * out.eq34;

    for m in &c.mutex {
        let pos = r.pow(m.position as u32);
        let (a, b) = (rows[m.a].全码.原始编码, rows[m.b].全码.原始编码);
        if a >= pos && b >= pos && (a / pos) % r == (b / pos) % r {
            out.mutex_violations += 1;
            out.total += m.weight;
        }
    }
    Some(out)
}

pub fn penalty(rows: &[编码信息], p: &默认目标函数参数) -> f64 {
    计算(rows, p).map_or(0.0, |x| x.total)
}

/// 编码结束时把分项写到 stderr，供外部核对（引擎 metric.json 结构不变）。
pub fn 报告(rows: &[编码信息], p: &默认目标函数参数) {
    if let Some(x) = 计算(rows, p) {
        eprintln!(
            "YOZAKURA exclusive={:?} overload={:.6e} rank_excess={:.6} eq23={:.6} eq34={:.6} mutex={} total={:.6}",
            x.exclusive_violations, x.overload, x.rank_excess, x.eq23, x.eq34, x.mutex_violations, x.total
        );
    }
}
