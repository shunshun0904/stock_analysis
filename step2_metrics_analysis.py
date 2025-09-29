import json
import time
import pandas as pd
import numpy as np


def calculate_shape_balance_score(scores):
    """正七角形に近い形状ほど高スコア"""
    n = 7

    # 各頂点間の距離を計算
    distances = []
    for i in range(n):
        j = (i + 1) % n
        distance = abs(scores[i] - scores[j])
        distances.append(distance)

    # 距離のばらつき（標準偏差）
    std_dev = np.std(distances)
    max_std = 1.0
    shape_balance = max(0, (max_std - std_dev) / max_std)

    # 極端に低い値のペナルティ
    min_score = min(scores)
    balance_penalty = 1.0 if min_score >= 0.1 else (min_score / 0.1 if min_score is not None else 0)

    return shape_balance * balance_penalty


def calculate_comprehensive_score(scores):
    """面積スコア × 形状バランススコア"""
    # 7角形面積計算
    n = 7
    central_angle = 2 * np.pi / n

    vertices = []
    for i in range(n):
        angle = i * central_angle
        x = scores[i] * np.cos(angle)
        y = scores[i] * np.sin(angle)
        vertices.append((x, y))

    area = 0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]

    area_score = abs(area) / 2
    shape_score = calculate_shape_balance_score(scores)
    comprehensive_score = area_score * shape_score

    return comprehensive_score, area_score, shape_score


