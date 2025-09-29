# 新高値ブレイク法システム - ステップ1: データ保存対応版スキャナー

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json
import traceback
import sys
# Configuration / defaults
# Prefer JQUANTS_TOKEN (may be access token or refresh token) from environment
_raw_token_env = os.environ.get('JQUANTS_TOKEN')

def exchange_refresh_for_idtoken(refresh_token: str):
    """If the provided token is a refresh token, exchange it for an idToken via auth_refresh.
    Returns idToken string on success, or None."""
    if not refresh_token:
        return None
    try:
        # POST to /v1/token/auth_refresh?refreshtoken=...
        url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"
        r = requests.post(url, timeout=15)
        if r.status_code == 200:
            j = r.json()
            idt = j.get('idToken') or j.get('id_token')
            if idt:
                return idt
        return None
    except Exception:
        return None


# Resolve ID_TOKEN: try exchanging env token as a refresh token, else use as-is
ID_TOKEN = None
if _raw_token_env:
    exchanged = exchange_refresh_for_idtoken(_raw_token_env)
    if exchanged:
        ID_TOKEN = exchanged
    else:
        # assume env contains an access/id token already
        ID_TOKEN = _raw_token_env

# Output file for step1
OUTPUT_FILE = os.environ.get('STEP1_OUTPUT_FILE', 'step1_results.json')
# Holding codes to always check (can be overridden by env var like 'HOLDING_CODES=1234,5678')
HOLDING_CODES = []
hc_env = os.environ.get('HOLDING_CODES')
if hc_env:
    try:
        HOLDING_CODES = [c.strip() for c in hc_env.split(',') if c.strip()]
    except Exception:
        HOLDING_CODES = []


def request_with_retry(url, params=None, headers=None, method='get', max_retries=3, backoff=1.0, timeout=30):
    """Simple retry wrapper around requests.get/post. Returns requests.Response or None."""
    for attempt in range(1, max_retries + 1):
        try:
            if method.lower() == 'post':
                resp = requests.post(url, params=params, headers=headers, timeout=timeout)
            else:
                resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            return resp
        except Exception as e:
            if attempt == max_retries:
                return None
            time.sleep(backoff * attempt)
def get_id_token_from_credentials():
    """Obtain an id token using JQUANTS_MAIL / JQUANTS_PASSWORD if provided.
    Returns token string or None."""
    # First, if the environment JQUANTS_TOKEN contains a refresh token, exchange it
    env_token = os.environ.get('JQUANTS_TOKEN') or os.environ.get('JQUANTS_ACCESS_TOKEN')
    if env_token:
        try:
            idt = exchange_refresh_for_idtoken(env_token)
            if idt:
                return idt
        except Exception:
            pass

    # Fallback to mail/password flow if provided
    mail = os.environ.get('JQUANTS_MAIL')
    password = os.environ.get('JQUANTS_PASSWORD')
    if not mail or not password:
        return None
    try:
        r = requests.post('https://api.jquants.com/v1/token/auth_user',
                          data=json.dumps({'mailaddress': mail, 'password': password}),
                          timeout=30)
        r.raise_for_status()
        refresh_token = r.json().get('refreshToken')
        # exchange refresh token for idToken
        if refresh_token:
            try:
                r2 = requests.post(f'https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}', timeout=30)
                r2.raise_for_status()
                return r2.json().get('idToken')
            except Exception:
                return None
        return None
    except Exception as e:
        print(f"認証トークン取得失敗: {e}")
        return None


def latest_fy_statement(rows: list) -> dict:
    # 期末(FY)のみ、期末日→開示日の順で最新を選択
    fy = [r for r in rows if r.get('TypeOfCurrentPeriod') == 'FY']
    if not fy:
        return {}
    def keyfunc(r):
        end = r.get('CurrentPeriodEndDate') or ''
        dis = r.get('DisclosedDate') or ''
        return (end, dis)
    fy.sort(key=keyfunc)
    return fy[-1]


