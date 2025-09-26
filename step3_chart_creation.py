# 新高値ブレイク法システム - ステップ3: データ読み込み対応版チャート作成

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import json

INPUT_FILE = "step2_results.json"

# 統一指標配置順序（全レーダーチャートで統一）
METRICS_ORDER = [
    "新高値更新回数", "出来高急増率", "売上成長率（3年平均）",
    "営業利益成長率（3年平均）", "ROE（3年平均）", 
    "自己資本比率", "フリーキャッシュフロー"
]

def load_step2_results():
    """ステップ2の結果を読み込み"""
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        print(f"✓ ステップ2結果読み込み成功: {INPUT_FILE}")
        print(f"  投資推奨上位3銘柄: {len(results['top3_stocks'])}件")
        print(f"  保有銘柄: {len(results['holding_stocks'])}件")
        
        return results
    except FileNotFoundError:
        print(f"✗ {INPUT_FILE}が見つかりません")
        print("先にステップ2を実行してください: python step2_metrics_analysis.py")
        return None
    except Exception as e:
        print(f"✗ ステップ2結果読み込みエラー: {e}")
        return None

def create_radar_chart(stocks_data, chart_title, filename):
    """レーダーチャート作成（統一指標順序）"""
    
    # 日本語フォント設定（環境に応じて調整）
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    # レーダーチャート設定
    fig, ax = plt.subplots(figsize=(12, 12), subplot_kw=dict(projection='polar'))
    
    # 角度設定（7角形）
    angles = [i * 2 * np.pi / 7 for i in range(7)]
    angles += angles[:1]  # 閉じるために最初の角度を追加
    
    colors = ['red', 'blue', 'green']
    alphas = [0.3, 0.3, 0.3]
    linewidths = [2.5, 2.0, 2.0]
    
    for i, stock in enumerate(stocks_data):
        if i < len(colors):  # 色数制限対策
            values = stock['scores'] + [stock['scores'][0]]  # 閉じる
            
            ax.plot(angles, values, 'o-', linewidth=linewidths[i], 
                    color=colors[i], label=stock['name'])
            ax.fill(angles, values, color=colors[i], alpha=alphas[i])
    
    # レーダーチャート装飾
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(METRICS_ORDER, fontsize=11, fontweight='bold')
    ax.set_ylim(0, 1)
    ax.set_title(chart_title, fontsize=16, fontweight='bold', pad=30)
    ax.legend(loc='upper right', bbox_to_anchor=(1.4, 1.0), fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # 目盛り設定
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=10)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.show()
    plt.close()
    
    print(f"✓ レーダーチャート作成完了: {filename}")

