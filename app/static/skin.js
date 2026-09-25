// Gear menu: picking a skin saves it (the server sets the cookie) and swaps the stylesheet
// in place, so a challenge in progress is never reloaded. Without this script the form
// still works, with a page reload. Like the other scripts, no styling is set here.
(function () {
  "use strict";

  const picker = document.querySelector(".skin-picker");
  if (!picker) return;
  const form = picker.querySelector(".skin-menu");
  const stylesheet = document.querySelector('link[rel="stylesheet"]');

  form.addEventListener("submit", (event) => {
    const choice = event.submitter;
    if (!choice || !stylesheet) return;
    event.preventDefault();
    const data = new FormData(form);
    data.set("skin", choice.value);
    fetch(form.action, { method: "POST", body: data, redirect: "manual" })
      .then(() => {
        stylesheet.href = choice.dataset.themeCss;
        for (const option of form.querySelectorAll(".skin-option")) {
          if (option === choice) option.setAttribute("aria-current", "true");
          else option.removeAttribute("aria-current");
        }
        picker.open = false;
      })
      .catch(() => form.submit());
  });

  // A tap anywhere outside the open menu closes it.
  document.addEventListener("click", (event) => {
    if (picker.open && !picker.contains(event.target)) picker.open = false;
  });
})();
