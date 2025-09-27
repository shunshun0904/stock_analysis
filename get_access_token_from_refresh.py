#!/usr/bin/env python3
"""
Refresh token -> access token (helper)

注意:
- このスクリプトは与えられたリフレッシュトークンを使ってアクセストークン取得を試みます。
- トークンや client_secret を Git にコミットしないでください（セキュリティリスク）。
- 必要に応じて環境変数 `JQUANTS_CLIENT_ID`, `JQUANTS_CLIENT_SECRET`, `JQUANTS_TOKEN_ENDPOINT` を設定できます。

使い方例:
  python get_access_token_from_refresh.py --save

--save を付けると成功時に `access_token.txt` に保存します（同ディレクトリ）。
"""
import os
import sys
import argparse
import requests
import base64
import json

# --- ユーザーが指定したリフレッシュトークン（ここに直書きして試す） ---
REFRESH_TOKEN = (
    "eyJjdHkiOiJKV1QiLCJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiUlNBLU9BRVAifQ.TFGq5lP-FmIQpLu0MngtWtux-HmQaeZPZwH3K2Roxb2pudMyVl2nUUf31aSgW0dVwbLEw7IMJ_r90XrosIiUnvq4aKCeoTu71w5sw8SkuODXNiZ_j-0RPWf0iXMfNeIZuzH19ROBTGvmqe88GxUN-5LK9zzVfOxa_y7HFGxlTnIlgg2KCeWxGv2SS7kEKbqgqCagsjh6EtMuvuJ9G6-X5Q6UlWVveI5gaqj121RyvO8FaTWX07FF73kjp27X0nk5rareMw6yagW0riFkivWDh7xoOXx852OPAvXYn3HR6_-YJwoXSJY3Lg--44rKAAah5LYqIdrKY9dsIpPKG6Gfug.x1IpEZEj_O_t7hMI.RxPNHRqlgTJNLHwBywWXS6HKcjKsGJfhOuvxcOEF8LllUkFtWuMeoxoAcjd5tgubTpm90EUSwLjgmtInbusJwgWyLqXr7rezhP2OPjfKZh51bFTIwrZsz4TTqKVmXwMLKS4IwWkEMNB__AAfylfLzv8ocF9FJC873KjL2nAlCYZl82xtd4fTnfIaTR-bshmJsL6JVTlv_ClVOt_dbvsgvUgOHK0XtskrnLq8wAveUK-v8H72cscEitHEM29zwlcI3to9_ebJ6ilgxXmsA0PzwfoUVaqYC7DEIn7JrrvheNhbC2YjZZLcy_nkoCzEGrB3STTnDUYW8Y_tlugtr0rngId_dtKj0gOvMEd5sdfVXRkpHkubr5v6pDt0iR7SG8f5ZF9-SPkkndRHMHuOA2gYG2uT9A-LNl5Ag5CY3o347bZENq7Ljj7dcOnOKjO7NznA8SRNK9U3MKvRTzx2tTESV00e1zj1cBxlvFUypOhwYLhTtJqJqtU9cEaQ2bZiqbr9Yvq5tfRo_HkIqNGMPGlcnL8y8_KkkjVGCE-quJQmOdGq73QbqD6IRRFDoL20p7bDBSxv41hNbjz0jmjqc-wY5t7bQuWjZ_7uMuOxiLKGRL9PkG2Km9twAmmGnVXaH0Zs9NkrNsTsAdVEW5WyW5vAxVV-YrPW75gpGpDtay3y7aEO4P_aYqFX_qi65uZ-X8L512Pf6IaDOmpO60ioeGEFXVEBbV6s7Dymoj9mp4GsA7xcvZHcjeiV2dtEsJ9uOVJxqNGAdO1fGm08T7tvfi-6cxnRMB_dqDdw7EYL_PXcMdDWxqFBB9erLh6EPGt8RscC8kFdneudNzsjFdn5DmaZguUB9k8X2vAnbpzEc8MQ7Y3E0rBldNXgvmogNJvbNofHccdePZmBYNOc8cQY-trfys6K6mMPu7AW0DL_6tbyqw8h3XLA_DNsTvRSTiS4EaKCJXInlZzPIqx_6mbxezUuaumtvaXzUunJFsiQaOS_bhDfCiym11PNxuEREunhENWw33sDp25jiiNHK92xXvBqlpOWJxY91fiKwGUmFK9mocCWnVAcmRcL8oPAFfLZi3Jv7ZBk6ZFtMuRuSWM2m-Cosj5n6IJ546e6ooceMfYEuAsDTpwUnBDDbdZ3q0Z0bW6bShxM9WNF78emibkVRL4V_jXvd_YwqZU9PHfriM3tTXYq_O7v9SxoTQ8YnYO0V5fRUmh1uBCd4QFi9CTlTNrSjfJ4C93Z4pcXj4E1St-Wrvgs534rKw308Y9qFbvsYMY9-BdjId8vSzeiuSBP8oWVTQDQgyWGAYtMM-gZuUwl4dZdk-ihQt8nXO5WDdme8ZP3rei4eEBhc_WgtQ.rTqfty_BJUI3a9FxNs4pkg"
)
# 上は長いトークンの先頭を示しています。実際には全体をここに貼るか、環境変数で渡してください。
# セキュリティ上の理由で、推奨は環境変数 JQUANTS_REFRESH_TOKEN を利用することです。