def create_stock_price_chart(code, stock_name, headers):
    """株価チャート作成（過去2年間日足）"""
    
    # 2年間の期間設定
    end_date = datetime(2025, 9, 26)  # 実運用時は datetime.now()
    start_date = end_date - timedelta(days=730)
    end_date_str = end_date.strftime('%Y%m%d')
    start_date_str = start_date.strftime('%Y%m%d')
    
    print(f"株価データ取得中: {stock_name}({code}) 期間:{start_date_str}～{end_date_str}")
    
    # 株価データ取得
    url = f"https://api.jquants.com/v1/prices/daily_quotes"
    params = {'code': code, 'from': start_date_str, 'to': end_date_str}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'daily_quotes' in data and data['daily_quotes']:
                df = pd.DataFrame(data['daily_quotes'])
                df['Date'] = pd.to_datetime(df['Date'])
                df['High'] = pd.to_numeric(df['High'], errors='coerce')
                df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
                df = df.sort_values('Date')
                
                print(f"  データ取得成功: {len(df)}日分")
                
                # 日本語フォント設定
                plt.rcParams['font.family'] = 'DejaVu Sans'
                
                # 株価チャート作成
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), 
                                             gridspec_kw={'height_ratios': [3, 1]})
                
                # 株価チャート（上部）- 高値を強調
                ax1.plot(df['Date'], df['High'], linewidth=2, color='red', alpha=0.8, label='High', zorder=3)
                ax1.plot(df['Date'], df['Close'], linewidth=1.5, color='blue', alpha=0.7, label='Close')
                ax1.fill_between(df['Date'], df['Low'], df['High'], alpha=0.1, color='gray', label='Daily Range')
                
                ax1.set_title(f"{stock_name}({code}) Stock Price - Past 2 Years", 
                             fontsize=16, fontweight='bold', pad=20)
                ax1.set_ylabel('Price (JPY)', fontsize=14, fontweight='bold')
                ax1.legend(fontsize=12)
                ax1.grid(True, alpha=0.3)
                
                # 新高値ポイントをマーク
                latest_high = df['High'].iloc[-1]
                latest_date = df['Date'].iloc[-1]
                ax1.scatter([latest_date], [latest_high], color='red', s=150, zorder=5, 
                           marker='*', edgecolors='darkred', linewidth=2)
                ax1.annotate(f'65W New High\\n{latest_high:.0f} JPY', 
                           xy=(latest_date, latest_high), xytext=(20, 20),
                           textcoords='offset points', fontsize=12, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.5', facecolor='red', alpha=0.8, edgecolor='darkred'),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='darkred', lw=2))
                
                # 価格統計表示
                price_high = df['High'].max()
                price_low = df['Low'].min()
                price_range = ((price_high - price_low) / price_low * 100)
                
                ax1.text(0.02, 0.98, f'2Y High: {price_high:.0f}\\n2Y Low: {price_low:.0f}\\nRange: {price_range:.1f}%', 
                        transform=ax1.transAxes, fontsize=11, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
                
                # 出来高チャート（下部）
                ax2.bar(df['Date'], df['Volume'], width=0.8, alpha=0.6, color='orange', label='Volume')
                ax2.set_ylabel('Volume', fontsize=14, fontweight='bold')
                ax2.set_xlabel('Date', fontsize=14, fontweight='bold')
                ax2.legend(fontsize=12)
                ax2.grid(True, alpha=0.3)
                
                # 出来高移動平均線
                df['Volume_MA20'] = df['Volume'].rolling(20).mean()
                ax2.plot(df['Date'], df['Volume_MA20'], color='red', linewidth=2, alpha=0.7, label='20MA')
                
                plt.tight_layout()
                filename = f'stock_chart_{code}_{stock_name.replace(" ", "_").replace("（", "_").replace("）", "")}.png'
                plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
                plt.show()
                plt.close()
                
                return True, df
        
        return False, None
    except Exception as e:
        print(f"  株価チャート作成エラー: {e}")
        return False, None

def main():
    """ステップ3: レーダーチャート4枚 + 株価チャート3枚作成"""
    
    # ステップ2結果を読み込み
    step2_results = load_step2_results()
    if step2_results is None:
        return False
    
    headers = {"Authorization": f"Bearer {step2_results.get('token', '')}"}
    top3_stocks = step2_results['top3_stocks']
    holding_stocks = step2_results['holding_stocks']
    
    print(f"\\n=== ステップ3: チャート作成開始 ===")
    
    # ===== レーダーチャート4枚作成 =====
    print(f"\\n【レーダーチャート作成】")
    
    # チャート1: 1位 + 保有2銘柄
    if len(top3_stocks) > 0:
        chart1_stocks = [top3_stocks[0]] + holding_stocks
        create_radar_chart(
            chart1_stocks,
            f"Chart 1: {top3_stocks[0]['name']} (1st) + Holdings Comparison",
            "radar_chart_1_top1_vs_holdings.png"
        )
    
    # チャート2: 2位 + 保有2銘柄  
    if len(top3_stocks) > 1:
        chart2_stocks = [top3_stocks[1]] + holding_stocks
        create_radar_chart(
            chart2_stocks,
            f"Chart 2: {top3_stocks[1]['name']} (2nd) + Holdings Comparison", 
            "radar_chart_2_top2_vs_holdings.png"
        )
    
    # チャート3: 3位 + 保有2銘柄
    if len(top3_stocks) > 2:
        chart3_stocks = [top3_stocks[2]] + holding_stocks
        create_radar_chart(
            chart3_stocks,
            f"Chart 3: {top3_stocks[2]['name']} (3rd) + Holdings Comparison",
            "radar_chart_3_top3_vs_holdings.png"
        )
    
    # チャート4: 上位3銘柄総合比較
    if len(top3_stocks) >= 3:
        create_radar_chart(
            top3_stocks,
            "Chart 4: Top 3 Stocks Overall Comparison (Shape Balance Considered)",
            "radar_chart_4_top3_comparison.png"
        )
    
    print("✓ レーダーチャート4枚作成完了")
    
    # ===== 株価チャート3枚作成 =====
    print(f"\\n【株価チャート作成】")
    
    chart_data = []
    
    for i, stock in enumerate(top3_stocks[:3]):  # 上位3銘柄のみ
        code = stock['code']
        name = stock['name']
        
        print(f"\\n株価チャート作成 {i+1}/3: {name}({code})")
        
        success, price_df = create_stock_price_chart(code, name, headers)
        
        if success:
            chart_data.append({
                'code': code,
                'name': name,
                'data_points': len(price_df),
                'period_high': price_df['High'].max(),
                'period_low': price_df['Low'].min(),
                'latest_price': price_df['Close'].iloc[-1]
            })
            print(f"  ✓ {name}のチャート作成完了")
        else:
            print(f"  ✗ {name}のチャート作成失敗")
        
        time.sleep(0.5)  # API制限対策
    
    print("\\n✓ 株価チャート3枚作成完了")
    
    # ===== 作成結果サマリー =====
    print(f"\\n=== ステップ3完了 ===")
    print("生成ファイル:")
    print("【レーダーチャート】")
    print("  - radar_chart_1_top1_vs_holdings.png")
    print("  - radar_chart_2_top2_vs_holdings.png")
    print("  - radar_chart_3_top3_vs_holdings.png")
    print("  - radar_chart_4_top3_comparison.png")
    
    print("【株価チャート】")
    if chart_data:
        for data in chart_data:
            filename = f"stock_chart_{data['code']}_{data['name'].replace(' ', '_').replace('（', '_').replace('）', '')}.png"
            print(f"  - {filename}")
            print(f"    2年間高値: {data['period_high']:.0f}円, 安値: {data['period_low']:.0f}円")
    
    print(f"\\n【投資推奨上位3銘柄（最終確認）】")
    for i, stock in enumerate(top3_stocks[:3]):
        new_high_mark = " ★65週新高値" if stock.get('is_new_high_today', False) else ""
        print(f"{i+1}. {stock['name']}（{stock['code']})：総合スコア {stock['comprehensive_score']:.4f}{new_high_mark}")
        print(f"   時価総額: {stock.get('market_cap', 0):.0f}億円, PER: {stock.get('per', 0):.1f}倍")
    
    print(f"\\n🎉 新高値ブレイク法による銘柄選定・チャート作成完了！")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\\n✓ ステップ3正常完了")
        print(f"全ての処理が完了しました。生成されたチャートを確認してください。")
    else:
        print(f"\\n✗ ステップ3でエラーが発生")