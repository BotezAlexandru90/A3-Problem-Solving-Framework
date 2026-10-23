document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("button.copy");
  if (!btn) return;
  ev.preventDefault();
  var el = document.getElementById("f_" + btn.dataset.copy);
  if (!el) return;
  var text = el.value;
  var done = function () {
    var old = btn.textContent;
    btn.textContent = "Copied";
    setTimeout(function () { btn.textContent = old; }, 1200);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done);
  } else {
    // Clipboard API is unavailable over plain http on the network; fall back to a hidden textarea.
    var tmp = document.createElement("textarea");
    tmp.value = text;
    tmp.style.position = "fixed";
    tmp.style.opacity = "0";
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    document.body.removeChild(tmp);
    done();
  }
});