def load_step1_results(path='step1_results.json'):
    """読み込みヘルパー: ステップ1出力をロードする。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"step1 results not found at {path}")
        return None
    except Exception as e:
        print(f"failed to load step1 results: {e}")
        return None


def get_7_metrics(code, headers=None):
    """ステップ1の出力 (`step1_results.json`) を参照して7指標を返す。

    戻り値は key->数値 の dict。呼び出し側でさらに 'new_high_count' を上書きするため
    ここでは主に market_data に入った値を安全に取り出す。
    """
    try:
        step1 = load_step1_results()
        if not step1:
            return {}

        md = step1.get('market_data', {}).get(code, {}) or {}

        # 指標候補（安全に数値化）
        new_high_count = float(md.get('new_high_count') or md.get('newHighCount') or 0)
        volume_ratio = float(md.get('volume_ratio') or md.get('volumeRatio') or 0)
        roe = md.get('roe')
        roe = float(roe) if roe is not None else 0.0

        per = md.get('per')
        try:
            per_val = float(per) if per is not None else None
        except Exception:
            per_val = None

        # PERは低い方が割安（ここでは逆数を取ることでスコア化）
        per_inv = 1.0 / (per_val + 1) if per_val and per_val > 0 else 0.0

        market_cap = md.get('market_cap') or md.get('marketCap')
        try:
            market_cap_val = float(market_cap) if market_cap is not None else None
        except Exception:
            market_cap_val = None

        # 時価総額も小さい方がスクリーニングに有利と仮定し逆数化
        market_cap_inv = 1.0 / (market_cap_val + 1) if market_cap_val and market_cap_val > 0 else 0.0

        eps = md.get('eps') or md.get('EarningsPerShare') or 0.0
        try:
            eps_val = float(eps)
        except Exception:
            eps_val = 0.0

        volatility = md.get('volatility') or md.get('vol') or 0.0
        try:
            vol_val = float(volatility)
        except Exception:
            vol_val = 0.0

        return {
            'new_high_count': new_high_count,
            'volume_ratio': volume_ratio,
            'roe': roe,
            'per_inv': per_inv,
            'market_cap_inv': market_cap_inv,
            'eps': eps_val,
            'volatility': vol_val,
        }
    except Exception as e:
        print(f"get_7_metrics internal error for {code}: {e}")
        return {}


def main():
    """ステップ2: 7指標分析・スコア算出・条件フィルタ"""

    # ステップ1結果を読み込み
    step1_results = load_step1_results()
    if step1_results is None:
        return False

    headers = {"Authorization": f"Bearer {step1_results.get('token', '')}"}
    new_high_stocks = step1_results.get('new_high_stocks', [])
    holding_info = step1_results.get('holding_stock_info', [])
    market_data = step1_results.get('market_data', {})

    print(f"\n=== ステップ2: 7指標分析・正規化・スコア算出 ===")

    # 分析対象銘柄リスト作成（新高値更新銘柄 + 保有銘柄）
    target_stocks = []

    # 新高値更新銘柄追加
    for stock in new_high_stocks:
        target_stocks.append({
            'code': stock.get('code'),
            'name': stock.get('name', ''),
            'new_high_count': stock.get('new_high_count', 0),
            'is_new_high_today': True,
            'is_holding': False
        })

    # 保有銘柄追加（重複避ける）
    for holding in holding_info:
        if not any(s['code'] == holding.get('code') for s in target_stocks):
            target_stocks.append({
                'code': holding.get('code'),
                'name': holding.get('name', ''),
                'new_high_count': holding.get('new_high_count', 0),
                'is_new_high_today': holding.get('is_new_high_today', False),
                'is_holding': True
            })

    print(f"分析対象銘柄: {len(target_stocks)}件")

    # 各銘柄の7指標を取得
    all_metrics = {}

    for i, stock in enumerate(target_stocks):
        code = stock.get('code')
        name = stock.get('name')
        print(f"7指標取得中 {i+1}/{len(target_stocks)}: {code} {name}")

        try:
            metrics = get_7_metrics(code, headers)
        except Exception as e:
            print(f"get_7_metrics failed for {code}: {e}")
            metrics = {}

        metrics['new_high_count'] = stock.get('new_high_count', 0)  # 既知の値を使用

        all_metrics[code] = metrics

        new_high_mark = " ★65週新高値" if stock.get('is_new_high_today') else ""
        holding_mark = " (保有)" if stock.get('is_holding') else ""
        print(f"  新高値:{metrics.get('new_high_count',0)}回, 出来高比率:{metrics.get('volume_ratio',0):.2f}{new_high_mark}{holding_mark}")

        time.sleep(0.2)

    # DataFrameに変換してMin-Maxスケーリング
    if not all_metrics:
        print("no metrics collected, aborting")
        return False

    df_metrics = pd.DataFrame(all_metrics).T.fillna(0)
    print(f"\n=== Min-Maxスケーリング ===")

    df_scores = df_metrics.copy()
    scaling_info = {}

    for column in df_metrics.columns:
        col_min = df_metrics[column].min()
        col_max = df_metrics[column].max()

        if col_max - col_min != 0:
            df_scores[column] = (df_metrics[column] - col_min) / (col_max - col_min)
        else:
            df_scores[column] = 0.5

        scaling_info[column] = {'min': float(col_min), 'max': float(col_max)}
        try:
            print(f"{column:18s}: Min={col_min:8.1f}, Max={col_max:8.1f}")
        except Exception:
            print(f"{column}: min={col_min}, max={col_max}")

    print(f"\n=== 総合スコア計算（面積 × 形状バランス） ===")

    # 各銘柄の総合スコア計算
    final_scores = []

    for code in df_scores.index:
        scores = df_scores.loc[code].tolist()
        # ensure length 7
        if len(scores) < 7:
            scores = (scores + [0] * 7)[:7]
        comprehensive, area, shape = calculate_comprehensive_score(scores)

        stock_info = next((s for s in target_stocks if s.get('code') == code), None)

        final_scores.append({
            'code': code,
            'name': (stock_info.get('name') if stock_info else ''),
            'scores': scores,
            'comprehensive_score': float(comprehensive),
            'area_score': float(area),
            'shape_score': float(shape),
            'is_holding': (stock_info.get('is_holding') if stock_info else False),
            'is_new_high_today': (stock_info.get('is_new_high_today') if stock_info else False)
        })

        holding_mark = " (保有)" if stock_info and stock_info.get('is_holding') else ""
        print(f"{(stock_info.get('name') if stock_info else code)}{holding_mark}:")
        print(f"  総合スコア: {comprehensive:.4f} (面積: {area:.4f} × 形状: {shape:.4f})")

    # 総合スコアでソート
    final_scores.sort(key=lambda x: x['comprehensive_score'], reverse=True)

    # ===== 条件フィルタ適用 =====
    print(f"\n=== 時価総額・PER条件フィルタ適用 ===")
    print("条件: 時価総額200億円以下 AND PER10倍以上（保有銘柄は除外対象外）")

    qualified_stocks = []
    excluded_stocks = []

    for stock in final_scores:
        code = stock['code']
        is_holding = stock['is_holding']

        md = market_data.get(code, {})
        market_cap = md.get('market_cap')
        per = md.get('per')
        # optional raw fields
        issued_shares = md.get('issued_shares') or md.get('issuedShares') or md.get('issued_share')
        latest_close = md.get('latest_close')
        market_cap_jpy = md.get('market_cap_jpy')
        eps = md.get('eps') or md.get('EarningsPerShare')

        meets_condition = (market_cap is not None and per is not None and market_cap <= 200 and per >= 10)
        if is_holding or meets_condition:
            stock['market_cap'] = market_cap
            stock['per'] = per
            # attach raw fields if available for traceability
            if issued_shares is not None:
                stock['issued_shares'] = issued_shares
            if latest_close is not None:
                stock['latest_close'] = latest_close
            if market_cap_jpy is not None:
                stock['market_cap_jpy'] = market_cap_jpy
            if eps is not None:
                stock['eps'] = eps
            stock['qualified'] = True
            qualified_stocks.append(stock)

            status = "(保有)" if is_holding else "条件クリア"
            try:
                print(f"✓ {stock['name']}: 時価総額{(market_cap if market_cap is not None else 0):.0f}億円, PER{(per if per is not None else 0):.1f}倍 - {status}")
            except Exception:
                print(f"✓ {stock.get('name')}: 時価総額{market_cap}億円, PER{per}倍 - {status}")
        else:
            # 除外理由
            reasons = []
            try:
                if market_cap is not None and market_cap > 200:
                    reasons.append(f"時価総額{market_cap:.0f}億円>200億円")
            except Exception:
                pass
            if per is None or per < 10:
                reasons.append(f"PER{(per if per is not None else 'N/A')}倍<10倍")

            ex_entry = {
                'code': code,
                'name': stock['name'],
                'comprehensive_score': stock['comprehensive_score'],
                'reason': ', '.join(reasons)
            }
            # attach raw fields for excluded too
            if issued_shares is not None:
                ex_entry['issued_shares'] = issued_shares
            if latest_close is not None:
                ex_entry['latest_close'] = latest_close
            excluded_stocks.append(ex_entry)
            print(f"✗ {stock['name']}: {', '.join(reasons)}")

    # 条件適合銘柄を総合スコア順にソート
    qualified_stocks.sort(key=lambda x: x['comprehensive_score'], reverse=True)

    # 最終選定
    non_holding_top3 = [s for s in qualified_stocks if not s['is_holding']][:3]
    holding_stocks = [s for s in qualified_stocks if s['is_holding']]

    print(f"\n=== 最終選定結果 ===")
    print("投資推奨上位3銘柄:")
    for i, stock in enumerate(non_holding_top3):
        new_high_mark = " ★65週新高値" if stock['is_new_high_today'] else ""
        print(f"{i+1}. {stock['code']} {stock['name']}")
        print(f"   総合スコア: {stock['comprehensive_score']:.4f}")
        extra = []
        if 'issued_shares' in stock:
            extra.append(f"発行済株式数:{stock['issued_shares']:,}株")
        if 'latest_close' in stock:
            extra.append(f"最新終値:{stock['latest_close']:.0f}円")
        print(f"   時価総額: {stock.get('market_cap',0):.0f}億円, PER: {stock.get('per',0):.1f}倍{new_high_mark}")
        if extra:
            print(f"   ({'; '.join(extra)})")

    print(f"\n保有銘柄評価:")
    for stock in holding_stocks:
        ranking = next((i for i, s in enumerate(qualified_stocks) if s['code'] == stock['code']), None)
        ranking = (ranking + 1) if ranking is not None else 'N/A'
        print(f"{ranking}位. {stock['code']} {stock['name']}")
        print(f"   総合スコア: {stock['comprehensive_score']:.4f}")
        print(f"   時価総額: {stock.get('market_cap',0):.0f}億円, PER: {stock.get('per',0):.1f}倍")
        if 'issued_shares' in stock or 'latest_close' in stock:
            parts = []
            if 'issued_shares' in stock:
                parts.append(f"発行済株式数:{stock['issued_shares']:,}株")
            if 'latest_close' in stock:
                parts.append(f"最新終値:{stock['latest_close']:.0f}円")
            print(f"   ({'; '.join(parts)})")

    # 結果をJSONファイルに保存
    results = {
        'analysis_date': step1_results.get('scan_date'),
        'top3_stocks': non_holding_top3,
        'holding_stocks': holding_stocks,
        'qualified_stocks': qualified_stocks,
        'excluded_stocks': excluded_stocks,
        'metrics_data': all_metrics,
        'scaling_info': scaling_info,
        'token': step1_results.get('token'),
        'summary': {
            'total_analyzed': len(target_stocks),
            'qualified_count': len(qualified_stocks),
            'excluded_count': len(excluded_stocks)
        }
    }

    out_file = globals().get('OUTPUT_FILE', 'step2_results.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n=== ステップ2完了 ===")
    print(f"条件適合銘柄: {len(qualified_stocks)}件")
    print(f"除外銘柄: {len(excluded_stocks)}件")
    print(f"結果保存: {out_file}")

    return True


if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✓ ステップ2正常完了")
        print(f"次ステップ: python step3_chart_creation.py")
    else:
        print(f"\n✗ ステップ2でエラーが発生")
        # end else: just report failure; previously a duplicated block was appended here which caused IndentationError