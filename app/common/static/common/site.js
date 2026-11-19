// trace: ADDR-012, ADDR-004
// 画面の補助（ADDR-012 INV-002：業務規則の判定は行わない。ADDR-004 INV-003：ボタン無効化は補助に限る）。
// - data-confirm を持つフォームは送信前に確認を求め、承諾しない場合は送信しない（MSG-01、UI-12）。
// - 送信後は同じフォームの送信ボタンを無効化する（二重送信防止の補助。正の防止はサーバーの送信トークン）。
(function () {
  "use strict";
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    if (form.method && form.method.toLowerCase() === "post") {
      window.setTimeout(function () {
        var buttons = form.querySelectorAll("button[type=submit]");
        for (var i = 0; i < buttons.length; i += 1) {
          buttons[i].disabled = true;
        }
      }, 0);
    }
  });
})();