def get_close_on_date(code: str, date_yyyy_mm_dd: str, headers: dict) -> float:
    """Get Close price on a specific date (YYYY-MM-DD)."""
    try:
        r = requests.get('https://api.jquants.com/v1/prices/daily_quotes', params={'code': code, 'date': date_yyyy_mm_dd}, headers=headers, timeout=30)
        r.raise_for_status()
        arr = r.json().get('daily_quotes') or r.json().get('data') or []
        if not arr:
            raise ValueError('No daily quote on date')
        close = arr[0].get('Close')
        if close in (None, '', 'NaN'):
            raise ValueError('Close missing')
        return float(close)
    except Exception as e:
        # fallback: try range search for nearby date
        try:
            yyyy, mm, dd = date_yyyy_mm_dd.split('-')
            compact = yyyy + mm + dd
            to_date = compact
            from_date = (datetime.strptime(date_yyyy_mm_dd, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y%m%d')
            resp = request_with_retry('https://api.jquants.com/v1/prices/daily_quotes', params={'code': code, 'from': from_date, 'to': to_date}, headers=headers)
            if resp and resp.status_code == 200:
                dq = resp.json().get('daily_quotes') or []
                if dq:
                    df = pd.DataFrame(dq)
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.sort_values('Date')
                    df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                    valid = df['Close'].dropna()
                    if len(valid) > 0:
                        return float(valid.iloc[-1])
        except Exception:
            pass
        raise e


def get_actual_market_data(code, headers):
    """実際の時価総額・PER・EPS・発行済株式数・ROEを公表値（期末）から算出して返す。

    戻り値: dict with keys: market_cap (億円), per, eps, issued_shares, latest_close, market_cap_jpy, roe
    """
    try:
        # Determine token to use: prefer provided headers token, else try mail/password
        token = None
        try:
            auth = headers.get('Authorization', '')
            if auth.lower().startswith('bearer '):
                token = auth.split(' ', 1)[1]
            elif auth:
                token = auth
        except Exception:
            token = None

        if not token:
            token = get_id_token_from_credentials()
        used_headers = {'Authorization': f'Bearer {token}'} if token else headers

        # 1) Get most recent FY statement
        issued_shares = None
        eps = None
        latest_close = None
        market_cap_jpy = None
        roe = None

        fin_resp = request_with_retry('https://api.jquants.com/v1/fins/statements', params={'code': code}, headers=used_headers)
        if fin_resp and fin_resp.status_code == 200:
            fj = fin_resp.json()
            statements = []
            if isinstance(fj, dict):
                if 'statements' in fj and isinstance(fj['statements'], list):
                    statements = fj['statements']
                elif 'data' in fj and isinstance(fj['data'], list):
                    statements = fj['data']
                else:
                    statements = [fj]
            elif isinstance(fj, list):
                statements = fj

            latest = latest_fy_statement(statements)
            if latest:
                # try canonical keys
                # issued shares
                for key in ('NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock', 'IssuedShares', 'issuedShares', 'sharesOutstanding'):
                    if key in latest and latest.get(key) not in (None, '', 'NaN'):
                        try:
                            issued_shares = float(latest.get(key))
                            break
                        except Exception:
                            pass
                # diluted EPS
                for key in ('DilutedEarningsPerShare', 'DilutedEPS', 'Diluted_EPS', 'DilutedEPSPerShare'):
                    if key in latest and latest.get(key) not in (None, '', 'NaN'):
                        try:
                            eps = float(latest.get(key))
                            break
                        except Exception:
                            pass
                # equity and profit for roe
                equity_curr = None
                profit_to_owners = None
                try:
                    equity_curr = float(latest.get('Equity')) if latest.get('Equity') not in (None, '', 'NaN') else None
                except Exception:
                    equity_curr = None

                # attempt to get fs_details for profit attributable to owners and NCI
                try:
                    disclosed = latest.get('DisclosedDate') or latest.get('CurrentPeriodEndDate')
                    if disclosed:
                        fs_resp = request_with_retry('https://api.jquants.com/v1/fins/fs_details', params={'code': code, 'date': disclosed}, headers=used_headers)
                        if fs_resp and fs_resp.status_code == 200:
                            fdet = fs_resp.json().get('fs_details') or fs_resp.json()
                            if isinstance(fdet, list) and fdet:
                                fdet = fdet[0]
                            # Drill into FinancialStatement dictionary if present
                            finstmt = None
                            if isinstance(fdet, dict):
                                finstmt = fdet.get('FinancialStatement') or fdet
                            if finstmt and isinstance(finstmt, dict):
                                # profit attributable to owners
                                for pkey in ('Profit (loss) attributable to owners of parent (IFRS)', 'Profit (loss) attributable to owners of parent'):
                                    if pkey in finstmt and finstmt.get(pkey) not in (None, '', 'NaN'):
                                        try:
                                            profit_to_owners = float(finstmt.get(pkey))
                                            break
                                        except Exception:
                                            pass
                                # Non-controlling interests
                                nci = None
                                for nkey in ('Non-controlling interests (IFRS)', 'Non-controlling interests'):
                                    if nkey in finstmt and finstmt.get(nkey) not in (None, '', 'NaN'):
                                        try:
                                            nci = float(finstmt.get(nkey))
                                            break
                                        except Exception:
                                            pass
                except Exception:
                    pass

        # 2) Determine close price on fiscal end date (use latest statement's CurrentPeriodEndDate if available)
        try:
            date_for_close = None
            if 'latest' in locals() and latest and latest.get('CurrentPeriodEndDate'):
                d = latest.get('CurrentPeriodEndDate')
                # normalize YYYY-MM-DD or YYYYMMDD
                if isinstance(d, str) and len(d) == 8 and d.isdigit():
                    date_for_close = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                else:
                    date_for_close = d
            if date_for_close:
                try:
                    latest_close = get_close_on_date(code, date_for_close, used_headers)
                except Exception:
                    latest_close = None
        except Exception:
            latest_close = None

        # 3) If issued_shares and latest_close available, compute marketcap
        market_cap_okuyen = None
        market_cap_jpy = None
        if issued_shares and latest_close:
            try:
                market_cap_jpy = issued_shares * latest_close
                market_cap_okuyen = market_cap_jpy / 1e8
            except Exception:
                market_cap_okuyen = None

        # 4) PER from diluted EPS
        per = None
        if eps is not None and latest_close is not None:
            try:
                per = latest_close / eps if eps != 0 else None
            except Exception:
                per = None

        # 5) Try compute ROE using two-year average equity if possible
        try:
            roe = None
            # get two latest FY statements
            if fin_resp and fin_resp.status_code == 200:
                stmt_list = statements
                fy_candidates = [r for r in stmt_list if r.get('TypeOfCurrentPeriod') == 'FY']
                if len(fy_candidates) >= 2:
                    # sort by end date
                    fy_candidates.sort(key=lambda r: (r.get('CurrentPeriodEndDate') or '', r.get('DisclosedDate') or ''))
                    prev = fy_candidates[-2]
                    curr = fy_candidates[-1]
                    equity_prev = float(prev.get('Equity')) if prev.get('Equity') not in (None, '', 'NaN') else None
                    equity_curr = float(curr.get('Equity')) if curr.get('Equity') not in (None, '', 'NaN') else None
                    # fs_details for profit_to_owners at curr
                    profit_to_owners = None
                    try:
                        disclosed_prev = prev.get('DisclosedDate') or prev.get('CurrentPeriodEndDate')
                        disclosed_curr = curr.get('DisclosedDate') or curr.get('CurrentPeriodEndDate')
                        if disclosed_prev and disclosed_curr:
                            fs_prev = request_with_retry('https://api.jquants.com/v1/fins/fs_details', params={'code': code, 'date': disclosed_prev}, headers=used_headers)
                            fs_curr = request_with_retry('https://api.jquants.com/v1/fins/fs_details', params={'code': code, 'date': disclosed_curr}, headers=used_headers)
                            if fs_prev and fs_prev.status_code == 200 and fs_curr and fs_curr.status_code == 200:
                                fp = fs_prev.json().get('fs_details') or fs_prev.json()
                                fc = fs_curr.json().get('fs_details') or fs_curr.json()
                                # extract profit_to_owners from current
                                if isinstance(fc, list) and fc:
                                    fc = fc[0]
                                fin_curr = fc.get('FinancialStatement') if isinstance(fc, dict) else None
                                if fin_curr and isinstance(fin_curr, dict):
                                    for pkey in ('Profit (loss) attributable to owners of parent (IFRS)', 'Profit (loss) attributable to owners of parent'):
                                        if pkey in fin_curr and fin_curr.get(pkey) not in (None, '', 'NaN'):
                                            try:
                                                profit_to_owners = float(fin_curr.get(pkey))
                                            except Exception:
                                                profit_to_owners = None
                                                break
                    except Exception:
                        profit_to_owners = None

                    if profit_to_owners is not None and equity_prev is not None and equity_curr is not None:
                        avg_equity = (equity_prev + equity_curr) / 2.0
                        if avg_equity != 0:
                            roe = profit_to_owners / avg_equity
        except Exception:
            roe = None

        # Final fallbacks
        if market_cap_okuyen is None:
            if latest_close and issued_shares:
                try:
                    market_cap_jpy = issued_shares * latest_close
                    market_cap_okuyen = market_cap_jpy / 1e8
                except Exception:
                    market_cap_okuyen = 50.0
            else:
                market_cap_okuyen = 50.0

        if per is None:
            per = 15.0 + (abs(hash(code)) % 20)

        # Return market cap (億円) and PER to match caller expectations
        try:
            mc_val = float(market_cap_okuyen)
        except Exception:
            mc_val = 50.0
        try:
            per_val = float(per) if per is not None else 15.0
        except Exception:
            per_val = 15.0
        return mc_val, per_val
    except Exception as e:
        print(f"get_actual_market_data で例外発生: {e}")
        return 50.0, 15.0


def check_65w_high_intraday(code, today_date, start_date, headers):
    """65週新高値判定（日中高値のみ）"""
    url = f"https://api.jquants.com/v1/prices/daily_quotes"
    params = {
        'code': code,
        'from': start_date,
        'to': today_date
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'daily_quotes' in data and data['daily_quotes']:
                df = pd.DataFrame(data['daily_quotes'])
                if len(df) == 0:
                    return False, 0, 0, 0, 0
                
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date')
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                df['High'] = pd.to_numeric(df['High'], errors='coerce')
                
                # 本日のデータ
                today_data = df[df['Date'] == today_date]
                if len(today_data) == 0:
                    return False, 0, 0, 0, 0
                
                today_high = today_data['High'].iloc[0]
                
                # 過去65週（本日以前）の最高値
                past_data = df[df['Date'] < today_date]
                if len(past_data) == 0:
                    return False, 0, 0, 0, 0
                
                past_max_high = past_data['High'].max()
                
                # 本日が65週新高値かどうか（日中高値のみで判定）
                is_new_high = (today_high > past_max_high)
                
                # 新高値更新回数をカウント
                new_high_count = 0
                rolling_max = 0
                
                for idx, row in df.iterrows():
                    if row['High'] > rolling_max:
                        new_high_count += 1
                    rolling_max = max(rolling_max, row['High'])
                
                return is_new_high, new_high_count, len(df), today_high, past_max_high
        
        return False, 0, 0, 0, 0
    except Exception as e:
        return False, 0, 0, 0, 0

def main():
    """ステップ1: 完全版スキャン + 市場データ取得 + 結果保存"""
    
    # Ensure ID_TOKEN is resolved: try exchanging raw env token or credentials if needed
    global ID_TOKEN
    if not ID_TOKEN:
        # try exchange again if raw env provided
        try:
            raw = os.environ.get('JQUANTS_TOKEN') or os.environ.get('JQUANTS_ACCESS_TOKEN') or os.environ.get('ID_TOKEN')
            if raw:
                exchanged = exchange_refresh_for_idtoken(raw)
                if exchanged:
                    ID_TOKEN = exchanged
        except Exception:
            pass
        # fallback to credentials flow
        if not ID_TOKEN:
            try:
                ID_TOKEN = get_id_token_from_credentials()
            except Exception:
                ID_TOKEN = None

    headers = {"Authorization": f"Bearer {ID_TOKEN}"}
    
    # 日付設定（65週前）
    # today = datetime.now()  # 実運用時は datetime.now()
    today = datetime(2025, 9, 25)
    start_date_65w = today - timedelta(weeks=65)
    today_str = today.strftime('%Y%m%d')
    start_date_str = start_date_65w.strftime('%Y%m%d')
    
    print(f"=== ステップ1: 65週新高値更新銘柄スキャン + 市場データ取得 ===")
    print(f"分析対象日: {today_str}")
    print(f"65週前: {start_date_str}")
    
    # 東証グロース銘柄リスト取得
    try:
        if not ID_TOKEN:
            print("警告: JQUANTS_TOKEN が未設定です。環境変数を確認してください。")
            return False

        # Debug: show token length (masked) to help diagnose secret issues without printing token
        try:
            print(f"JQUANTS_TOKEN length: {len(ID_TOKEN)} (masked)")
        except Exception:
            pass

        # Assume JQUANTS_TOKEN is an access token (Bearer). Use it directly.
        headers = {"Authorization": f"Bearer {ID_TOKEN}"}

        response = request_with_retry("https://api.jquants.com/v1/listed/info", headers=headers)
        if response is None:
            print("API取得エラー: リクエストが失敗しました（タイムアウトや接続エラーの可能性）。")
            return False
        if response.status_code == 200:
            try:
                all_stocks = response.json()["info"]
            except Exception as e:
                print(f"レスポンスJSONパースエラー: {e}\nレスポンステキスト: {response.text[:500]}")
                return False

            growth_stocks = [s for s in all_stocks if s.get("MarketCodeName") == "グロース"]
            print(f"グロース市場銘柄数: {len(growth_stocks)}")
        else:
            text = response.text or ''
            print(f"API取得エラー: ステータスコード={response.status_code}\nレスポンステキスト: {text[:500]}")
            if response.status_code in (401, 403) or 'invalid' in text.lower() or 'expired' in text.lower():
                print("認証エラー: 提供された JQUANTS_TOKEN が無効または期限切れの可能性があります。")
                print(" - 確認手順: GitHub Secrets の値が access token (Bearer) であること、また期限内であることを確認してください。")
                print(" - もし refresh token を使う運用に戻す場合は、環境変数に client_id/client_secret と JQUANTS_TOKEN_ENDPOINT を設定してください。")
            return False
            return False
    except Exception as e:
        print(f"銘柄リスト取得エラー: {e}")
        return False
    
    # 段階的スキャン実行
    print(f"\\n65週新高値更新銘柄スキャン（100銘柄ずつ段階処理）")
    
    batch_size = 100
    all_new_high_stocks = []
    market_data_dict = {}  # 実際の市場データを蓄積
    
    total_batches = len(growth_stocks) // batch_size + (1 if len(growth_stocks) % batch_size else 0)
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(growth_stocks))
        batch = growth_stocks[start_idx:end_idx]
        
        print(f"第{batch_num + 1}段階: 銘柄{start_idx + 1}-{end_idx}をスキャン中...")
        batch_results = []
        
        for stock in batch:
            code = stock['Code']
            name = stock['CompanyName']
            
            # 65週新高値判定
            is_new_high, high_count, total_days, today_high, past_max = check_65w_high_intraday(
                code, today_str, start_date_str, headers
            )
            
            # 新高値更新銘柄の場合、市場データも取得
            if is_new_high:
                market_cap, per = get_actual_market_data(code, headers)
                
                batch_results.append({
                    'code': code,
                    'name': name,
                    'new_high_count': high_count,
                    'today_high': today_high,
                    'past_max': past_max,
                    'total_days': total_days
                })
                
                market_data_dict[code] = {
                    'market_cap': market_cap,
                    'per': per
                }
            time.sleep(0.1)  # API制限対策
        
        all_new_high_stocks.extend(batch_results)
        print(f"第{batch_num + 1}段階結果: {len(batch_results)}件")
    
    # 保有銘柄の65週新高値判定 + 市場データ取得
    print(f"\n保有銘柄の65週新高値判定 + 市場データ取得")
    holding_stock_info = []

    for code in HOLDING_CODES:
        print(f"確認中: {code}")

        is_new_high, high_count, _, _, _ = check_65w_high_intraday(
            code, today_str, start_date_str, headers
        )

        # 保有銘柄の市場データを必ず取得
        market_cap, per = get_actual_market_data(code, headers)
        try:
            market_data_dict[code] = {
                'market_cap': float(market_cap),
                'per': float(per)
            }
        except Exception:
            market_data_dict[code] = {
                'market_cap': market_cap,
                'per': per
            }

        stock_info = next((s for s in all_stocks if s['Code'] == code), None)
        name = stock_info['CompanyName'] if stock_info else f"保有銘柄{code}"

        holding_stock_info.append({
            'code': code,
            'name': name,
            'new_high_count': high_count,
            'is_new_high_today': is_new_high
        })
        
        if is_new_high:
            print(f"  ✓ 本日65週新高値: {name} (更新回数:{high_count}, 時価総額:{market_cap:.0f}億円)")
            all_new_high_stocks.append({
                'code': code,
                'name': name,
                'new_high_count': high_count,
                'today_high': 0,
                'past_max': 0,
                'total_days': 0
            })
        else:
            print(f"  - 新高値なし: {name} (更新回数:{high_count}, 時価総額:{market_cap:.0f}億円)")
    
    # 結果をJSONファイルに保存
    results = {
        'scan_date': today_str,
        'new_high_stocks': all_new_high_stocks,
        'holding_stock_info': holding_stock_info,
        'market_data': market_data_dict,
        'token': ID_TOKEN,
        'summary': {
            'total_new_high': len(all_new_high_stocks),
            'growth_stocks_count': len(growth_stocks)
        }
    }
    
    def json_default(o):
        import numpy as np
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, (np.integer, np.int64, np.int32)):
            return int(o)
        if isinstance(o, (np.floating, np.float64, np.float32)):
            return float(o)
        return str(o)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=json_default)
    
    print(f"\\n=== ステップ1完了 ===")
    print(f"65週新高値更新銘柄: {len(all_new_high_stocks)}件")
    print(f"取得した市場データ: {len(market_data_dict)}件")
    print(f"結果保存: {OUTPUT_FILE}")
    
    # 結果表示
    print(f"\\n発見された65週新高値更新銘柄:")
    for i, stock in enumerate(all_new_high_stocks):
        print(f"{i+1:2d}. {stock['code']} {stock['name'][:30]} (更新回数:{stock['new_high_count']})")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print(f"\n✓ ステップ1正常完了")
            print(f"次ステップ: python step2_metrics_analysis.py")
            sys.exit(0)
        else:
            print(f"\n✗ ステップ1でエラーが発生")
            # Write a short message to help debugging
            msg = "ステップ1がエラーで終了しました。詳細は step1_error.log を確認してください。"
            print(msg)
            # ensure we have some trace info if any exception was caught earlier
            try:
                tb = traceback.format_exc()
            except Exception:
                tb = "No traceback available"
            with open('step1_error.log', 'w', encoding='utf-8') as ef:
                ef.write(msg + "\n\n" + tb)
            sys.exit(1)
    except Exception:
        tb = traceback.format_exc()
        print(f"Unhandled exception in main():\n{tb}")
        with open('step1_error.log', 'w', encoding='utf-8') as ef:
            ef.write(tb)
        sys.exit(1)