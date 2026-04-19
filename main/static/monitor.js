let liveTimer = null;
let isMonitoring = false;
const video = document.createElement('video');
const canvas = document.createElement('canvas');
const context = canvas.getContext('2d');

// Audio Context for the alert sound (since winsound is gone)
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playAlertSound() {
    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(1000, audioCtx.currentTime);
    gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
    oscillator.start();
    oscillator.stop(audioCtx.currentTime + 0.2);
}

async function startMonitoring() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        await video.play();
        
        await fetch("/start", { method: "POST" });
        
        if (audioCtx.state === 'suspended') audioCtx.resume();
        
        isMonitoring = true;
        sendFrameToServer(); 

        // --- DYNAMIC RETRY LOGIC ---
        const checkReady = setInterval(async () => {
            const res = await fetch("/api/live");
            const data = await res.json();
            
            // If EAR > 0, the server has processed at least one frame!
            if (data.ear > 0) {
                const videoFeed = document.getElementById("videoFeed");
                videoFeed.src = "/video_feed?t=" + new Date().getTime();
                clearInterval(checkReady); // Stop checking once displayed
                console.log("Feed synchronized successfully.");
            }
        }, 1000); // Check every 1 second

        if (!liveTimer) {
            liveTimer = setInterval(updateLiveValues, 500);
        }
    } catch (err) {
        alert("Camera access denied: " + err);
    }
}
async function sendFrameToServer() {
    if (!isMonitoring) return;

    // Draw the current video frame to our hidden canvas
    canvas.width = 640;
    canvas.height = 480;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to a small JPEG blob to keep it fast
    canvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append("file", blob, "frame.jpg");

        try {
            await fetch("/api/process", {
                method: "POST",
                body: formData
            });
        } catch (e) {
            console.error("Network lag, skipping frame...");
        }

        // Loop using requestAnimationFrame for smoothness
        if (isMonitoring) {
            requestAnimationFrame(sendFrameToServer);
        }
    }, "image/jpeg", 0.4); // 0.4 quality is plenty for EAR detection
}

async function stopMonitoring() {
    isMonitoring = false;
    
    // Stop the actual webcam hardware
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
    }

    const res = await fetch("/stop", { method: "POST" });
    const data = await res.json();
    console.log(data.message);

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
    
    const statusVal = document.getElementById("statusValue");
    statusVal.innerText = data.drowsy ? "DROWSY" : "Normal";
    statusVal.style.color = data.drowsy ? "red" : "white";

    document.getElementById('earBar').style.width = Math.min(data.ear * 200, 100) + "%";
    document.getElementById('perclosBar').style.width = (data.perclos * 100) + "%";

    if (data.drowsy) {
        playAlertSound();
    }
}

async function toggleLandmarks() {
    const enabled = document.getElementById("landmarkToggle").checked;
    await fetch("/api/overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
    });
}