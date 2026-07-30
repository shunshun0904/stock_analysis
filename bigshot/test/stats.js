'use strict';
/* AI 同士で回して、ゲームの手触りを数字で見る。node test/stats.js [局数] */

const {api, playGame, smart} = require('./harness');

const N = +(process.argv[2] || 300);
const acc = {
  bidsum: 0, bidn: 0, free: 0, top: 0,
  loans: 0, cash: 0, land: 0, total: 0,
  unowned: 0, parks: 0, doubled: 0, hist: {}
};

for(let g = 0; g < N; g++){
  const paid = [];
  const G = api.createGame(['A','B','C','D'], [{rate:1},{rate:1},{rate:1},{rate:1}]);
  let guard = 0;
  while(G.phase !== 'over'){
    if(++guard > 20000) throw new Error('停止');
    if(G.phase === 'roll'){ api.rollDie(G); continue; }
    if(G.phase === 'auction'){
      const p = api.bidder(G);
      const mv = smart.bid(G, p, api);
      if(mv.loan){ api.takeLoan(G, p); continue; }
      if(mv.pass || !mv.amt){
        const before = api.inCount(G);
        api.applyPass(G, p);
        if(before === 2) paid.push(G.high);
      } else api.applyBid(G, p, mv.amt);
      continue;
    }
    const mv = smart.place(G, api);
    if(!mv) api.endPlacement(G); else api.placeCube(G, mv.k, mv.area);
  }
  paid.forEach(v => { acc.bidsum += v; acc.bidn++; if(v === 0) acc.free++; if(v > acc.top) acc.top = v; });
  G.players.forEach(p => {
    acc.loans += p.loans; acc.cash += p.cash;
    acc.land += api.landScore(G, p.idx); acc.total += api.totalScore(G, p.idx);
  });
  G.areas.forEach((A, i) => {
    if(A.owner === null) acc.unowned++;
    else if(api.AREAS[i].kind === 'park') acc.parks++;
  });
  // 公園効果で倍になった区画の数
  api.AREAS.forEach(d => {
    if(d.kind !== 'lot' || d.park === null) return;
    const o = G.areas[d.id].owner;
    if(o !== null && G.areas[api.PARK_AREA[d.park]].owner === o) acc.doubled++;
  });
  const t = api.finalTable(G);
  const k = t.winner ? t.winner.name : '引分';
  acc.hist[k] = (acc.hist[k] || 0) + 1;
}

const P = N * 4;
const f = (x, d) => (x).toFixed(d === undefined ? 2 : d);
console.log('局数 ' + N + '（AI 4人）');
console.log('');
console.log('落札額     平均 ' + f(acc.bidsum / acc.bidn) + '　最高 ' + acc.top + '　無償 ' + f(100 * acc.free / acc.bidn, 1) + '%');
console.log('借用書     1人あたり ' + f(acc.loans / P) + ' 枚');
console.log('決算       残金 ' + f(acc.cash / P) + '　土地 ' + f(acc.land / P) + '　合計 ' + f(acc.total / P));
console.log('所有者なし 1局あたり ' + f(acc.unowned / N) + ' エリア / 13');
console.log('公園       決着した公園 ' + f(acc.parks / N) + ' / 2');
console.log('×2 成立    1局あたり ' + f(acc.doubled / N) + ' 区画 / 6');
console.log('勝者の席   ' + JSON.stringify(acc.hist));
