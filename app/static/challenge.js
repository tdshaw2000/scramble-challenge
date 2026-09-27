// Challenge page client: talks to the server over Socket.IO and switches screens.
// Presentation lives entirely in the theme CSS: this file only shows/hides elements
// (the `hidden` attribute), sets text, and sets data-phase on #game and data-puzzle on
// #scramble for themes to use.
(function () {
  "use strict";

  // WCA inspection: 15 seconds, then 2 more in which starting costs 2 seconds (a +2).
  // After 17 seconds the attempt is a DNF.
  const INSPECTION_SECONDS = 15;
  const INSPECTION_LIMIT_MS = 17000;
  const PLUS_TWO_MS = 2000;
  // How long the player's own time (or DNF) fills the screen after they finish.
  const FINISHED_MS = 1000;

  // A +2 time is shown WCA-style with the penalty already added and a "+" after it: 12.34+.
  function formatTime(ms, plusTwo = false) {
    if (ms === null || ms === undefined) return "DNF";
    // Truncate to hundredths like WCA results: 12.349 shows as 12.34, never rounded up.
    // Whole-number maths only, so floating point can't nudge a time across a boundary.
    const hundredths = Math.floor(ms / 10);
    const minutes = Math.floor(hundredths / 6000);
    const rest = hundredths % 6000;
    const seconds = `${Math.floor(rest / 100)}.${String(rest % 100).padStart(2, "0")}`;
    const shown = minutes > 0 ? `${minutes}:${seconds.padStart(5, "0")}` : seconds;
    return plusTwo ? `${shown}+` : shown;
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
  let plusTwo = false; // this solve started between 15 and 17 seconds into inspection
  let finishedTimer = null;
  let roundEndedWhileFinished = false;
  let roundLive = false;
  let wakeLock = null; // the screen lock held, or a marker while one is being asked for

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
        element("span", "time", formatTime(r.time_ms, r.plus_two)),
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

  // Keeps the phone's screen from dimming while a round is on, where the browser allows it
  // (the Screen Wake Lock API). Browsers drop the lock whenever the page is hidden, so it is
  // asked for again on coming back. Old phones and battery saver just dim as before.
  async function keepScreenAwake() {
    if (!roundLive || !navigator.wakeLock || document.visibilityState !== "visible") return;
    if (wakeLock) return;
    const asking = {};
    wakeLock = asking;
    let lock = null;
    try {
      lock = await navigator.wakeLock.request("screen");
    } catch {
      // Refused: nothing to do, the screen may dim.
    }
    if (wakeLock !== asking) {
      // The round ended while asking.
      if (lock) lock.release().catch(() => {});
      return;
    }
    wakeLock = lock;
    if (lock) lock.addEventListener("release", () => {
      if (wakeLock === lock) wakeLock = null;
    });
  }

  function letScreenSleep() {
    const lock = wakeLock;
    wakeLock = null;
    if (lock && lock.release) lock.release().catch(() => {});
  }

  function setRoundLive(live) {
    roundLive = live;
    if (live) keepScreenAwake();
    else letScreenSleep();
  }

  document.addEventListener("visibilitychange", keepScreenAwake);

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
    setRoundLive(true);
  });

  socket.on("leaderboard_update", (update) => renderResults(update.results));

  socket.on("round_complete", (update) => {
    stopTicker();
    setRoundLive(false);
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
    setRoundLive(false);
    window.location.reload();
  });

  socket.on("game_error", (error) => showMessage(error.message));

  // Right after a solve (or a DNF) the player's own result fills the screen for a moment,
  // then the page moves on: to the results if the round ended meanwhile, else to waiting.
  // data-result on #finished ("time" or "dnf") lets themes show a DNF differently.
  function showFinished(timeMs, plusTwo = false) {
    setText("finished", formatTime(timeMs, plusTwo));
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
    $("qr-button").addEventListener("click", () => $("qr-dialog").showModal());
    $("qr-dialog").addEventListener("click", (event) => {
      // Taps on the backdrop also target the dialog, so tell them apart by position.
      const box = $("qr-dialog").getBoundingClientRect();
      const inside = event.clientX >= box.left && event.clientX <= box.right
        && event.clientY >= box.top && event.clientY <= box.bottom;
      if (!inside) $("qr-dialog").close();
    });
    $("share-link-button").addEventListener("click", async () => {
      const url = $("share-link-button").dataset.url;
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
        showMessage(`Copy this link to share it: ${url}`);
        return;
      }
      setText("share-link-button", "Copied!");
      setTimeout(() => setText("share-link-button", "Share URL"), 2000);
    });
  }

  $("start-inspection").addEventListener("click", () => {
    socket.emit("start_inspection", {});
    // If the screen lock was refused when the round started, ask again from this tap.
    keepScreenAwake();
    inspectionStartedAt = performance.now();
    setHeld(false);
    setText("countdown", INSPECTION_SECONDS);
    $("countdown").hidden = false;
    $("solving").hidden = true;
    setPhase("inspecting");
    ticker = setInterval(() => {
      const elapsed = inspectionElapsed();
      if (elapsed >= INSPECTION_LIMIT_MS) {
        inspectionRanOut();
        return;
      }
      // Counts down 15 to 1, then shows "+2" for the two seconds that cost a +2.
      const remaining = INSPECTION_SECONDS - Math.floor(elapsed / 1000);
      setText("countdown", remaining > 0 ? remaining : "+2");
    }, 100);
  });

  function inspectionElapsed() {
    return performance.now() - inspectionStartedAt;
  }

  function inspectionRanOut() {
    stopTicker();
    socket.emit("inspection_expired", {});
    showMessage("Inspection ran out: DNF.");
    showFinished(null);
  }

  // Starts the solve during inspection and stops it while solving. A finger or the spacebar
  // works it like a real cubing timer: during inspection, holding down gets ready and
  // letting go starts the solve; while solving, pressing down stops the solve at once.
  function pressTimer() {
    if (phase === "inspecting") {
      const elapsed = inspectionElapsed();
      // The ticker only looks every 100 ms, so a start just after 17 seconds lands here.
      if (elapsed >= INSPECTION_LIMIT_MS) {
        inspectionRanOut();
        return;
      }
      stopTicker();
      plusTwo = elapsed >= INSPECTION_SECONDS * 1000;
      solveStartedAt = performance.now();
      socket.emit("start_solve", { plus_two: plusTwo });
      setText("countdown", "");
      $("countdown").hidden = true;
      $("solving").hidden = false;
      setPhase("solving");
    } else if (phase === "solving") {
      const timeMs = Math.max(1, Math.round(performance.now() - solveStartedAt));
      socket.emit("stop_solve", { time_ms: timeMs });
      showFinished(plusTwo ? timeMs + PLUS_TWO_MS : timeMs, plusTwo);
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
  // Nor should a press start selecting the text (the themes also forbid it in CSS).
  $("overlay").addEventListener("selectstart", (event) => event.preventDefault());

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
