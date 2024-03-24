import os
from html import escape
from locust import events
from flask import Blueprint, render_template, jsonify
import psutil


stats = {}
min_cpu = 999999999
max_cpu = 0
min_memory = 999999999
max_memory = 0
min_used_memory = 99999999999
max_used_memory = 0
path = os.path.dirname(os.path.abspath(__file__))
extend = Blueprint(
    "extend",
    "extend_web_ui",
    static_folder=f"{path}/locustfiles/static/",
    static_url_path="/extend/static/",
    template_folder=f"{path}/locustfiles/templates/",
)


@events.init.add_listener
def locust_init(environment, **kwargs):
    """
    We need somewhere to store the stats.
    On the master node stats will contain the aggregated sum of all host-metrics,
    while on the worker nodes this will be the sum of the host-metrics since the
    last stats report was sent to the master
    """
    if environment.web_ui:
        # this code is only run on the master node (the web_ui instance doesn't exist on workers)
        @extend.route("/host-metrics")
        def total_host_metrics():
            """
            Add a route to the Locust web app where we can see the total content-length for each
            endpoint Locust users are hitting. This is also used by the Content Length tab in the
            extended web UI to show the stats. See `updateStats()` and
            `renderTable()` in extend.js.
            """
            report = {"stats": []}
            if stats:
                stats_tmp = []

                for name, inner_stats in stats.items():
                    stats_tmp.append(
                        {"name": name, "safe_name": escape(name, quote=False), "percentage": inner_stats}
                    )

                    # Truncate the total number of stats and errors displayed since a large number of rows will cause the app
                    # to render extremely slowly.
                    report = {"stats": stats_tmp[:500]}
                return jsonify(report)
            return jsonify(stats)

        @extend.route("/extend")
        def extend_web_ui():
            """
            Add route to access the extended web UI with our new tab.
            """
            # ensure the template_args are up to date before using them
            environment.web_ui.update_template_args()
            return render_template("extend.html", **environment.web_ui.template_args)

        # register our new routes and extended UI with the Locust web UI
        environment.web_ui.app.register_blueprint(extend)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """
    Event handler that get triggered on every request
    """
    global min_cpu
    global max_cpu
    global min_memory
    global max_memory
    global max_used_memory
    global min_used_memory

    cpu_percentage = psutil.cpu_percent(interval=1)
    if cpu_percentage > max_cpu:
        max_cpu = cpu_percentage
    if cpu_percentage < min_cpu:
        min_cpu = cpu_percentage

    # root_request = requests.get('http://0.0.0.0:8282/').json()
    # memory_precentage = root_request["memory_precentage"]
    # memory_used = root_request["memory_usage"]
    # if memory_precentage > max_memory:
    #     max_memory = memory_precentage
    # if memory_precentage < min_memory:
    #     min_memory = memory_precentage

    # if memory_used > max_used_memory:
    #     max_used_memory = memory_used
    # if memory_used < min_used_memory:
    #     min_used_memory = memory_used
    
    stats["CPU_PERCENTAGE"] = cpu_percentage
    stats["CPU_MAX"] = max_cpu
    stats["CPU_MIN"] = min_cpu
    stats["MEMORY_PERCENTAGE"] = 0
    stats["MEMORY_USED"] = 0
    stats["MEMORY_PERCENTAGE_MAX"] = max_memory
    stats["MEMORY_PERCENTAGE_MIN"] = min_memory
    stats["MEMORY_USED_MAX"] = max_used_memory
    stats["MEMORY_USED_MIN"] = min_used_memory


@events.reset_stats.add_listener
def on_reset_stats():
    """
    Event handler that get triggered on click of web UI Reset Stats button
    """
    global stats
    global min_cpu
    global max_cpu
    global min_memory
    global max_memory
    global min_used_memory
    global max_used_memory
    stats = {}
    min_cpu = 999999999
    max_cpu = 0
    min_memory = 999999999
    max_memory = 0
    min_used_memory = 99999999999
    max_used_memory = 0
