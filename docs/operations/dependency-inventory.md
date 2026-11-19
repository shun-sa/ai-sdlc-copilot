# 依存ライブラリ・実行環境の一覧（MiniCommerce）

ADDR-014 DD-009（NFR-EN-10、NFR-EN-12、NFR-SC-11、NFR-SC-21 VUL-09・VUL-10）に基づく記録。
版の正本は `app/requirements.txt`・`app/requirements-dev.txt`（pip-tools・ハッシュ付き）、`app/Dockerfile`・`compose.yaml`（ダイジェスト固定）とする。
本書は Implementation 工程（RUN-AOBA-EC-1118）時点の記録であり、リリース前の全依存の最終確認・再照合は TASK-021 で行う。

- 照合日：2026-11-19
- 取得元：Python パッケージは PyPI、コンテナイメージは Docker Hub の公式イメージ（ADDR-014 4.3 の6）
- 脆弱性照合：pip-audit（PyPI の脆弱性情報）で `app/requirements.txt`・`app/requirements-dev.txt` を照合し「No known vulnerabilities found」（既知の脆弱性 0件。CVSS 7.0以上 0件）。
  照合ツールは Implementation 工程の自己確認に用いたもので、試験計画でのツール選定（NCN-07）を代替しない。
- ライセンス：インストール済みパッケージのメタデータ（License-Expression・License・Classifier）から記録。AGPL・ライセンス不明は 0件。

## 1. 実行環境

| 名称 | 版 | 取得元（ダイジェスト） | ライセンス | サポート期限（公開情報） | 脆弱性照合 |
| --- | --- | --- | --- | --- | --- |
| Python（python:3.12-slim） | 3.12.16 | docker.io/library/python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b | PSF-2.0 | 2028-10（Python 3.12 のセキュリティ修正期限） | イメージの OS パッケージは未照合（TASK-021 で照合） |
| PostgreSQL（postgres:16） | 16 | docker.io/library/postgres@sha256:3950ad7c3148ca2175ef1b6c36c9efbf78957ae8fbe8b3a5d7c35af50500382f | PostgreSQL License | 2028-11（PostgreSQL 16 のサポート期限） | イメージの OS パッケージは未照合（TASK-021 で照合） |

## 2. 実行時の依存（app/requirements.txt）

| パッケージ | 版 | 種別 | ライセンス | サポート期限 | 既知の脆弱性（CVSS 7.0以上） |
| --- | --- | --- | --- | --- | --- |
| Django | 5.2.19 | 直接 | BSD-3-Clause | 2028-04（5.2 LTS） | 0件 |
| djangorestframework | 3.18.3 | 直接 | BSD-3-Clause | 期限の公表なし（Django 5.2 対応版） | 0件 |
| psycopg | 3.3.9 | 直接 | LGPL-3.0-only | 期限の公表なし | 0件 |
| psycopg-binary | 3.3.9 | 間接（psycopg[binary]） | LGPL-3.0-only | 期限の公表なし | 0件 |
| gunicorn | 27.0.1 | 直接 | MIT | 期限の公表なし | 0件 |
| whitenoise | 6.12.0 | 直接 | MIT | 期限の公表なし | 0件 |
| asgiref | 3.13.0 | 間接（Django） | BSD-3-Clause | 期限の公表なし | 0件 |
| sqlparse | 0.6.1 | 間接（Django） | BSD License | 期限の公表なし | 0件 |
| typing-extensions | 4.16.0 | 間接（psycopg） | PSF-2.0 | 期限の公表なし | 0件 |

LGPL-3.0 の psycopg は改変せずにライブラリとして利用し、社外へ配布しないサーバー上での利用であり利用条件を満たす（NFR-EN-12）。

## 3. 開発・試験用の依存（app/requirements-dev.txt。ENV-01 の app コンテナのみ）

| パッケージ | 版 | ライセンス | 既知の脆弱性 |
| --- | --- | --- | --- |
| pytest | 9.2.0 | MIT | 0件 |
| pytest-django | 4.14.0 | BSD License | 0件 |
| ruff | 0.17.5 | MIT | 0件 |
| pip-tools | 7.7.0 | BSD-3-Clause | 0件 |
| build | 1.6.1 | MIT | 0件 |
| click | 8.5.1 | BSD-3-Clause | 0件 |
| iniconfig | 2.3.1 | MIT | 0件 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | 0件 |
| pluggy | 1.7.0 | MIT | 0件 |
| pygments | 2.21.0 | BSD-2-Clause | 0件 |
| pyproject-hooks | 1.3.3 | MIT | 0件 |
| wheel | 0.48.0 | MIT | 0件 |
| pip | 26.3 | MIT | 0件 |
| setuptools | 84.2.1 | MIT | 0件 |

## 4. 再構築の手順

```text
# 依存の版の更新（Linux の Python 3.12 で実行する）
pip-compile --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url --output-file app/requirements.txt app/requirements.in
pip-compile --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url --output-file app/requirements-dev.txt app/requirements-dev.in
# イメージの再構築（--require-hashes で取得）
docker compose build
```
