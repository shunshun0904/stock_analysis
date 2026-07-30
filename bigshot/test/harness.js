'use strict';
/* index.html のロジック区画をそのまま切り出して Node で動かす。
   ブラウザで動くコードと検査するコードがずれないようにするための仕掛け。 */

const fs = require('fs');
const path = require('path');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function section(startMark, endMark){
  const a = SRC.indexOf(startMark);
  const b = SRC.indexOf(endMark);
  if(a < 0 || b < 0) throw new Error('区画が見つからない: ' + startMark);
  const s = SRC.indexOf('*/', a) + 2;      // 見出しコメントの直後から
  const e = SRC.lastIndexOf('/*', b);      // 締めコメントの直前まで
  return SRC.slice(s, e);
}

const CODE = section('ENGINE_START', 'ENGINE_END') + section('AI_START', 'AI_END');

const EXPORTS = [
  'NP','CAP','NSPACE','START_CASH','LOAN_MAX','LOAN_COST','AREAS','NAREA','PARK_AREA','LAND_TOTAL',
  'sum','shuffle','ownerOf','createGame','say','beginRound','rollDie','startAuction','bidder',
  'inCount','nextBidder','canLoan','loanAmount','takeLoan','applyBid','applyPass','beginPlacement',
  'openAreas','placeCube','resolveArea','endPlacement','finish','landScore','totalScore','finalTable',
  'areaName','snapshot','cloneSnap','ownProb','evalSnap','snapPlace','snapOpen','planPlacement',
  'auctionValue','cpuBid','cpuPlacement'
];

const api = new Function(CODE + '\nreturn {' + EXPORTS.join(',') + '};')();

/* ---- 1局まわす。policy[i] は席 i の指し手 ---- */
function playGame(api, policy){
  const names = ['P0','P1','P2','P3'];
  const personas = [{rate:1},{rate:1},{rate:1},{rate:1}];
  const G = api.createGame(names, personas);
  let guard = 0;
  while(G.phase !== 'over'){
    if(++guard > 20000) throw new Error('進行が止まった');
    if(G.phase === 'roll'){ api.rollDie(G); continue; }
    if(G.phase === 'auction'){
      const p = api.bidder(G);
      const mv = policy[p.idx].bid(G, p, api);
      if(mv.loan){ api.takeLoan(G, p); continue; }
      if(mv.pass || !mv.amt) api.applyPass(G, p); else api.applyBid(G, p, mv.amt);
      continue;
    }
    if(G.phase === 'place'){
      const mv = policy[G.pend.by].place(G, api);
      if(!mv){ api.endPlacement(G); continue; }
      api.placeCube(G, mv.k, mv.area);
      continue;
    }
  }
  return G;
}

/* ---- 方策 ---- */
const smart = {
  bid: (G, p, api) => api.cpuBid(G),
  place: (G, api) => api.cpuPlacement(G)
};
const random = {
  bid: (G, p) => {
    const need = G.high + 1;
    if (need > p.cash || Math.random() < 0.45) return {pass:true};
    return {amt: need};
  },
  place: (G, api) => {
    const open = api.openAreas(G);
    if(!open.length) return null;
    const k = G.pend.done.indexOf(false);
    return {k: k, area: open[Math.floor(Math.random()*open.length)]};
  }
};
// 上限まで無条件に競る「金遣いの荒い」相手
const spender = {
  bid: (G, p) => {
    const need = G.high + 1;
    if(need > p.cash) return {pass:true};
    return Math.random() < 0.75 ? {amt: need} : {pass:true};
  },
  place: random.place
};

// 素人筋。「高い区画に自分の色を集める」だけを考え、競りは4金までで降りる。
// 相手の色をどこへ置くかは考えていない（そこがこのゲームの肝なのだが）。
const plain = {
  bid: (G, p) => {
    const need = G.high + 1;
    return (need > 4 || need > p.cash) ? {pass:true} : {amt: need};
  },
  place: (G, a) => {
    const open = a.openAreas(G);
    if(!open.length) return null;
    const k = G.pend.done.indexOf(false);
    const color = G.pend.cubes[k], me = G.pend.by;
    let best = null;
    open.forEach(id => {
      const d = a.AREAS[id], A = G.areas[id];
      // 自分の色なら価値の高い区画へ、他人の色なら価値の低い区画へ捨てる
      const score = (color === me ? 1 : -1) * (d.kind === 'park' ? 12 : d.v);
      if(!best || score > best.s) best = {s: score, id: id};
    });
    return {k: k, area: best.id};
  }
};

module.exports = {api, playGame, smart, random, spender, plain, CODE};
