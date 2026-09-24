// Bare socket client for step 3: enough to play a round. The real screens come in step 4.
(function () {
  const game = document.getElementById("game");
  const slug = game.dataset.slug;
  const isCo = game.dataset.isCo === "true";
  const $ = (id) => document.getElementById(id);
  const show = (id, visible) => { const el = $(id); if (el) el.hidden = !visible; };
  const socket = io();

  let phase = "idle"; // idle -> inspecting -> solving -> done
  let solveStartedAt = 0;
  let countdownTimer = null;

  function formatTime(ms) {
    return ms === null ? "DNF" : (ms / 1000).toFixed(2);
  }

  function renderResults(results) {
    $("leaderboard").innerHTML = "";
    for (const r of results) {
      const li = document.createElement("li");
      li.textContent = `${r.position}. ${r.display_name}: ${formatTime(r.time_ms)}`;
      $("leaderboard").appendChild(li);
    }
  }

  socket.on("connect", () => socket.emit("join_challenge", { challenge_slug: slug }));

  socket.on("player_list", (players) => {
    $("players").innerHTML = "";
    for (const p of players) {
      const li = document.createElement("li");
      li.textContent = p.display_name + (p.is_co ? " (owner)" : "") + (p.connected ? "" : " (away)");
      $("players").appendChild(li);
    }
  });

  socket.on("round_started", (round) => {
    phase = "idle";
    $("round-number").textContent = round.round_number;
    $("scramble-text").textContent = round.scramble_text;
    $("scramble-image").src = round.scramble_svg_url;
    renderResults([]);
    show("lobby", false);
    show("scramble", true);
    show("results", false);
    show("end-round", true);
  });

  socket.on("leaderboard_update", (update) => renderResults(update.results));

  socket.on("round_complete", (update) => {
    renderResults(update.results);
    phase = "done";
    show("overlay", false);
    show("scramble", false);
    show("results", true);
    show("lobby", true);
    show("end-round", false);
  });

  socket.on("challenge_ended", () => {
    $("message").textContent = "The challenge owner has left, so this challenge has ended.";
    show("lobby", false);
    show("scramble", false);
  });

  socket.on("game_error", (error) => { $("message").textContent = error.message; });

  if (isCo) {
    $("start-form").addEventListener("submit", (event) => {
      event.preventDefault();
      socket.emit("start_round", { puzzle: $("puzzle").value });
    });
    $("end-round").addEventListener("click", () => socket.emit("end_round", {}));
  }

  $("start-inspection").addEventListener("click", () => {
    phase = "inspecting";
    socket.emit("start_inspection", {});
    let remaining = 15;
    $("countdown").textContent = remaining;
    show("overlay", true);
    countdownTimer = setInterval(() => {
      remaining -= 1;
      $("countdown").textContent = remaining;
    }, 1000);
  });

  // A press anywhere on the blank screen starts, then stops, the solve.
  $("overlay").addEventListener("pointerdown", () => {
    if (phase === "inspecting") {
      clearInterval(countdownTimer);
      phase = "solving";
      solveStartedAt = performance.now();
      $("countdown").textContent = "Solving…";
      socket.emit("start_solve", {});
    } else if (phase === "solving") {
      phase = "done";
      socket.emit("stop_solve", { time_ms: Math.max(1, Math.round(performance.now() - solveStartedAt)) });
      show("overlay", false);
      show("scramble", false);
      show("results", true);
    }
  });
})();
