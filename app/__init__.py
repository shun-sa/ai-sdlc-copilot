"""映画館EC Webシステム (Cinema EC) アプリケーションパッケージ.

レイヤードアーキテクチャ (ADR-003):
- routers      : Presentation層
- services     : Application層 (トランザクション境界)
- （models内に業務ルールを保持する軽量Domain）
- repositories : Infrastructure層 (DBアクセス)
"""
