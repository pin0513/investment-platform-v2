// Helpers used by templates
window.IPV2 = {
  // Build a donut chart from a "by-X" breakdown array
  donut(canvasId, dataAttr) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    const raw = el.dataset[dataAttr];
    if (!raw) return;
    const data = JSON.parse(raw);
    new Chart(el.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: data.map(d => d.label),
        datasets: [{
          data: data.map(d => Number(d.value)),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        cutout: '60%',
      },
    });
  },
};
