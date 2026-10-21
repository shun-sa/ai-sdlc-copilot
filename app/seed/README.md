# 初期データ定義ファイルの配置先

- 本ディレクトリに初期データ定義ファイル（JSON、UTF-8）を配置する（FR-060、FILE-001）。
- 既定のファイル名は `initial_data.json`（コマンド例は `seed/initial_data.json`）。
- 定義ファイルは平文パスワード・個人情報（架空の値）を含むため、バージョン管理の追跡対象にしない
  （リポジトリルートの `.gitignore` で `app/seed/*.json` を除外している。NFR-SC-07、FILE-001 12章）。
- 投入後はファイルをサーバー上から退避または削除する。差し替えは別名で配置してから改名する。

投入コマンド:

```text
docker compose exec app python manage.py load_initial_data seed/initial_data.json --reset
```
