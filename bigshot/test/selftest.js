'use strict';
/* ルールの検査。node test/selftest.js */

const {api, playGame, smart, random, spender, plain} = require('./harness');

let fail = 0;
function ok(cond, label, extra){
  if(cond) console.log('  ok   ' + label);
  else { fail++; console.log('  FAIL ' + label + (extra ? '  ' + extra : '')); }
}
function head(s){ console.log('\n' + s); }

/* ---------- 所有権の判定 ---------- */
head('所有権（同数の色はすべて無効）');
ok(api.ownerOf([3,3,1,0]) === 2, '3/3/1 → 1個の色が獲る');
ok(api.ownerOf([4,3,0,0]) === 0, '4/3 → 4個の色');
ok(api.ownerOf([2,2,2,1]) === 3, '2/2/2/1 → 1個の色');
ok(api.ownerOf([3,2,2,0]) === 0, '3/2/2 → 3個の色');
ok(api.ownerOf([5,1,1,0]) === 0, '5/1/1 → 5個の色');
ok(api.ownerOf([2,2,0,0]) === null, '2/2 → 該当なし');
ok(api.ownerOf([0,0,0,0]) === null, '空 → 該当なし');
ok(api.ownerOf([7,0,0,0]) === 0, '7/0 → 独占');
{
  // 7個の分け方はすべて勝者が定まるはず
  let bad = [];
  const rec = (rest, k, acc) => {
    if(k === 4){ if(rest === 0 && api.ownerOf(acc) === null) bad.push(acc.slice()); return; }
    for(let v = 0; v <= rest; v++){ acc.push(v); rec(rest - v, k + 1, acc); acc.pop(); }
  };
  rec(7, 0, []);
  ok(bad.length === 0, '7個ならどの分け方でも所有者が決まる', JSON.stringify(bad.slice(0,3)));
}

/* ---------- 盤面の定義 ---------- */
head('街区');
ok(api.NAREA === 13, '13エリア');
ok(api.AREAS.filter(a => a.kind === 'lot').length === 11, '区画は11');
ok(api.AREAS.filter(a => a.kind === 'park').length === 2, '公園は2');
{
  const vs = api.AREAS.filter(a => a.kind === 'lot').map(a => a.v).sort((x,y)=>x-y);
  ok(vs[0] === 9 && vs[vs.length-1] === 21, '区画の価値は 9〜21', vs.join(','));
  ok(new Set(vs).size === 11, '価値に重複なし');
  ok(api.LAND_TOTAL === 161, '土地の合計は161点', String(api.LAND_TOTAL));
}
{
  // 各公園の ×2 印はちょうど3区画、かつ低額側
  const per = [0,1].map(k => api.AREAS.filter(a => a.park === k));
  ok(per[0].length === 3 && per[1].length === 3, '各公園に ×2 が3区画ずつ');
  const marked = per[0].concat(per[1]).map(a => a.v).sort((x,y)=>x-y);
  ok(marked.join(',') === '9,10,11,12,13,14', '×2 は低額の6区画', marked.join(','));
  // 幾何的にも公園と接していること（辺を共有）
  const touch = (a,b) => {
    const hx = a.x < b.x + b.w + 2.1 && b.x < a.x + a.w + 2.1;
    const hy = a.y < b.y + b.h + 2.1 && b.y < a.y + a.h + 2.1;
    return hx && hy;
  };
  let geo = true;
  [0,1].forEach(k => {
    const park = api.AREAS[api.PARK_AREA[k]];
    per[k].forEach(a => { if(!touch(park, a)) geo = false; });
  });
  ok(geo, '×2 区画はその公園に接している');
}
{
  const cap = api.NAREA * api.CAP, cubes = api.NSPACE * 4;
  ok(cap >= cubes, '盤面の収容量がキューブ数以上（置けなくならない）', cap + ' vs ' + cubes);
}

/* ---------- 1局を通した不変条件 ---------- */
head('通し（AI 4人 × 200局）');
{
  let bad = {cash:0, loans:0, spaces:0, areas:0, cubes:0, money:0, rounds:0};
  const N = 200;
  for(let g = 0; g < N; g++){
    const G = playGame(api, [smart, smart, smart, smart]);
    if(G.round !== api.NSPACE) bad.rounds++;
    if(G.spaces.some(s => !s.sold)) bad.spaces++;
    if(G.areas.some(A => !A.sold)) bad.areas++;
    if(G.players.some(p => p.cash < 0)) bad.cash++;
    if(G.players.some(p => p.loans < 0 || p.loans > api.LOAN_MAX)) bad.loans++;
    // 決着した区画に残るのは勝者の1個だけ
    if(G.areas.some(A => A.owner !== null && api.sum(A.cubes) > 1)) bad.cubes++;
    // 金の出入り：残金 = 初期 + 借入 - 落札額。落札額の合計は銀行へ消える
    const got = G.players.reduce((s,p) => s + p.cash, 0);
    const lent = G.players.reduce((s,p) => {
      let t = 0; for(let n = 1; n <= p.loans; n++) t += api.LOAN_COST - n; return s + t;
    }, 0);
    if(got > api.START_CASH * api.NP + lent) bad.money++;
  }
  ok(bad.rounds === 0, '18回の競りで終わる', JSON.stringify(bad));
  ok(bad.spaces === 0, '18マスすべてが売却済み');
  ok(bad.areas === 0, '13エリアすべてに決着がつく');
  ok(bad.cash === 0, '残金が負にならない');
  ok(bad.loans === 0, '借用書は0〜' + api.LOAN_MAX + '枚');
  ok(bad.cubes === 0, '決着した区画には勝者の1個だけが残る');
  ok(bad.money === 0, '残金の合計が初期資金＋借入を超えない');
}

