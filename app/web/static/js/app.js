/* trace: ADDR-010 */
// 確認ダイアログ（UI-12）と更新ボタンの二重送信防止（UI-15）のみを行う。
// 画面の表示内容はサーバー側で生成する（業務ルールは実装しない）。
(function () {
  "use strict";

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var button = form.querySelector("[data-submit-once]");
    if (!button) {
      return;
    }
    var message = button.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    button.disabled = false;
    window.setTimeout(function () {
      button.disabled = true;
    }, 0);
  });
})();
