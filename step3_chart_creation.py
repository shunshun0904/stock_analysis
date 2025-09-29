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
import glob

INPUT_FILE = "step2_results.json"

# Enable Japanese font support for matplotlib
import matplotlib
import japanize_matplotlib  # This automatically configures Japanese fonts

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

# Note: LLM generation removed per user request. This script will compose a plain-text
# summary including charts and the numeric metrics used for scoring, and send that via
# Gmail API (or save to a local file when Gmail credentials are not available).

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
    """レーダーチャート作成（統一指標順序・日本語フォント対応）"""
    # レーダーチャート設定
    fig, ax = plt.subplots(figsize=(14, 12), subplot_kw=dict(projection='polar'))

    # 角度設定（7角形）
    angles = [i * 2 * np.pi / 7 for i in range(7)]
    angles += angles[:1]  # 閉じるために最初の角度を追加

    # カラーパレット: 非保有銘柄用と保有銘柄用を分ける
    non_holding_palette = ['#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C7']
    holding_palette = ['#2F4B8F', '#FF8C00']  # 保有銘柄は目立つ別系統カラー
    alphas = 0.25
    linewidth_default = 2.5

    # カウンタを用意して、それぞれのリストで色を割り当てる
    non_holding_idx = 0
    holding_idx = 0

    max_stocks = len(stocks_data)
    for i in range(max_stocks):
        stock = stocks_data[i]
        values = stock['scores'] + [stock['scores'][0]]  # 閉じる

        is_holding = stock.get('is_holding', False)
        if is_holding:
            color = holding_palette[holding_idx % len(holding_palette)]
            holding_idx += 1
            line_style = '--'
            marker_style = 's'
            lw = linewidth_default + 0.5
        else:
            color = non_holding_palette[non_holding_idx % len(non_holding_palette)]
            non_holding_idx += 1
            line_style = '-'
            marker_style = 'o'
            lw = linewidth_default

        ax.plot(angles, values, marker=marker_style, linestyle=line_style,
                linewidth=lw, color=color,
                label=f"{stock.get('name', stock.get('code'))}{' (保有)' if is_holding else ''}")
        ax.fill(angles, values, color=color, alpha=alphas)
    
    # レーダーチャート装飾（japanize_matplotlib が自動でフォント設定）
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(METRICS_ORDER, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 1)
    ax.set_title(chart_title, fontsize=18, fontweight='bold', pad=40)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11)
    ax.grid(True, alpha=0.3)
    
    # 目盛り設定
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=10)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()  # Remove plt.show() to avoid blocking
    
    print(f"✓ レーダーチャート作成完了: {filename}")

