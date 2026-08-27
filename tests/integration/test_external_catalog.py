"""External Integration Test Cases: 映画・商品カタログ（IT-010〜IT-020）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.constants import MovieStatus, PublishStatus
from tests.integration._helpers import login, make_movie, make_product, make_screening, make_user

UTC = timezone.utc


def _detail_link_count(text: str, prefix: str) -> int:
    return text.count(f'href="{prefix}')


# IT-010: 映画検索：タイトル検索（FR-003 / C-DATA-001）
def test_it_010_movie_search_by_title(client, session_factory):
    with session_factory() as s:
        make_movie(s, title="スペースヒーロー", genre="SF")
        make_movie(s, title="海の物語", genre="ドラマ")
        s.commit()

    res = client.get("/movies", params={"keyword": "スペース"})
    assert res.status_code == 200
    assert "スペースヒーロー" in res.text
    assert "海の物語" not in res.text
    assert "検索結果: 1件" in res.text


# IT-011: 映画検索：ジャンル・並び替え・ページング（FR-003 / C-UI-003 / NFR-PERF-003）
def test_it_011_movie_search_sort_paging(client, session_factory):
    base = datetime(2030, 1, 1, tzinfo=UTC)
    with session_factory() as s:
        for i in range(21):
            make_movie(
                s,
                title=f"作品{i:02d}",
                genre="SF",
                release_date=base + timedelta(days=i),
            )
        make_movie(s, title="別ジャンル", genre="コメディ")
        s.commit()

    page1 = client.get("/movies", params={"genre": "SF", "sort": "release_desc", "page": 1})
    page2 = client.get("/movies", params={"genre": "SF", "sort": "release_desc", "page": 2})
    assert page1.status_code == 200
    assert "検索結果: 21件" in page1.text
    assert _detail_link_count(page1.text, "/movies/") == 20  # 1ページ20件標準
    assert _detail_link_count(page2.text, "/movies/") == 1


# IT-012: 映画検索：非公開・削除済み除外（FR-003 / C-DATA-001）
def test_it_012_movie_search_excludes_unpublished(client, session_factory):
    with session_factory() as s:
        make_movie(s, title="公開作品X", status=MovieStatus.PUBLISHED)
        make_movie(s, title="非公開作品Y", status=MovieStatus.UNPUBLISHED)
        s.commit()

    res = client.get("/movies")
    assert "公開作品X" in res.text
    assert "非公開作品Y" not in res.text


# IT-013: 映画検索：0件（FR-003）
def test_it_013_movie_search_empty(client, session_factory):
    with session_factory() as s:
        make_movie(s, title="唯一の作品")
        s.commit()

    res = client.get("/movies", params={"keyword": "存在しないキーワードZZZ"})
    assert res.status_code == 200
    assert "検索結果: 0件" in res.text
    assert "0件です" in res.text


# IT-014: 映画詳細：作品情報・上映回・関連商品（FR-004 / C-UI-005）
def test_it_014_movie_detail(client, session_factory):
    starts_at = datetime(2030, 6, 15, 13, 30, tzinfo=UTC)
    with session_factory() as s:
        movie = make_movie(s, title="詳細対象作品", genre="SF", synopsis="壮大なあらすじ")
        make_product(s, name="関連グッズA", movie_id=movie.id)
        make_screening(s, movie_id=movie.id, starts_at=starts_at)
        movie_id = movie.id
        s.commit()

    res = client.get(f"/movies/{movie_id}")
    assert res.status_code == 200
    assert "詳細対象作品" in res.text
    assert "SF" in res.text
    assert "関連グッズA" in res.text
    assert "2030/06/15 13:30" in res.text  # YYYY/MM/DD HH:mm


# IT-015: 映画詳細：上映終了回（FR-004 / ERR-004）
def test_it_015_movie_detail_ended_screening_not_purchasable(client, session_factory):
    past = datetime.now(UTC) - timedelta(days=1)
    with session_factory() as s:
        user = make_user(s, email="it015@example.com")
        movie = make_movie(s, title="上映終了対象")
        ended = make_screening(
            s,
            movie_id=movie.id,
            starts_at=past,
            sales_start_at=past - timedelta(days=10),
            sales_end_at=past - timedelta(hours=1),
        )
        movie_id, screening_id = movie.id, ended.id
        s.commit()

    login(client, "it015@example.com")
    res = client.get(f"/movies/{movie_id}")
    assert res.status_code == 200
    # 上映終了回には購入導線が表示されない
    assert f"/tickets/new?screening_id={screening_id}" not in res.text


# IT-016: 商品検索：キーワード・関連映画（FR-005 / C-UI-003）
def test_it_016_product_search(client, session_factory):
    with session_factory() as s:
        movie = make_movie(s, title="タイアップ映画")
        make_product(s, name="限定フィギュア", movie_id=movie.id)
        make_product(s, name="通常タオル")
        s.commit()

    by_keyword = client.get("/products", params={"keyword": "フィギュア"})
    assert "限定フィギュア" in by_keyword.text
    assert "通常タオル" not in by_keyword.text
    assert "検索結果: 1件" in by_keyword.text


# IT-017: 商品検索：非公開・削除済み除外（FR-005 / C-DATA-001）
def test_it_017_product_search_excludes_unpublished(client, session_factory):
    with session_factory() as s:
        make_product(s, name="公開商品P", publish_status=PublishStatus.PUBLISHED)
        make_product(s, name="非公開商品Q", publish_status=PublishStatus.UNPUBLISHED)
        s.commit()

    res = client.get("/products")
    assert "公開商品P" in res.text
    assert "非公開商品Q" not in res.text


# IT-018: 商品詳細：販売期間外（FR-005 / C-DATA-002 / ERR-004 / AC-COM-006）
def test_it_018_product_out_of_sales_period(client, session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        product = make_product(
            s,
            name="販売前商品",
            sales_start_at=now + timedelta(days=5),  # 販売開始前
            sales_end_at=now + timedelta(days=30),
            stock=10,
        )
        product_id = product.id
        s.commit()

    res = client.get(f"/products/{product_id}")
    assert res.status_code == 200
    assert "販売期間外" in res.text
    assert 'action="/cart/add"' not in res.text  # 購入導線なし


# IT-019: 商品詳細：在庫0（FR-005 / C-DATA-003）
def test_it_019_product_no_stock(client, session_factory):
    with session_factory() as s:
        product = make_product(s, name="品切れ商品", stock=0)
        product_id = product.id
        s.commit()

    res = client.get(f"/products/{product_id}")
    assert res.status_code == 200
    assert "在庫なし" in res.text
    assert 'action="/cart/add"' not in res.text


# IT-020: 金額表示（C-UI-004）
def test_it_020_price_format(client, session_factory):
    with session_factory() as s:
        product = make_product(s, name="価格表示商品", price=1980)
        product_id = product.id
        s.commit()

    res = client.get(f"/products/{product_id}")
    assert "1,980円" in res.text  # 税込・3桁区切り
