var hostMetricsStats;
var hostMetricsCharts = {};

// Used for sorting
var hostMetricsDesc = false;
var hostMetricsSortAttribute = "name";

// Trigger sorting of stats when a table label is clicked
$("#host-metrics .stats_label").click(function (event) {
    event.preventDefault();
    hostMetricsSortAttribute = $(this).attr("data-sortkey");
    hostMetricsDesc = !hostMetricsDesc;
    renderHostMetricsTable(window.hots_metrics_report);
});

// Render and sort Content Length table
function renderHostMetricsTable(hots_metrics_report) {
    $('#host-metrics tbody').empty();

    window.alternate = false;
    $('#host-metrics tbody').jqoteapp($('#host-metrics-template'), (hots_metrics_report.stats).sort(sortBy(hostMetricsSortAttribute, hostMetricsDesc)));
}

// Get and repeatedly update Content Length stats and table
function updateHostMetricsStats() {
    $.get('./host-metrics', function (hots_metrics_report) {
        console.log("TRIGGERED, RES: ", JSON.stringify(hots_metrics_report))
        window.hots_metrics_report = hots_metrics_report
        $('#host-metrics tbody').empty();

        if (JSON.stringify(hots_metrics_report) !== JSON.stringify({})) {
            renderHostMetricsTable(hots_metrics_report);

            // Make a separate chart for each URL
            chart_stats = ["CPU_PERCENTAGE", "MEMORY_PERCENTAGE", "MEMORY_USED"]

            for (let index = 0; index < hots_metrics_report.stats.length; index++) {
                const url_stats = hots_metrics_report.stats[index];
                if(chart_stats.indexOf(url_stats.safe_name) > -1) {
                    // If a chart already exists, just add the new value
                    if (hostMetricsCharts.hasOwnProperty(url_stats.safe_name)) {
                        hostMetricsCharts[url_stats.safe_name].addValue([url_stats.percentage]);
                    } else {
                        // If a chart doesn't already exist, create the chart first then add the value
                        hostMetricsCharts[url_stats.safe_name] = new LocustLineChart($(".charts-container"), `Chart for ${url_stats.safe_name}`, ["host-metrics"], "bytes");
                        // Add newly created chart to Locust web UI's array of charts
                        charts.push(hostMetricsCharts[url_stats.safe_name])
                        hostMetricsCharts[url_stats.safe_name].addValue([url_stats.percentage]);
                    }
                }
            }
        }
        // Schedule a repeat of updating stats in 2 seconds
        setTimeout(updateHostMetricsStats, 1000);
    });
}

updateHostMetricsStats();