def create_stock_price_chart(code, stock_name, headers):
    """株価チャート作成（過去2年間日足）"""
    
    # 2年間の期間設定
    #end_date = datetime(2025, 9, 26)  # 実運用時は datetime.now()
    end_date = datetime.now()
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
                
                # japanize_matplotlib が自動で日本語フォントを設定
                
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
    # 取引所上の銘柄コード->会社名マッピングを取得（あれば表示に使う）
    def fetch_company_names(headers):
        try:
            url = 'https://api.jquants.com/v1/listed/info'
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                info = resp.json().get('info', [])
                df = pd.DataFrame(info)
                if 'Code' in df.columns and 'CompanyName' in df.columns:
                    mapping = dict(zip(df['Code'].astype(str).str.zfill(4), df['CompanyName']))
                    return mapping
        except Exception as e:
            print(f"警告: 上場会社情報取得失敗: {e}")
        return {}

    code_to_name = fetch_company_names(headers)
    top3_stocks = step2_results.get('top3_stocks', [])
    holding_stocks = step2_results.get('holding_stocks', [])

    # Ensure holdings and top3 have resolved display names (prefer exchange mapping)
    def resolve_name_for_stock(s):
        code = str(s.get('code', '')).zfill(4)
        resolved = code_to_name.get(code)
        if resolved:
            s['name'] = resolved
        else:
            # keep existing name if present, otherwise fallback to code
            s['name'] = s.get('name') or code
        return s

    holding_stocks = [resolve_name_for_stock(s) for s in holding_stocks]
    top3_stocks = [resolve_name_for_stock(s) for s in top3_stocks]
    
    print(f"\\n=== ステップ3: チャート作成開始 ===")
    
    # ===== レーダーチャート4枚作成 =====
    print(f"\\n【レーダーチャート作成】")
    
    # 保有銘柄フラグを明示的に設定
    for stock in holding_stocks:
        stock['is_holding'] = True
    for stock in top3_stocks:
        stock['is_holding'] = False

    # チャート1: 1位 + 保有2銘柄
    if len(top3_stocks) > 0:
        chart1_stocks = [top3_stocks[0]] + holding_stocks
        create_radar_chart(
            chart1_stocks,
            f"保有銘柄 vs {top3_stocks[0]['name']} (1位)",
            "radar_chart_1_top1_vs_holdings.png"
        )
    
    # チャート2: 2位 + 保有2銘柄  
    if len(top3_stocks) > 1:
        chart2_stocks = [top3_stocks[1]] + holding_stocks
        create_radar_chart(
            chart2_stocks,
            f"保有銘柄 vs {top3_stocks[1]['name']} (2位)", 
            "radar_chart_2_top2_vs_holdings.png"
        )
    
    # チャート3: 3位 + 保有2銘柄
    if len(top3_stocks) > 2:
        chart3_stocks = [top3_stocks[2]] + holding_stocks
        create_radar_chart(
            chart3_stocks,
            f"保有銘柄 vs {top3_stocks[2]['name']} (3位)",
            "radar_chart_3_top3_vs_holdings.png"
        )
    
    # チャート4: 上位3銘柄総合比較
    if len(top3_stocks) >= 3:
        create_radar_chart(
            top3_stocks,
            "投資推奨上位3銘柄 比較分析（総合スコア順）",
            "radar_chart_4_top3_comparison.png"
        )
    
    print("✓ レーダーチャート4枚作成完了")
    
    # ===== 株価チャート3枚作成 =====
    print(f"\\n【株価チャート作成】")
    
    chart_data = []
    
    for i, stock in enumerate(top3_stocks[:3]):  # 上位3銘柄のみ
        code = str(stock['code']).zfill(4)
        # 優先: J-Quants 上場情報の CompanyName -> step2 の name -> コード
        name = code_to_name.get(code) or stock.get('name') or code
        
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
    
    # ===== メール本文作成（LLMなし） & メール送信/ローカル保存 =====
    print(f"\n【メール本文作成・メール送信/保存】")

    token_secret = os.environ.get('GMAIL_TOKEN')
    to_address = os.environ.get('TO_EMAIL')

    # 件名
    subject = f"日次新高値ブレイク法分析レポート ({datetime.now().strftime('%Y-%m-%d')})"

    # 本文組み立て: 上位3・保有銘柄・チャート要約・指標の数値
    lines = []
    lines.append(subject)
    lines.append("\n=== 投資推奨上位3銘柄 ===\n")
    for i, stock in enumerate(top3_stocks[:3]):
        code = str(stock.get('code','')).zfill(4)
        display_name = code_to_name.get(code) or stock.get('name') or code
        lines.append(f"{i+1}. {code} {display_name}")
        lines.append(f"   総合スコア: {stock.get('comprehensive_score', 0):.4f}")
        lines.append(f"   面積スコア: {stock.get('area_score', 0):.4f}, 形状スコア: {stock.get('shape_score', 0):.4f}")
        lines.append(f"   時価総額(億円): {stock.get('market_cap', 'N/A')}, PER: {stock.get('per', 'N/A')}")
        # raw fields if present
        if 'issued_shares' in stock or 'latest_close' in stock or 'eps' in stock or 'market_cap_jpy' in stock:
            extra = []
            if 'issued_shares' in stock:
                extra.append(f"発行済株式数:{stock['issued_shares']:,}株")
            if 'latest_close' in stock:
                extra.append(f"最新終値:{stock['latest_close']:.0f}円")
            if 'eps' in stock:
                extra.append(f"EPS:{stock['eps']}")
            if 'market_cap_jpy' in stock:
                extra.append(f"時価総額(JPY):{stock['market_cap_jpy']:,}円")
            lines.append("   (" + "; ".join(extra) + ")")
        lines.append("")

    lines.append("\n=== 保有銘柄 ===\n")
    for h in holding_stocks:
        code = str(h.get('code','')).zfill(4)
        display_name = h.get('name') or code_to_name.get(code) or code
        lines.append(f"- {code} {display_name}  総合スコア:{h.get('comprehensive_score',0):.4f}")

    lines.append("\n=== 株価チャート要約 ===\n")
    if chart_data:
        for item in chart_data:
            lines.append(f"- {item['code']} {item['name']}: 最新終値 {item.get('latest_price','N/A')}, データ点数 {item.get('data_points','N/A')}")
    else:
        lines.append("(株価チャートデータはありません)")

    lines.append("\n=== 補足 ===")
    lines.append("このメールにはレーダーチャートと株価チャートのPNGファイルを添付しています。LLMによる文章生成は行っていません。")

    body_text = "\n".join(lines)

    attachments = glob.glob('*.png')

    if token_secret and to_address:
        print(f"{len(attachments)}個のファイルを添付して、{to_address}にメールを送信します...")
        ok = create_and_send_email(subject, body_text, to_address, attachments, token_secret)
        if not ok:
            # 保存して手動送付できるようにローカルに保存
            with open('step3_email_body.txt', 'w', encoding='utf-8') as wf:
                wf.write(body_text)
            print("メール送信に失敗したため、本文を step3_email_body.txt に保存しました。PNGはワークスペースにあります。")
    else:
        # Gmail設定がない場合はローカル保存
        with open('step3_email_body.txt', 'w', encoding='utf-8') as wf:
            wf.write(body_text)
        print("GMAIL_TOKEN または TO_EMAIL が未設定のため、メール送信を行いませんでした。")
        print("本文を step3_email_body.txt に保存しました。PNGファイルを手動で添付して送信してください。")

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
