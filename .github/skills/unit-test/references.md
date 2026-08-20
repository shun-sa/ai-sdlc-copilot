# Unit Test Policy References

## Code Coverage

Google Testing Blog - Code Coverage Best Practices

<https://testing.googleblog.com/2020/08/code-coverage-best-practices.html>

参考ポイント:

- 一律の理想Coverage値は存在しない
- 60%: acceptable
- 75%: commendable
- 90%: exemplary

本プロジェクトでは、
50人月程度のWebアプリケーションを想定した初期基準として
80%を採用する。

## Coverage Gate

Jest Documentation - coverageThreshold

<https://jestjs.io/docs/configuration>

参考ポイント:

- Statement / Branch / Function / Lineごとに
  Coverage Thresholdを設定できる
- Threshold未達をTest Failureとして扱える

## Security / Input Validation

OWASP Web Security Testing Guide

<https://owasp.org/www-project-web-security-testing-guide/stable/>

参考ポイント:

- Input Validation
- Business Logic Data Validation
- 不正入力・業務ルール違反の検証

## Database Testing

Testcontainers - Database Containers

<https://java.testcontainers.org/modules/databases/>

参考ポイント:

- DisposableなDatabase ContainerをTestで利用できる
- Testごとに既知のDatabase状態を作れる
- DB固有機能を利用するDAO Testに利用できる
- 上位レイヤーではDBアクセスを減らしMockを活用する
