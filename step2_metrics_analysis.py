# 新高値ブレイク法システム - ステップ2: データ読み込み対応版分析

import pandas as pd
import numpy as np
import requests
import time
import json
import warnings
warnings.filterwarnings('ignore')

INPUT_FILE = "step1_results.json"
OUTPUT_FILE = "step2_results.json"
HOLDING_CODES = ['5621', '5527']

def load_step1_results():
    """ステップ1の結果を読み込み"""
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        print(f"✓ ステップ1結果読み込み成功: {INPUT_FILE}")
        print(f"  新高値更新銘柄: {results['summary']['total_new_high']}件")
        print(f"  市場データ: {len(results['market_data'])}件")
        
        return results
    except FileNotFoundError:
        print(f"✗ {INPUT_FILE}が見つかりません")
        print("先にステップ1を実行してください: python step1_stock_scanner.py")
        return None
    except Exception as e:
        print(f"✗ ステップ1結果読み込みエラー: {e}")
        return None

def get_7_metrics(code, headers):
    """7指標を取得（これまでの実装と同じ）"""
    metrics = {
        'new_high_count': 0,
        'volume_ratio': 1.0,
        'sales_growth': 0.0,
        'op_growth': 0.0,
        'roe_avg': 0.0,
        'equity_ratio': 0.0,
        'free_cf': 0.0
    }
    
    try:
        # 出来高急増率（直近5日 vs 過去20日）
        url = f"https://api.jquants.com/v1/prices/daily_quotes"
        params = {'code': code, 'from': '20250901', 'to': '20250926'}
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if 'daily_quotes' in data and data['daily_quotes']:
                df = pd.DataFrame(data['daily_quotes'])
                df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
                if len(df) >= 25:
                    recent_5_avg = df['Volume'].tail(5).mean()
                    past_20_avg = df['Volume'].iloc[-25:-5].mean()
                    if past_20_avg > 0:
                        metrics['volume_ratio'] = recent_5_avg / past_20_avg
        
        # 財務データ取得
        url = f"https://api.jquants.com/v1/fins/statements"
        params = {'code': code}
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if 'statements' in data and data['statements']:
                fin_df = pd.DataFrame(data['statements'])
                annual_data = fin_df[fin_df['TypeOfDocument'].str.contains('Annual|年次', na=False)]
                if len(annual_data) == 0:
                    annual_data = fin_df
                annual_data = annual_data.sort_values('DisclosedDate').tail(3)
                
                # 売上成長率（3年平均）
                try:
                    sales = pd.to_numeric(annual_data['NetSales'], errors='coerce').dropna()
                    if len(sales) >= 2:
                        growth_rates = []
                        for i in range(1, len(sales)):
                            if sales.iloc[i-1] != 0:
                                rate = (sales.iloc[i] - sales.iloc[i-1]) / sales.iloc[i-1] * 100
                                growth_rates.append(rate)
                        if growth_rates:
                            metrics['sales_growth'] = np.mean(growth_rates)
                except:
                    pass
                
                # 営業利益成長率（3年平均）
                try:
                    op_profit = pd.to_numeric(annual_data['OperatingProfit'], errors='coerce').dropna()
                    if len(op_profit) >= 2:
                        growth_rates = []
                        for i in range(1, len(op_profit)):
                            if abs(op_profit.iloc[i-1]) > 0:
                                rate = (op_profit.iloc[i] - op_profit.iloc[i-1]) / abs(op_profit.iloc[i-1]) * 100
                                growth_rates.append(rate)
                        if growth_rates:
                            metrics['op_growth'] = np.mean(growth_rates)
                except:
                    pass
                
                # ROE（3年平均）
                try:
                    profit = pd.to_numeric(annual_data['Profit'], errors='coerce').dropna()
                    equity = pd.to_numeric(annual_data['Equity'], errors='coerce').dropna()
                    
                    roes = []
                    for p, e in zip(profit, equity):
                        if e != 0 and not pd.isna(p) and not pd.isna(e):
                            roe = (p / e) * 100
                            roes.append(roe)
                    
                    if roes:
                        metrics['roe_avg'] = np.mean(roes)
                except:
                    pass
                
                # 自己資本比率（最新）
                try:
                    if len(annual_data) > 0:
                        latest = annual_data.iloc[-1]
                        equity_ratio_raw = pd.to_numeric(latest['EquityToAssetRatio'], errors='coerce')
                        if not pd.isna(equity_ratio_raw):
                            metrics['equity_ratio'] = equity_ratio_raw * 100
                except:
                    pass
                
                # フリーキャッシュフロー（営業利益で代替、億円単位）
                try:
                    if len(annual_data) > 0:
                        latest = annual_data.iloc[-1]
                        op_profit = pd.to_numeric(latest['OperatingProfit'], errors='coerce')
                        if not pd.isna(op_profit):
                            metrics['free_cf'] = op_profit / 1e8
                except:
                    pass
    
    except Exception as e:
        print(f"  データ取得エラー: {e}")
    
    return metrics

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
    balance_penalty = 1.0 if min_score >= 0.1 else min_score / 0.1
    
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

