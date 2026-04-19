let chart = null;

async function loadSessions() {
    const res = await fetch("/api/sessions");
    const sessions = await res.json();

    const tbody = document.querySelector("#sessionTable tbody");
    tbody.innerHTML = "";

    sessions.forEach(s => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${s.id}</td>
            <td>${s.start}</td>
            <td>${s.end ? s.end : "Running"}</td>
            <td><button onclick="loadSessionGraph(${s.id})">View Analytics</button></td>
        `;
        tbody.appendChild(row);
    });
}

// async function loadSessionGraph(sessionId) {
//     const res = await fetch(`/api/perclos/session/${sessionId}`);
//     const data = await res.json();

//     const labels = data.map(d => d.time);
//     const values = data.map(d => d.perclos);

//     const ctx = document.getElementById("perclosChart").getContext("2d");

//     // Create a subtle gradient for the line
//     const gradient = ctx.createLinearGradient(0, 0, 0, 400);
//     gradient.addColorStop(0, 'rgba(45, 108, 223, 0.5)');
//     gradient.addColorStop(1, 'rgba(45, 108, 223, 0)');

//     if (chart) {
//         chart.destroy();
//     }

//     chart = new Chart(ctx, {
//         type: "line",
//         data: {
//             labels: labels,
//             datasets: [{
//                 label: "Driver Fatigue Level",
//                 data: values,
//                 borderColor: "#60a5fa", 
//                 borderWidth: 3,
//                 tension: 0.4,
//                 fill: true,
//                 // This creates a "Glow" effect under the line
//                 backgroundColor: 'rgba(96, 165, 250, 0.1)', 
//                 pointRadius: 5,
//                 pointBackgroundColor: (context) => {
//                     const val = context.raw;
//                     return val > 0.7 ? '#ef4444' : '#60a5fa'; // Red dots for danger
//                 }
//             }]
//         },
//         options: {
//             responsive: true,
//             maintainAspectRatio: false,
//             plugins: {
//                 legend: { display: false }, // Hide legend to save space
//                 tooltip: {
//                     callbacks: {
//                         label: function(context) {
//                             let status = context.raw > 0.7 ? "🚨 DANGER" : (context.raw > 0.3 ? "⚠️ DROWSY" : "✅ ALERT");
//                             return `Fatigue: ${context.raw.toFixed(2)} (${status})`;
//                         }
//                     }
//                 }
//             },
//             scales: {
//                 y: { 
//                     min: 0, 
//                     max: 1,
//                     title: { display: true, text: 'Fatigue Severity', color: '#94a3b8' },
//                     grid: {
//                         // Create a bright line at the "Danger" threshold
//                         color: (context) => context.tick.value === 0.7 ? 'rgba(239, 68, 68, 0.5)' : 'rgba(255, 255, 255, 0.05)',
//                         lineWidth: (context) => context.tick.value === 0.7 ? 2 : 1
//                     },
//                     ticks: {
//                         color: '#94a3b8',
//                         callback: function(value) {
//                             if (value === 0.8) return "DANGER";
//                             if (value === 0.5) return "DROWSY";
//                             if (value === 0.2) return "ALERT";
//                             return "";
//                         }
//                     }
//                 },
//                 x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
//             }
//         }
//     });
// }

async function loadSessionGraph(sessionId) {
    const res = await fetch(`/api/perclos/session/${sessionId}`);
    const data = await res.json();

    if (data.length === 0) return;

    const labels = data.map(d => d.time);
    const values = data.map(d => d.perclos);

    // --- CALCULATE QUICK STATS ---
    
    // 1. Total Duration (Difference between first and last timestamp)
    const startTime = new Date(labels[0]);
    const endTime = new Date(labels[labels.length - 1]);
    const diffMs = endTime - startTime;
    const diffMins = Math.floor(diffMs / 60000);
    const diffSecs = Math.floor((diffMs % 60000) / 1000);
    document.getElementById("totalTime").innerText = `${diffMins}m ${diffSecs}s`;

    // 2. Fatigue Peaks (Count how many times PERCLOS > 0.7)
    const peaks = values.filter(v => v > 0.7).length;
    document.getElementById("peakCount").innerText = peaks;

    // 3. Avg Alertness (100% - Average PERCLOS %)
    const avgPerclos = values.reduce((a, b) => a + b, 0) / values.length;
    const alertness = Math.round((1 - avgPerclos) * 100);
    document.getElementById("avgScore").innerText = `${alertness}%`;

    // --- RENDER THE CHART (Same as before) ---
    const ctx = document.getElementById("perclosChart").getContext("2d");
    if (chart) { chart.destroy(); }

    chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Fatigue Level",
                data: values,
                borderColor: "#60a5fa",
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                backgroundColor: 'rgba(96, 165, 250, 0.1)',
                pointBackgroundColor: (c) => c.raw > 0.7 ? '#ef4444' : '#60a5fa'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { 
                    min: 0, max: 1,
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                x: { ticks: { color: '#94a3b8' }, grid: { display: false } }
            }
        }
    });
}

window.onload = () => {
    loadSessions();
};