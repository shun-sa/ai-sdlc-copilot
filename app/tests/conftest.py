# trace: ADDR-011
"""テスト共通の設定（pytest-django）。テストケース・フィクスチャの本体は Unit Test・Integration Test 工程が作成する。

試験用状態は各テストの開始時に設定し終了時に clear する（ADDR-011 INV-003）。
複数の接続・スレッドを使う同時実行の試験は transaction=True（コミット方式）で行う（ADDR-011 DD-010）。
"""
