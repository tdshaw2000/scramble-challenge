// Challenge page client: talks to the server over Socket.IO and switches screens.
// Presentation lives entirely in the theme CSS: this file only shows/hides elements
// (the `hidden` attribute), sets text, and sets data-phase on #game for themes to use.
(function () {
  "use strict";

  const INSPECTION_SECONDS = 15;

  function formatTime(ms) {
    if (ms === null || ms === undefined) return "DNF";
    const totalSeconds = ms / 1000;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = (totalSeconds - minutes * 60).toFixed(2);
    return minutes > 0 ? `${minutes}:${seconds.padStart(5, "0")}` : seconds;
  }

  function ordinal(n) {
    const tens = n % 100;
    const suffix = tens >= 11 && tens <= 13 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
    return `${n}${suffix}`;
  }

  window.ScrambleChallenge = { formatTime, ordinal };

  const game = document.getElementById("game");
  if (!game) return;

  const $ = (id) => document.getElementById(id);
  const isCo = game.dataset.isCo === "true";
  const socket = io();

  let roundNumber = null;
  let phase = "lobby";
  let inspectionStartedAt = 0;
  let solveStartedAt = 0;
  let ticker = null;

  function setPhase(next) {
    phase = next;
    game.dataset.phase = next;
    const show = {
      lobby: ["lobby"],
      scramble: ["scramble"],
      inspecting: ["overlay"],
      solving: ["overlay"],
      waiting: ["results"],
      results: ["results", "lobby"],
      ended: ["results"],
    }[next];
    for (const id of ["lobby", "scramble", "overlay", "results"]) {
      $(id).hidden = !show.includes(id);
    }
  }

  function setText(id, text) {
    $(id).textContent = text;
  }

  function showMessage(text) {
    setText("message", text);
    $("message").hidden = !text;
  }

  function element(tag, className, text) {
    const el = document.createElement(tag);
    el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function renderPlayers(players) {
    const list = $("players");
    list.replaceChildren();
    for (const p of players) {
      const label = p.display_name + (p.is_co ? " (owner)" : "") + (p.connected ? "" : " (away)");
      const li = element("li", "player", label);
      li.classList.toggle("player-co", p.is_co);
      li.classList.toggle("player-away", !p.connected);
      list.appendChild(li);
    }
  }

  function renderResults(results) {
    const list = $("leaderboard");
    list.replaceChildren();
    for (const r of results) {
      const li = element("li", `result result-${r.result} result-position-${r.position}`);
      li.append(
        element("span", "position", ordinal(r.position)),
        element("span", "name", r.display_name),
        element("span", "time", formatTime(r.time_ms)),
      );
      list.appendChild(li);
    }
  }

  function setEndRoundVisible(visible) {
    if ($("end-round")) $("end-round").hidden = !visible;
  }

  function stopTicker() {
    clearInterval(ticker);
    ticker = null;
  }

  // --- server events -------------------------------------------------------

  socket.on("connect", () => socket.emit("join_challenge", { challenge_slug: game.dataset.slug }));

  socket.on("player_list", renderPlayers);

  socket.on("round_started", (round) => {
    roundNumber = round.round_number;
    setText("round-heading", `Round ${roundNumber}`);
    setText("results-heading", `Round ${roundNumber}`);
    setText("scramble-text", round.scramble_text);
    $("scramble-image").src = round.scramble_svg_url;
    renderResults([]);
    showMessage("");
    setEndRoundVisible(true);
    setPhase("scramble");
  });

  socket.on("leaderboard_update", (update) => renderResults(update.results));

  socket.on("round_complete", (update) => {
    stopTicker();
    renderResults(update.results);
    setText("results-heading", roundNumber ? `Round ${roundNumber} results` : "Last round's results");
    setEndRoundVisible(false);
    setPhase("results");
  });

  socket.on("challenge_ended", () => {
    stopTicker();
    setEndRoundVisible(false);
    setPhase("ended");
    showMessage("This challenge has ended because the owner left.");
  });

  socket.on("game_error", (error) => showMessage(error.message));

  // --- player actions ------------------------------------------------------

  if (isCo) {
    $("start-form").addEventListener("submit", (event) => {
      event.preventDefault();
      socket.emit("start_round", { puzzle: $("puzzle").value });
    });
    $("end-round").addEventListener("click", () => socket.emit("end_round", {}));
    $("copy-link").addEventListener("click", async () => {
      await navigator.clipboard.writeText($("share-link").value);
      setText("copy-link", "Copied!");
      setTimeout(() => setText("copy-link", "Copy link"), 2000);
    });
  }

  $("start-inspection").addEventListener("click", () => {
    socket.emit("start_inspection", {});
    inspectionStartedAt = performance.now();
    setText("countdown", INSPECTION_SECONDS);
    $("countdown").hidden = false;
    $("solving").hidden = true;
    setPhase("inspecting");
    ticker = setInterval(() => {
      const elapsed = Math.floor((performance.now() - inspectionStartedAt) / 1000);
      const remaining = Math.max(0, INSPECTION_SECONDS - elapsed);
      setText("countdown", remaining);
      if (remaining === 0) {
        // House rule, not WCA's: letting the countdown reach zero is a DNF.
        stopTicker();
        socket.emit("inspection_expired", {});
        showMessage("Inspection ran out: DNF.");
        setPhase("waiting");
      }
    }, 100);
  });

  // A press anywhere on the blank screen starts the solve, and the next one stops it.
  $("overlay").addEventListener("pointerdown", () => {
    if (phase === "inspecting") {
      stopTicker();
      solveStartedAt = performance.now();
      socket.emit("start_solve", {});
      setText("countdown", "");
      $("countdown").hidden = true;
      $("solving").hidden = false;
      setPhase("solving");
    } else if (phase === "solving") {
      const timeMs = Math.max(1, Math.round(performance.now() - solveStartedAt));
      socket.emit("stop_solve", { time_ms: timeMs });
      setPhase("waiting");
    }
  });
})();