def main():
    """ステップ2: 7指標分析・スコア算出・条件フィルタ"""
    
    # ステップ1結果を読み込み
    step1_results = load_step1_results()
    if step1_results is None:
        return False
    
    headers = {"Authorization": f"Bearer {step1_results['token']}"}
    new_high_stocks = step1_results['new_high_stocks']
    holding_info = step1_results['holding_stock_info']
    market_data = step1_results['market_data']
    
    print(f"\\n=== ステップ2: 7指標分析・正規化・スコア算出 ===")
    
    # 分析対象銘柄リスト作成（新高値更新銘柄 + 保有銘柄）
    target_stocks = []
    
    # 新高値更新銘柄追加
    for stock in new_high_stocks:
        target_stocks.append({
            'code': stock['code'],
            'name': stock['name'],
            'new_high_count': stock['new_high_count'],
            'is_new_high_today': True,
            'is_holding': False
        })
    
    # 保有銘柄追加（重複避ける）
    for holding in holding_info:
        if not any(s['code'] == holding['code'] for s in target_stocks):
            target_stocks.append({
                'code': holding['code'],
                'name': holding['name'],
                'new_high_count': holding['new_high_count'],
                'is_new_high_today': holding['is_new_high_today'],
                'is_holding': True
            })
    
    print(f"分析対象銘柄: {len(target_stocks)}件")
    
    # 各銘柄の7指標を取得
    all_metrics = {}
    
    for i, stock in enumerate(target_stocks):
        code = stock['code']
        name = stock['name']
        print(f"7指標取得中 {i+1}/{len(target_stocks)}: {code} {name}")
        
        metrics = get_7_metrics(code, headers)
        metrics['new_high_count'] = stock['new_high_count']  # 既知の値を使用
        
        all_metrics[code] = metrics
        
        new_high_mark = " ★65週新高値" if stock['is_new_high_today'] else ""
        holding_mark = " (保有)" if stock['is_holding'] else ""
        print(f"  新高値:{metrics['new_high_count']}回, 出来高比率:{metrics['volume_ratio']:.2f}{new_high_mark}{holding_mark}")
        
        time.sleep(0.3)
    
    # DataFrameに変換してMin-Maxスケーリング
    df_metrics = pd.DataFrame(all_metrics).T
    print(f"\\n=== Min-Maxスケーリング ===")
    
    df_scores = df_metrics.copy()
    scaling_info = {}
    
    for column in df_metrics.columns:
        col_min = df_metrics[column].min()
        col_max = df_metrics[column].max()
        
        if col_max - col_min != 0:
            df_scores[column] = (df_metrics[column] - col_min) / (col_max - col_min)
        else:
            df_scores[column] = 0.5
        
        scaling_info[column] = {'min': col_min, 'max': col_max}
        print(f"{column:18s}: Min={col_min:8.1f}, Max={col_max:8.1f}")
    
    print(f"\\n=== 総合スコア計算（面積 × 形状バランス） ===")
    
    # 各銘柄の総合スコア計算
    final_scores = []
    
    for code in df_scores.index:
        scores = df_scores.loc[code].tolist()
        comprehensive, area, shape = calculate_comprehensive_score(scores)
        
        stock_info = next((s for s in target_stocks if s['code'] == code), None)
        
        final_scores.append({
            'code': code,
            'name': stock_info['name'],
            'scores': scores,
            'comprehensive_score': comprehensive,
            'area_score': area,
            'shape_score': shape,
            'is_holding': stock_info['is_holding'],
            'is_new_high_today': stock_info['is_new_high_today']
        })
        
        holding_mark = " (保有)" if stock_info['is_holding'] else ""
        print(f"{stock_info['name']}{holding_mark}:")
        print(f"  総合スコア: {comprehensive:.4f} (面積: {area:.4f} × 形状: {shape:.4f})")
    
    # 総合スコアでソート
    final_scores.sort(key=lambda x: x['comprehensive_score'], reverse=True)
    
    # ===== 条件フィルタ適用 =====
    print(f"\\n=== 時価総額・PER条件フィルタ適用 ===")
    print("条件: 時価総額250億円以下 AND PER10倍以上（保有銘柄は除外対象外）")
    
    qualified_stocks = []
    excluded_stocks = []
    
    for stock in final_scores:
        code = stock['code']
        is_holding = stock['is_holding']
        
        if code in market_data:
            md = market_data[code]
            market_cap = md.get('market_cap')
            per = md.get('per')
            # optional raw fields
            issued_shares = md.get('issued_shares') or md.get('issuedShares') or md.get('issued_share')
            latest_close = md.get('latest_close')
            market_cap_jpy = md.get('market_cap_jpy')
            eps = md.get('eps') or md.get('EarningsPerShare')
            
            # 保有銘柄は条件関係なく含める
            if is_holding or (market_cap <= 250 and per >= 10):
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
                print(f"✓ {stock['name']}: 時価総額{market_cap:.0f}億円, PER{per:.1f}倍 - {status}")
            else:
                # 除外理由
                reasons = []
                if market_cap > 250:
                    reasons.append(f"時価総額{market_cap:.0f}億円>250億円")
                if per < 10:
                    reasons.append(f"PER{per:.1f}倍<10倍")
                
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
        else:
            print(f"⚠ {stock['name']}: 市場データなし")
    
    # 条件適合銘柄を総合スコア順にソート
    qualified_stocks.sort(key=lambda x: x['comprehensive_score'], reverse=True)
    
    # 最終選定
    non_holding_top3 = [s for s in qualified_stocks if not s['is_holding']][:3]
    holding_stocks = [s for s in qualified_stocks if s['is_holding']]
    
    print(f"\\n=== 最終選定結果 ===")
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
        print(f"   時価総額: {stock['market_cap']:.0f}億円, PER: {stock['per']:.1f}倍{new_high_mark}")
        if extra:
            print(f"   ({'; '.join(extra)})")
    
    print(f"\\n保有銘柄評価:")
    for stock in holding_stocks:
        ranking = next(i for i, s in enumerate(qualified_stocks) if s['code'] == stock['code']) + 1
        print(f"{ranking}位. {stock['code']} {stock['name']}")
        print(f"   総合スコア: {stock['comprehensive_score']:.4f}")
        print(f"   時価総額: {stock['market_cap']:.0f}億円, PER: {stock['per']:.1f}倍")
        if 'issued_shares' in stock or 'latest_close' in stock:
            parts = []
            if 'issued_shares' in stock:
                parts.append(f"発行済株式数:{stock['issued_shares']:,}株")
            if 'latest_close' in stock:
                parts.append(f"最新終値:{stock['latest_close']:.0f}円")
            print(f"   ({'; '.join(parts)})")
    
    # 結果をJSONファイルに保存
    results = {
        'analysis_date': step1_results['scan_date'],
        'top3_stocks': non_holding_top3,
        'holding_stocks': holding_stocks,
        'qualified_stocks': qualified_stocks,
        'excluded_stocks': excluded_stocks,
        'metrics_data': all_metrics,
        'scaling_info': scaling_info,
        'token': step1_results['token'],
        'summary': {
            'total_analyzed': len(target_stocks),
            'qualified_count': len(qualified_stocks),
            'excluded_count': len(excluded_stocks)
        }
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\\n=== ステップ2完了 ===")
    print(f"条件適合銘柄: {len(qualified_stocks)}件")
    print(f"除外銘柄: {len(excluded_stocks)}件")
    print(f"結果保存: {OUTPUT_FILE}")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\\n✓ ステップ2正常完了")
        print(f"次ステップ: python step3_chart_creation.py")
    else:
        print(f"\\n✗ ステップ2でエラーが発生")