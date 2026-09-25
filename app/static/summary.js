// Summary page: the View rounds button shows and hides each round's results.
// Like challenge.js, this only toggles the `hidden` attribute and sets text; the theme
// CSS does all the styling.
(function () {
  "use strict";

  const button = document.getElementById("toggle-rounds");
  const rounds = document.getElementById("rounds");
  if (!button || !rounds) return;

  button.addEventListener("click", () => {
    const show = rounds.hidden;
    rounds.hidden = !show;
    button.setAttribute("aria-expanded", String(show));
    button.textContent = show ? "Hide rounds" : "View rounds";
  });
})();
