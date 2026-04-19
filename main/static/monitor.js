let liveTimer = null;

async function startMonitoring() {
    const res = await fetch("/start", { method: "POST" });
    const data = await res.json();
    alert(data.message);

    document.getElementById("videoFeed").src = "/video_feed";

    if (!liveTimer) {
        liveTimer = setInterval(updateLiveValues, 500);
    }
}

async function stopMonitoring() {
    const res = await fetch("/stop", { method: "POST" });
    const data = await res.json();
    alert(data.message);

    document.getElementById("videoFeed").src = "";

    if (liveTimer) {
        clearInterval(liveTimer);
        liveTimer = null;
    }
}

async function updateLiveValues() {
    const res = await fetch("/api/live");
    const data = await res.json();

    document.getElementById("earValue").innerText = data.ear.toFixed(3);
    document.getElementById("perclosValue").innerText = data.perclos.toFixed(3);
    document.getElementById("fpsValue").innerText = data.fps;
    document.getElementById("statusValue").innerText = data.drowsy ? "DROWSY" : "Normal";

    // Inside your function that updates the UI:

    document.getElementById('earBar').style.width = (data.ear * 200) + "%"; // Scale for visual
    document.getElementById('perclosBar').style.width = (data.perclos * 100) + "%";
}

async function toggleLandmarks() {
    const enabled = document.getElementById("landmarkToggle").checked;

    await fetch("/api/overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
    });
}