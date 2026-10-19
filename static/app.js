document.addEventListener("DOMContentLoaded", () => {
  const kindSelect = document.getElementById("kind");
  const categorySelect = document.getElementById("category");

  if (kindSelect && categorySelect) {
    const options = {
      expense: ["Food", "Transport", "Shopping", "Bills", "Health", "Education", "Entertainment", "Other"],
      income: ["Salary", "Allowance", "Freelance", "Gift", "Other"]
    };
    const refreshCategories = () => {
      const selected = categorySelect.value;
      categorySelect.replaceChildren();
      options[kindSelect.value].forEach((category) => {
        const option = document.createElement("option");
        option.value = category;
        option.textContent = category;
        categorySelect.appendChild(option);
      });
      if (options[kindSelect.value].includes(selected)) categorySelect.value = selected;
    };
    kindSelect.addEventListener("change", refreshCategories);
    refreshCategories();
  }

  const dataElement = document.getElementById("chart-data");
  if (!dataElement || typeof Chart === "undefined") return;

  const data = JSON.parse(dataElement.textContent);
  const categoryCanvas = document.getElementById("categoryChart");
  const categoryEmpty = document.getElementById("categoryEmpty");
  const monthlyCanvas = document.getElementById("monthlyChart");
  const monthlyEmpty = document.getElementById("monthlyEmpty");

  if (categoryCanvas && data.categories.length) {
    new Chart(categoryCanvas, {
      type: "doughnut",
      data: {
        labels: data.categories.map(item => item.label),
        datasets: [{
          data: data.categories.map(item => item.value),
          backgroundColor: ["#6ee7b7", "#60a5fa", "#c4b5fd", "#fbbf24", "#fb7185", "#67e8f9", "#a3e635", "#fdba74"],
          borderColor: "#171b24",
          borderWidth: 4,
          hoverOffset: 7
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: { position: "bottom", labels: { color: "#a5adbd", padding: 16, usePointStyle: true, pointStyle: "circle" } },
          tooltip: { callbacks: { label: context => ` ${context.label}: ₹${Number(context.raw).toLocaleString("en-IN", {minimumFractionDigits: 2})}` } }
        }
      }
    });
  } else if (categoryEmpty) {
    categoryCanvas.hidden = true;
    categoryEmpty.hidden = false;
  }

  if (monthlyCanvas && data.monthly.length) {
    const labels = data.monthly.map(item => {
      const [year, month] = item.month.split("-");
      return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
    });
    new Chart(monthlyCanvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Income", data: data.monthly.map(item => item.income), backgroundColor: "#6ee7b7", borderRadius: 5 },
          { label: "Expenses", data: data.monthly.map(item => item.expenses), backgroundColor: "#fb7185", borderRadius: 5 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: "#a5adbd" }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { color: "#a5adbd", callback: value => "₹" + Number(value).toLocaleString("en-IN") }, grid: { color: "#2b303c" } }
        },
        plugins: {
          legend: { labels: { color: "#a5adbd", usePointStyle: true, pointStyle: "circle", padding: 18 } },
          tooltip: { callbacks: { label: context => ` ${context.dataset.label}: ₹${Number(context.raw).toLocaleString("en-IN", {minimumFractionDigits: 2})}` } }
        }
      }
    });
  } else if (monthlyEmpty) {
    monthlyCanvas.hidden = true;
    monthlyEmpty.hidden = false;
  }
});