# --- 環境変数で補助情報を取得 ---
CLIENT_ID = os.environ.get('JQUANTS_CLIENT_ID')
CLIENT_SECRET = os.environ.get('JQUANTS_CLIENT_SECRET')
TOKEN_ENDPOINT_ENV = os.environ.get('JQUANTS_TOKEN_ENDPOINT')

# コマンドライン引数
parser = argparse.ArgumentParser()
parser.add_argument('--save', action='store_true', help='成功時に access_token.txt に保存する')
parser.add_argument('--token', default=None, help='リフレッシュトークンを直接渡す（コマンドライン）')
args = parser.parse_args()

refresh_token = args.token or os.environ.get('JQUANTS_REFRESH_TOKEN') or REFRESH_TOKEN
if not refresh_token or refresh_token.strip().endswith('...'):
    print('リフレッシュトークンが設定されていません。環境変数 JQUANTS_REFRESH_TOKEN を使うか、スクリプト内にフルトークンを貼ってください。')
    sys.exit(1)

# 候補エンドポイント
candidate_endpoints = []
if TOKEN_ENDPOINT_ENV:
    candidate_endpoints.append(TOKEN_ENDPOINT_ENV)
candidate_endpoints.extend([
    'https://api.jquants.com/v1/oauth/token',
    'https://api.jquants.com/oauth2/token',
    'https://api.jquants.com/v1/token',
])
# 一意化
seen = set()
candidate_endpoints = [e for e in candidate_endpoints if e and (e not in seen and not seen.add(e))]


def mask(s, head=4, tail=4):
    if not s:
        return ''
    if len(s) <= head + tail:
        return '****'
    return s[:head] + '...' + s[-tail:]


def try_post_form(endpoint, body, headers=None):
    try:
        resp = requests.post(endpoint, data=body, headers=headers, timeout=15)
        return resp
    except Exception as e:
        print(f'  [ERROR] 接続失敗: {e}')
        return None


print('=== リフレッシュトークンからアクセストークン取得を試行します ===')
print('候補 endpoint:', candidate_endpoints)
print('CLIENT_ID:', 'set' if CLIENT_ID else 'None')
print('CLIENT_SECRET:', 'set' if CLIENT_SECRET else 'None')

# まず JQuants の簡易エンドポイントを試す: /v1/token/auth_refresh?refreshtoken=...
print('\n--- auth_refresh エンドポイント（簡易）を先に試行します ---')
try:
    auth_refresh_url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"
    r = requests.post(auth_refresh_url, timeout=15)
    print(f'  auth_refresh status={r.status_code}')
    print('  resp:', r.text[:800])
    if r.status_code in (200, 201):
        try:
            jd = r.json()
            access = (
                jd.get('access_token') or jd.get('accessToken') or jd.get('token') or jd.get('id_token')
                or jd.get('idToken') or jd.get('tokenValue') or jd.get('idTokenValue')
            )
            if access:
                print('  => auth_refresh でアクセストークン取得成功:', mask(access))
                if args.save:
                    with open('access_token.txt', 'w') as f:
                        f.write(access)
                    print('   saved to access_token.txt')
                sys.exit(0)
        except Exception:
            pass