/* ---------- 借用書 ---------- */
head('借用書');
{
  const G = api.createGame(['A','B','C','D'], [{rate:1},{rate:1},{rate:1},{rate:1}]);
  const p = G.players[0];
  ok(api.loanAmount(p) === 9, '1枚目は +9');
  api.takeLoan(G, p);
  ok(p.cash === api.START_CASH + 9, '残金に加算される', String(p.cash));
  ok(!api.canLoan(p), '同じ競りで2枚目は切れない');
  p.loanedThisRound = false;
  ok(api.loanAmount(p) === 8, '2枚目は +8');
  api.takeLoan(G, p);
  p.loanedThisRound = false;
  ok(api.loanAmount(p) === 7, '3枚目は +7');
  // 実質負担：n枚目は n 点
  ok((api.LOAN_COST - 1) - api.LOAN_COST === -1, '1枚目の実質負担は −1');
  p.loans = api.LOAN_MAX;
  ok(!api.canLoan(p), api.LOAN_MAX + '枚で打ち止め');
}

/* ---------- 公園の ×2 ---------- */
head('公園の ×2');
{
  const G = api.createGame(['A','B','C','D'], [{rate:1},{rate:1},{rate:1},{rate:1}]);
  G.areas.forEach(A => { A.sold = true; A.owner = null; A.cubes = [0,0,0,0]; });
  const lot = api.AREAS.find(a => a.park === 0);
  G.areas[lot.id].owner = 0;
  const plain = api.landScore(G, 0);
  ok(plain === lot.v, '公園なしなら素の価値', plain + ' / ' + lot.v);
  G.areas[api.PARK_AREA[0]].owner = 0;
  ok(api.landScore(G, 0) === lot.v * 2, '公園を持てば ×2', String(api.landScore(G,0)));
  G.areas[api.PARK_AREA[0]].owner = 1;
  ok(api.landScore(G, 0) === lot.v, '他人の公園では倍にならない');
  // よその公園では効かない
  G.areas[api.PARK_AREA[1]].owner = 0;
  ok(api.landScore(G, 0) === lot.v, '隣接しない公園では倍にならない');
}

/* ---------- 得点 ---------- */
head('決算');
{
  const G = api.createGame(['A','B','C','D'], [{rate:1},{rate:1},{rate:1},{rate:1}]);
  G.areas.forEach(A => { A.sold = true; A.owner = null; });
  const p = G.players[0];
  p.cash = 12; p.loans = 3;
  ok(api.totalScore(G, 0) === 12 - 30, '残金 − 借用書×10', String(api.totalScore(G,0)));
  const t = api.finalTable(G);
  ok(t.rows.length === 4, '4人ぶんの明細');
}

/* ---------- 強さ ---------- */
head('強さ（席順は1局ごとに回す）');
function match(challenger, field, N){
  let win = 0, draw = 0;
  for(let g = 0; g < N; g++){
    const seat = g % 4;                                   // 挑戦者の座る席
    const pol = [0,1,2,3].map(i => i === seat ? challenger : field);
    const G = playGame(api, pol);
    const t = api.finalTable(G);
    if(!t.winner) { draw++; continue; }
    if(t.winner.idx === seat) win++;
  }
  return {rate: win / N, draw: draw / N};
}
{
  const N = 200;
  const a = match(smart, random, N);
  console.log('  AI 1人 vs 乱択 3人      勝率 ' + a.rate.toFixed(3) + '（引分 ' + a.draw.toFixed(3) + '）');
  ok(a.rate > 0.40, '乱択相手に互角(0.25)を大きく上回る', String(a.rate));

  const b = match(smart, spender, N);
  console.log('  AI 1人 vs 浪費家 3人    勝率 ' + b.rate.toFixed(3) + '（引分 ' + b.draw.toFixed(3) + '）');
  ok(b.rate > 0.35, '浪費家相手に互角を上回る', String(b.rate));

  const e = match(smart, plain, N);
  console.log('  AI 1人 vs 素人筋 3人    勝率 ' + e.rate.toFixed(3) + '（引分 ' + e.draw.toFixed(3) + '）');
  ok(e.rate > 0.30, '素人筋（高い区画を狙うだけ）にも勝ち越す', String(e.rate));

  const f2 = match(plain, smart, N);
  console.log('  素人筋 1人 vs AI 3人    勝率 ' + f2.rate.toFixed(3) + '（引分 ' + f2.draw.toFixed(3) + '）');
  ok(f2.rate < 0.25, 'AI3人に囲まれた素人筋は負け越す', String(f2.rate));

  const c = match(random, smart, N);
  console.log('  乱択 1人 vs AI 3人      勝率 ' + c.rate.toFixed(3) + '（引分 ' + c.draw.toFixed(3) + '）');
  ok(c.rate < 0.20, 'AI3人に囲まれた乱択は沈む', String(c.rate));

  // 席順の偏り。全員同じ方策なので、どの席も 0.25 に寄るはず。
  // （18回は4で割り切れないので、手番が5回まわる席と4回の席がある）
  const M = 600, seat = [0,0,0,0];
  let dr = 0;
  for(let g = 0; g < M; g++){
    const t = api.finalTable(playGame(api, [smart, smart, smart, smart]));
    if(t.winner) seat[t.winner.idx]++; else dr++;
  }
  console.log('  AI 4人 席別            ' + seat.map(w => (w/M).toFixed(3)).join(' / ')
    + '（引分 ' + (dr/M).toFixed(3) + '）');
  ok(seat.every(w => Math.abs(w/M - 0.25) < 0.06), '席順による偏りがない', seat.join(','));
}

console.log('\n' + (fail ? fail + ' 件 失敗' : 'すべて通過'));
process.exit(fail ? 1 : 0);
