# 新高値ブレイク法システム - ステップ3: データ読み込み対応版チャート作成

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import json
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import openai
import glob

INPUT_FILE = "step2_results.json"

# Ensure Japanese font is available for matplotlib (try local fonts, otherwise download Noto Sans JP)
import matplotlib
from matplotlib import font_manager

def ensure_japanese_font():
    """Return selected font name after ensuring a Japanese-capable font is available and set as rcParams."""
    candidates = ['Noto Sans JP', 'NotoSansJP', 'IPAexGothic', 'TakaoPGothic', 'Yu Gothic', 'Meiryo', 'DejaVu Sans']
    try:
        for name in candidates:
            for f in font_manager.fontManager.ttflist:
                if name.lower() in f.name.lower():
                    matplotlib.rcParams['font.family'] = f.name
                    return f.name
    except Exception:
        pass
    # Try to download Noto Sans JP and register it
    try:
        url = "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP-Regular.otf"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            tmp_path = os.path.join('/tmp', 'NotoSansJP-Regular.otf')
            with open(tmp_path, 'wb') as wf:
                wf.write(resp.content)
            try:
                font_manager.fontManager.addfont(tmp_path)
            except Exception:
                # addfont may still work even if it raises; continue
                pass
            try:
                fp = font_manager.FontProperties(fname=tmp_path)
                font_name = fp.get_name()
                matplotlib.rcParams['font.family'] = font_name
                return font_name
            except Exception:
                # fallback to setting known name
                matplotlib.rcParams['font.family'] = 'Noto Sans JP'
                return 'Noto Sans JP'
    except Exception as e:
        print(f"日本語フォントのダウンロード失敗: {e}")

    # Fallback to DejaVu Sans
    matplotlib.rcParams['font.family'] = 'DejaVu Sans'
    return 'DejaVu Sans'

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

def generate_generative_analysis(top3, holdings, chart_data, api_key):
    """LLMによる考察文生成"""
    prompt = (
        "あなたは高度な株式分析レポート作成AIです。以下のJSONデータ（上位3銘柄、主要スコア、形状バランス、株価推移サマリーなど）"
        "とレーダーチャートの内容をもとに、プロのファンドマネージャーが毎日伝えるレベルで精緻な考察と明日以降の戦略方針含む分析レポートを日本語で生成してください。"
        f"\n\n【データJSON】\n{top3}\n\n【保有銘柄JSON】\n{holdings}\n\n【株価チャート要約】\n{chart_data}\n"
    )
    
    # OpenAI APIキー設定
    openai.api_key = api_key
    
    def generate_simple_report(top3, holdings, chart_data):
        # Simple fallback summary in Japanese when LLM is unavailable
        lines = ["自動生成レポート（簡易版）", ""]
        lines.append("上位推奨銘柄:")
        for s in top3[:3]:
            lines.append(f"- {s.get('code','')} {s.get('name','')} (スコア: {s.get('score', 'N/A')})")
        lines.append("")
        lines.append("保有銘柄サマリ:")
        for h in holdings:
            lines.append(f"- {h.get('code','')} {h.get('name','')} (新高値回数: {h.get('new_high_count', 'N/A')})")
        lines.append("")
        lines.append("※OpenAIの利用が制限されているため、簡易レポートを表示しています。")
        return "\n".join(lines)

    try:
        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user", "content":prompt}],
            max_tokens=900,
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        # detect quota error from OpenAI
        try:
            msg = str(e)
            if 'insufficient_quota' in msg or '429' in msg or 'quota' in msg.lower():
                print(f"LLM考察生成エラー（quota）: {e}")
                return generate_simple_report(top3, holdings, chart_data)
        except Exception:
            pass
        print(f"LLM考察生成エラー: {e}")
        return "本日の分析レポートの自動生成に失敗しました。添付チャートをご確認ください。"

def create_and_send_email(subject, body_text, to_email, attachment_paths, token_json_str):
    """Gmail APIでメール送信"""
    try:
        creds = Credentials.from_authorized_user_info(json.loads(token_json_str), scopes=['https://www.googleapis.com/auth/gmail.send'])
        service = build('gmail', 'v1', credentials=creds)

        message = MIMEMultipart()
        message['to'] = to_email
        message['subject'] = subject
        message.attach(MIMEText(body_text, 'plain', 'utf-8'))

        for path in attachment_paths:
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                message.attach(part)
            else:
                print(f"警告: 添付ファイルが見つかりません: {path}")

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw_message}

        sent_message = service.users().messages().send(userId='me', body=body).execute()
        print(f'✓ メール送信成功！ Message ID: {sent_message["id"]}')
        return True
    except Exception as e:
        print(f"✗ メール送信エラー: {e}")
        return False

def create_radar_chart(stocks_data, chart_title, filename):
    """レーダーチャート作成（統一指標順序）"""
    # 日本語フォント設定
    selected_font = ensure_japanese_font()
    # Ensure rcParams uses the selected font
    try:
        matplotlib.rcParams['font.family'] = selected_font
        matplotlib.rcParams['font.sans-serif'] = [selected_font]
        matplotlib.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass
    
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
                selected_font = ensure_japanese_font()
                try:
                    matplotlib.rcParams['font.family'] = selected_font
                    matplotlib.rcParams['font.sans-serif'] = [selected_font]
                    matplotlib.rcParams['axes.unicode_minus'] = False
                except Exception:
                    pass
                
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
    """ステップ3: レーダーチャート4枚 + 株価チャート3枚作成 + LLM考察 + メール送信"""
    
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
    
    # ===== LLM考察生成 & メール送信処理 =====
    print(f"\\n【LLM考察生成・メール送信処理】")
    
    # GitHub Secretsから環境変数を取得
    token_secret = os.environ.get('GMAIL_TOKEN')
    to_address = os.environ.get('TO_EMAIL')
    openai_api_key = os.environ.get('OPENAI_API_KEY')

    if token_secret and to_address and openai_api_key:
        # LLMによる考察（本文）生成
        try:
            generative_body = generate_generative_analysis(
                top3=top3_stocks,
                holdings=holding_stocks,
                chart_data=chart_data if chart_data else None,
                api_key=openai_api_key
            )
        except Exception as e:
            # フォールバック（障害時は簡易本文）
            print(f"LLM生成エラー: {e}")
            generative_body = "本日の分析レポートの自動生成に失敗しました。添付チャートをご確認ください。"

        # 既存の件名＋添付を維持し、本文だけLLM生成に差し替え
        subject = f"日次新高値ブレイク法分析レポート ({datetime.now().strftime('%Y-%m-%d')})"
        attachments = glob.glob('*.png')

        print(f"{len(attachments)}個のファイルを添付して、{to_address}にメールを送信します...")
        create_and_send_email(subject, generative_body, to_address, attachments, token_secret)
    else:
        print("\\nメール送信をスキップ: GitHub Secrets (GMAIL_TOKEN, TO_EMAIL, OPENAI_API_KEY)が設定されていません。")

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
    
    print(f"\\n🎉 新高値ブレイク法による銘柄選定・チャート作成・LLM考察・メール送信完了！")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\\n✓ ステップ3正常完了")
        print(f"全ての処理が完了しました。生成されたチャートとメール送信を確認してください。")
    else:
        print(f"\\n✗ ステップ3でエラーが発生")
