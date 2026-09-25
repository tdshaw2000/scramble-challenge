// Challenge page client: talks to the server over Socket.IO and switches screens.
// Presentation lives entirely in the theme CSS: this file only shows/hides elements
// (the `hidden` attribute), sets text, and sets data-phase on #game and data-puzzle on
// #scramble for themes to use.
(function () {
  "use strict";

  const INSPECTION_SECONDS = 15;
  // How long the player's own time (or DNF) fills the screen after they finish.
  const FINISHED_MS = 1000;

  function formatTime(ms) {
    if (ms === null || ms === undefined) return "DNF";
    // Truncate to hundredths like WCA results: 12.349 shows as 12.34, never rounded up.
    // Whole-number maths only, so floating point can't nudge a time across a boundary.
    const hundredths = Math.floor(ms / 10);
    const minutes = Math.floor(hundredths / 6000);
    const rest = hundredths % 6000;
    const seconds = `${Math.floor(rest / 100)}.${String(rest % 100).padStart(2, "0")}`;
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
  let heldInInspection = false;
  let finishedTimer = null;
  let roundEndedWhileFinished = false;

  function setPhase(next) {
    clearTimeout(finishedTimer);
    phase = next;
    game.dataset.phase = next;
    if (next !== "inspecting") setHeld(false);
    const show = {
      lobby: ["lobby"],
      scramble: ["scramble"],
      inspecting: ["overlay"],
      solving: ["overlay"],
      finished: ["overlay"],
      waiting: ["results"],
      results: ["results", "lobby"],
    }[next];
    for (const id of ["lobby", "scramble", "overlay", "results"]) {
      $(id).hidden = !show.includes(id);
    }
    $("finished").hidden = next !== "finished";
    $("overlay-hint").hidden = next === "finished";
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

  // Round wins so far in this challenge, in brackets after the name.
  function nameWithPoints(person) {
    return `${person.display_name} (${person.points})`;
  }

  function renderPlayers(players) {
    const list = $("players");
    list.replaceChildren();
    for (const p of players) {
      const label = nameWithPoints(p) + (p.is_co ? " (owner)" : "") + (p.connected ? "" : " (away)");
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
        element("span", "name", nameWithPoints(r)),
        element("span", "time", formatTime(r.time_ms)),
      );
      list.appendChild(li);
    }
  }

  function setEndRoundVisible(visible) {
    if ($("end-round")) $("end-round").hidden = !visible;
  }

  // The owner can end the challenge only from a finished round's results; the server
  // refuses it at any other time. Confirming first stops a stray tap ending it for everyone.
  function setEndChallengeVisible(visible) {
    if (!$("end-challenge")) return;
    $("end-challenge").hidden = !visible;
    $("end-challenge-confirm").hidden = true;
  }

  function stopTicker() {
    clearInterval(ticker);
    ticker = null;
  }

  // --- server events -------------------------------------------------------

  socket.on("connect", () => socket.emit("join_challenge", { challenge_slug: game.dataset.slug }));

  // The owner may start a round only while this page has joined the challenge; before that
  // the server rejects it. app/sockets.py sends player_list only to the challenge's room, so
  // receiving it means this socket has joined. After a disconnect the page must rejoin, and
  // Socket.IO would send a buffered click before the rejoin, so the button waits again.
  function setStartRoundEnabled(enabled) {
    if ($("start-round")) $("start-round").disabled = !enabled;
  }

  socket.on("player_list", (players) => {
    renderPlayers(players);
    setStartRoundEnabled(true);
  });

  socket.on("disconnect", () => setStartRoundEnabled(false));

  socket.on("round_started", (round) => {
    roundNumber = round.round_number;
    setText("round-heading", `Round ${roundNumber}: ${round.puzzle_name}`);
    setText("results-heading", `Round ${roundNumber}`);
    $("scramble").dataset.puzzle = round.puzzle;
    setText("scramble-text", round.scramble_text);
    $("scramble-image").src = round.scramble_svg_url;
    renderResults([]);
    showMessage("");
    setEndRoundVisible(true);
    setEndChallengeVisible(false);
    setPhase("scramble");
  });

  socket.on("leaderboard_update", (update) => renderResults(update.results));

  socket.on("round_complete", (update) => {
    stopTicker();
    renderResults(update.results);
    setText("results-heading", roundNumber ? `Round ${roundNumber} results` : "Last round's results");
    setEndRoundVisible(false);
    setEndChallengeVisible(true);
    // The player's own time finishes showing first; see showFinished.
    if (phase === "finished") roundEndedWhileFinished = true;
    else setPhase("results");
  });

  // However the challenge ended, the server now answers this page's address with the
  // summary page, so reloading takes everyone there.
  socket.on("challenge_ended", () => {
    stopTicker();
    window.location.reload();
  });

  socket.on("game_error", (error) => showMessage(error.message));

  // Right after a solve (or a DNF) the player's own result fills the screen for a moment,
  // then the page moves on: to the results if the round ended meanwhile, else to waiting.
  // data-result on #finished ("time" or "dnf") lets themes show a DNF differently.
  function showFinished(timeMs) {
    setText("finished", formatTime(timeMs));
    $("finished").dataset.result = timeMs === null ? "dnf" : "time";
    $("countdown").hidden = true;
    $("solving").hidden = true;
    roundEndedWhileFinished = false;
    setPhase("finished");
    finishedTimer = setTimeout(
      () => setPhase(roundEndedWhileFinished ? "results" : "waiting"),
      FINISHED_MS,
    );
  }

  // --- player actions ------------------------------------------------------

  if (isCo) {
    $("start-form").addEventListener("submit", (event) => {
      event.preventDefault();
      socket.emit("start_round", { puzzle: $("puzzle").value });
    });
    $("end-round").addEventListener("click", () => socket.emit("end_round", {}));
    $("end-challenge").addEventListener("click", () => {
      $("end-challenge").hidden = true;
      $("end-challenge-confirm").hidden = false;
    });
    $("end-challenge-no").addEventListener("click", () => setEndChallengeVisible(true));
    $("end-challenge-yes").addEventListener("click", () => socket.emit("end_challenge", {}));
    $("share-link-button").addEventListener("click", async () => {
      const url = $("share-link").value;
      if (navigator.share) {
        try {
          await navigator.share({ title: "Scramble Challenge", text: "Join my Scramble Challenge", url });
          return;
        } catch (error) {
          // The player closed the share sheet: nothing to do.
          if (error.name === "AbortError") return;
          // Any other refusal falls back to copying, like browsers without sharing.
        }
      }
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        // No clipboard (plain http) or the browser refused, e.g. Safari after a failed share.
        $("share-link").focus();
        $("share-link").select();
        showMessage("Copy the link above to share it.");
        return;
      }
      setText("share-link-button", "Copied!");
      setTimeout(() => setText("share-link-button", "Share"), 2000);
    });
  }

  $("start-inspection").addEventListener("click", () => {
    socket.emit("start_inspection", {});
    inspectionStartedAt = performance.now();
    setHeld(false);
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
        showFinished(null);
      }
    }, 100);
  });

  // Starts the solve during inspection and stops it while solving. A finger or the spacebar
  // works it like a real cubing timer: during inspection, holding down gets ready and
  // letting go starts the solve; while solving, pressing down stops the solve at once.
  function pressTimer() {
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
      showFinished(timeMs);
    }
  }

  // While held down in inspection, data-ready on #game lets themes light the screen up.
  function setHeld(held) {
    heldInInspection = held;
    if (held) game.dataset.ready = "true";
    else delete game.dataset.ready;
  }

  function holdOrStop() {
    if (phase === "inspecting") setHeld(true);
    else pressTimer();
  }

  function letGo() {
    if (phase === "inspecting" && heldInInspection) pressTimer();
    setHeld(false);
  }

  $("overlay").addEventListener("pointerdown", holdOrStop);
  $("overlay").addEventListener("pointerup", letGo);
  // The browser took the touch over (e.g. for a gesture): no pointerup will follow.
  $("overlay").addEventListener("pointercancel", () => setHeld(false));
  // A long press on a phone would otherwise open a menu.
  $("overlay").addEventListener("contextmenu", (event) => event.preventDefault());

  // The spacebar does the same while the blank screen is showing. It must not scroll the
  // page or press a focused button, and a held key's repeats are not new presses. Space
  // with Ctrl, Alt or Meta is a shortcut (e.g. switching input language), not a press.
  function isTimerSpace(event) {
    const plain = event.code === "Space" && !event.ctrlKey && !event.altKey && !event.metaKey;
    return plain && (phase === "inspecting" || phase === "solving");
  }

  document.addEventListener("keydown", (event) => {
    if (!isTimerSpace(event)) return;
    event.preventDefault();
    if (!event.repeat) holdOrStop();
  });

  document.addEventListener("keyup", (event) => {
    if (!isTimerSpace(event)) return;
    event.preventDefault();
    letGo();
  });
})();