except Exception as e:
    print('  auth_refresh 接続エラー:', e)


for endpoint in candidate_endpoints:
    print('\n--- 試行 endpoint:', endpoint, '---')

    # 1) body に client_id/client_secret を含める方法
    body = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    if CLIENT_ID:
        body['client_id'] = CLIENT_ID
    if CLIENT_SECRET:
        body['client_secret'] = CLIENT_SECRET

    print('  方法1: フォームボディ送信')
    resp = try_post_form(endpoint, body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if resp is not None:
        print(f'    status={resp.status_code}')
        text_preview = resp.text[:800]
        print('    resp:', text_preview)
        if resp.status_code in (200, 201):
            try:
                jd = resp.json()
                access = (
                    jd.get('access_token') or jd.get('accessToken') or jd.get('token') or jd.get('id_token')
                    or jd.get('idToken') or jd.get('tokenValue') or jd.get('idTokenValue')
                )
                if access:
                    print('  => アクセストークン取得成功:', mask(access))
                    if args.save:
                        with open('access_token.txt', 'w') as f:
                            f.write(access)
                        print('   saved to access_token.txt')
                    sys.exit(0)
            except Exception:
                pass

    # 2) Basic 認証ヘッダ (client_id:client_secret)
    if CLIENT_ID and CLIENT_SECRET:
        try:
            basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
            headers = {'Authorization': f'Basic {basic}', 'Content-Type': 'application/x-www-form-urlencoded'}
            print('  方法2: Basic auth (client_id:client_secret)')
            resp = try_post_form(endpoint, {'grant_type': 'refresh_token', 'refresh_token': refresh_token}, headers=headers)
            if resp is not None:
                print(f'    status={resp.status_code}')
                print('    resp:', resp.text[:800])
                if resp.status_code in (200, 201):
                    try:
                        jd = resp.json()
                        access = jd.get('access_token') or jd.get('accessToken') or jd.get('token')
                        if access:
                            print('  => アクセストークン取得成功:', mask(access))
                            if args.save:
                                with open('access_token.txt', 'w') as f:
                                    f.write(access)
                                print('   saved to access_token.txt')
                            sys.exit(0)
                    except Exception:
                        pass
        except Exception as e:
            print('  Basic auth 試行で例外:', e)

    # 3) x-api-key ヘッダ (一部サービス向け)
    if CLIENT_ID and len(CLIENT_ID) > 10:
        print('  方法3: x-api-key ヘッダ')
        headers = {'x-api-key': CLIENT_ID, 'Content-Type': 'application/x-www-form-urlencoded'}
        resp = try_post_form(endpoint, {'grant_type': 'refresh_token', 'refresh_token': refresh_token}, headers=headers)
        if resp is not None:
            print(f'    status={resp.status_code}')
            print('    resp:', resp.text[:800])
            if resp.status_code in (200, 201):
                try:
                    jd = resp.json()
                    access = (
                        jd.get('access_token') or jd.get('accessToken') or jd.get('token') or jd.get('id_token')
                        or jd.get('idToken') or jd.get('tokenValue') or jd.get('idTokenValue')
                    )
                    if access:
                        print('  => アクセストークン取得成功:', mask(access))
                        if args.save:
                            with open('access_token.txt', 'w') as f:
                                f.write(access)
                            print('   saved to access_token.txt')
                        sys.exit(0)
                except Exception:
                    pass

print('\n== 全試行終了: アクセストークン取得失敗 ==')
print('レスポンスに 403/Missing Authentication Token が出る場合、endpoint URL または認証方式が間違っています。')
print('JQUANTS_TOKEN_ENDPOINT, JQUANTS_CLIENT_ID, JQUANTS_CLIENT_SECRET を確認してください。')
sys.exit(2)
