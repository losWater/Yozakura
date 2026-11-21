// 用 chai 的拆分算法，按夜莺现行字根把字拆成字根序列（全字版用）。
// 输入 out/input.json：roots（chai 部件名 → 夜莺根名；笔画写 1–5）、targets（要拆的字）。
// 输出 out/splits_chai.json：字 → 夜莺根名序列；拆不了的字不出现。
// 拆分规则沿用夜莺早期 chai 配置（~/Nightingale/work/v176.yaml 的 analysis）。
// 用法：<bun> run tool/quanzi/chai_split.ts
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {load} from 'js-yaml';
import * as chai from '/Users/ice2447/编码理论极限研究/vendor/hanzi-chai/packages/hanzi-chai/src/index.ts';

const dir = fileURLToPath(new URL('./out/', import.meta.url));
const input = JSON.parse(readFileSync(dir + 'input.json', 'utf8'));
const raw = JSON.parse(readFileSync('/Users/ice2447/编码理论极限研究/experiments/003-chai-inverse/repertoire.raw.json', 'utf8'));
const models = raw.map((m: any) => ({...m, ambiguous: m.ambiguous === 1,
  glyphs: JSON.parse(m.glyphs).map((g: any) => g.type === 'basic_component' ? g :
    ['derived_component', 'identity'].includes(g.type) ? {...g, source: String.fromCodePoint(g.source)} :
    {...g, operandList: g.operandList.map((x: number) => String.fromCodePoint(x))})}));
const old: any = load(readFileSync('/Users/ice2447/Nightingale/work/v176.yaml', 'utf8'));
const mapping: Record<string, string> = {};
for (const k of Object.keys(input.roots)) mapping[k] = 'a';
const config: any = {
  version: '2.3', data: {glyph_sources: ['G']},
  analysis: old.analysis,
  form: {alphabet: 'abcdefghijklmnopqrstuvwxyz', mapping_type: 1, mapping},
  encoder: {max_length: 4, sources: {}, conditions: {}, rules: []},
};
const primitive = new chai.原始字库(models as any);
const glyphResult = primitive.确定({}, [], ['G']);
if (!glyphResult.ok) throw glyphResult.error;
const glyphs = glyphResult.value;
const targets: string[] = input.targets;
const dictionary = primitive.校验词典(targets.map(c => ({词: c, 拼音: ['a1'], 频率: 1})));
const {拼音元素映射} = chai.计算拼音分析与元素映射(dictionary, chai.合并拼写运算());
const {名称映射} = chai.计算全部合法元素与元素映射([...glyphs].map(x => x.字符), chai.合并分类器(config.analysis?.classifier), 拼音元素映射, new Map());
const analysis = chai.获取字形分析结果(config, glyphs, dictionary, 名称映射, primitive);
if (!analysis.ok) throw analysis.error;
const out: Record<string, string[]> = {};
const byChar = new Map<string, any>();
for (const [k, v] of analysis.value.分析结果) byChar.set(typeof k === "string" ? k : (k as any).字符 ?? (k as any).获取名称?.(), v);
let fail = 0;
for (const c of targets) {
  const a = byChar.get(c);
  if (!a || !a.length) { fail++; continue; }
  out[c] = a[0].字根序列.map((r: any) => {
    const n = r.获取名称();
    return input.roots[n] ?? n;
  });
}
writeFileSync(dir + 'splits_chai.json', JSON.stringify(out));
console.log('拆出', Object.keys(out).length, '拆不了', fail);
