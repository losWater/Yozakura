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
    eq: HashMap<String, f64>,
}

static DATA: OnceLock<Option<Data>> = OnceLock::new();

fn data() -> Option<&'static Data> {
    DATA.get_or_init(|| {
        let path = std::env::var("NIGHTINGALE_YOZAKURA").ok()?;
        let c: Config = serde_json::from_str(&std::fs::read_to_string(&path).expect("读取夜桜配置失败"))
            .expect("解析夜桜配置失败");
        let eq = serde_json::from_str(&std::fs::read_to_string(&c.matrix).expect("读取当量矩阵失败"))
            .expect("解析当量矩阵失败");
        assert_eq!(c.signature.len(), c.n);
        assert_eq!(c.frequency.len(), c.n);
        Some(Data { c, eq })
    })
    .as_ref()
}

fn keys(code: u64, p: &默认目标函数参数) -> Vec<char> {
    let mut n = code;
    let mut out = Vec::with_capacity(4);
    while n > 0 {
        out.push(*p.数字转键.get(&(n % p.进制)).unwrap());
        n /= p.进制;
    }
    out
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
    let d = data()?;
    let c = &d.c;
    let codes: Vec<Vec<char>> = rows[..c.n].iter().map(|r| keys(r.全码.原始编码, p)).collect();
    let mut out = 分项::default();

    // 独占码位
    let mut by_code: HashMap<u64, Vec<usize>> = HashMap::new();
    for (i, r) in rows[..c.n].iter().enumerate() {
        by_code.entry(r.全码.原始编码).or_default().push(i);
    }
    for tier in &c.exclusive {
        let mut v = 0usize;
        for &i in &tier.indices {
            let others = &by_code[&rows[i].全码.原始编码];
            if others.iter().any(|&j| j != i && (!tier.effective || j < i) && c.signature[j] != c.signature[i]) {
                v += 1;
            }
        }
        out.exclusive_violations.push(v);
        out.total += tier.weight * v as f64;
    }

    // 三四码负荷与分段当量
    let mut use_: HashMap<char, f64> = HashMap::new();
    let (mut e23, mut e34, mut w) = (0.0, 0.0, 0.0);
    let pair = |a: char, b: char| -> f64 {
        let mut s = String::with_capacity(8);
        s.push(a);
        s.push(b);
        *d.eq.get(&s).unwrap_or(&1.3)
    };
    for (i, k) in codes.iter().enumerate() {
        if k.len() < 4 {
            continue;
        }
        let f = c.frequency[i];
        *use_.entry(k[2]).or_default() += f;
        *use_.entry(k[3]).or_default() += f;
        e23 += f * pair(k[1], k[2]);
        e34 += f * pair(k[2], k[3]);
        w += f;
    }
    if w > 0.0 {
        out.eq23 = e23 / w;
        out.eq34 = e34 / w;
        let mut shares: Vec<(char, f64)> =
            ('a'..='z').map(|k| (k, use_.get(&k).copied().unwrap_or(0.0) / (2.0 * w))).collect();
        for &(k, u) in &shares {
            let t = c.target_share.get(&k).copied().unwrap_or(1.0 / 26.0);
            let excess = (u - t).max(0.0);
            out.overload += excess * excess;
        }
        shares.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        for (&k, &min_rank) in &c.rank_gate {
            // 须排第 min_rank 名或更后：超出第 (min_rank-1) 名份额的部分计罚
            let u = shares.iter().find(|x| x.0 == k).unwrap().1;
            let bar = shares[min_rank - 1].1;
            out.rank_excess += (u - bar).max(0.0);
        }
    }
    out.total += c.overload_weight * out.overload * 1e4
        + c.rank_gate_weight * out.rank_excess * 1e2
        + c.eq23_weight * out.eq23
        + c.eq34_weight * out.eq34;

    for m in &c.mutex {
        let (a, b) = (&codes[m.a], &codes[m.b]);
        if a.len() > m.position && b.len() > m.position && a[m.position] == b[m.position] {
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
