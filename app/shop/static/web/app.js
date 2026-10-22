// trace: ADDR-004
// JavaScript の用途は、取消できない操作の確認ダイアログ（NFR-US-09）と
// 更新ボタンの二重送信防止（NFR-US-10）に限る。
(function () {
  "use strict";

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var confirmMessage = form.getAttribute("data-confirm");
    if (confirmMessage && !window.confirm(confirmMessage)) {
      event.preventDefault();
      return;
    }
    var buttons = form.querySelectorAll('[data-submit-once="true"]');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
    }
  });
})();
