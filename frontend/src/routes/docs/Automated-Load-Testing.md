### **Automated Load Testing**

---

**Introduction**

Load testing is a crucial aspect of performance testing in software development, ensuring that the application can handle a certain level of traffic without performance degradation. Locust is a popular open-source load testing tool written in Python that allows you to define user behavior as code. Here is a brief description for automated load testing using Locust .

**Setting Up**

Before writing load tests, ensure that you have Locust installed in your Python environment. You can install Locust via pip:

```bash
pip  install  locust

```

**Getting Started with Locust:**

1.  **Installation:** Use pip to install Locust: `pip install locust`

2.  **Running the Test:** Run the command `locust` in your terminal `path_to/dmart/backend` to launch the Locust web UI, ande run : `locust` as command line, then open: `0.0.0.0:8089` on your browser.

3.  **Web UI Interaction:** Within the web UI, configure your test parameters (number of users, duration) and initiate the load test.

4.  **Analyzing Results:** After running the test, Locust generates reports with detailed performance metrics for analysis.

**Additional Resources:**

- Locust Documentation: [https://docs.locust.io/](https://docs.locust.io/)

- Locust Examples: [https://docs.locust.io/](https://docs.locust.io/)

**Writing Load Tests**

Locust allows you to define user behavior as tasks within a Python class. These tasks simulate user actions, such as making HTTP requests to your application endpoints. Here's an example of a Locust test file:

```python
# my_load_test.py

import time
from locust import HttpUser, between, task

class  MyUser(HttpUser):
wait_time = between(1, 2)

@task
def  my_task(self):
self.client.get("/my-endpoint")

```

In the above example, `MyUser` is a subclass of `HttpUser`, representing a virtual user. The `wait_time` attribute defines the wait time between each task execution. The `@task` decorator defines a user task, which in this case is making a GET request to the `/my-endpoint` endpoint.

You can define multiple tasks within the user class to simulate various user behaviors.

**Running Load Tests**

To run load tests using Locust, navigate to the directory containing your test file and run the following command:

```bash
locust  -f  my_load_test.py
```

This will start the Locust web interface on `http://localhost:8089`, where you can specify the number of users to simulate and the hatch rate (i.e., how quickly users are spawned). Once you start the test, Locust will distribute user tasks across available workers and measure the performance of your application.

**Dmart Load Testing with vegeta.sh**

This document provides a comprehensive explanation of the `vegeta.sh` script for load testing specific functionalities within Dmart's internal systems.

**What is Vegeta?**

Vegeta is a powerful open-source tool written in Go for load testing HTTP APIs and protocols. It allows you to define attack patterns that simulate realistic user behavior by creating scenarios with various HTTP requests.

**Vegeta.sh**

The `vegeta.sh` script leverages Vegeta to perform load testing on specific functionalities within your Dmart's internal systems .

**How to use vegeta.sh?**

1.Install vegete tool

2.Go to /dmart/backend/loadtest path and run : `./vegeta.sh` make sure your dmart server is runig

You can edit ./vegeta file in order to get a test that is more suitable for your case..

**Dmart Load Testing with abtests.sh**

This document provides a comprehensive explanation of the `abtests.sh` script for load testing functionalities within Dmart's internal systems using the Apache Benchmark (ab) tool.

**What is Apache Benchmark (ab)?**
Ab is a command-line tool included with the Apache HTTP Server package. It allows you to perform basic load testing by simulating concurrent HTTP requests to a web server.

**Script Functionality :**

The `abtests.sh` script leverages `ab` to perform load testing on specific functionalities within Dmart's internal systems (the exact functionalities will depend on your Dmart IT team's configuration). Here's a breakdown of the script's functionalities :

1.  **ab Availability Check:** Ensures `ab` is installed and accessible. Provides download instructions if not found.

2.  **Three Load Tests:** The script defines three separate `ab` commands to execute load tests against Dmart's internal API:

- **Test 1:** Targets the base URL `http://0.0.0.0:8282/` with the following options:

- `-l`: Enables detailed results output.

- `-c 500`: Simulates 500 concurrent requests.

- `-n 10000`: Executes a total of 10000 requests.

- **Test 2:** Targets the URL `http://0.0.0.0:8282/public/entry/folder/applications/api/user?retrieve_json_payload=true` with the same options as Test 1. (Consult Dmart IT for the specific API endpoint functionality).

- **Test 3:** Targets the URL `http://0.0.0.0:8282/public/query` with the following options:

- `-l`: Enables detailed results output.

- `-p query_ab.json`: Reads additional data for the request from the `query_ab.json` file (consult Dmart IT for its content and purpose).

- `-T application/json`: Sets the request content type to JSON.

- `-c 500`: Simulates 500 concurrent requests.

- `-n 10000`: Executes a total of 10000 requests.

**Dmart's Load Testing Tools (Summary)**

This summary provides an overview of three load testing tools utilized within Dmart's internal environment:

- **vegeta.sh**: This script leverages the Vegeta tool for advanced load testing scenarios. It allows defining attack patterns that simulate
  realistic user behavior by creating scenarios with various HTTP requests. Collaboration with your Dmart IT team is crucial to understand the targeted API endpoints, user actions simulated, and the role of referenced JSON files within the script.

- **abtests.sh**: This script utilizes the Apache Benchmark (ab) tool for basic load testing. It defines three separate tests that simulate
  concurrent HTTP requests against specific Dmart internal API endpoints. Consult with your Dmart IT team to comprehend the functionalities of
  each test and the purpose of the query_ab.json file used in one of the tests.

- **locustfile.py**: This Python script leverages the Locust library for comprehensive load testing. It allows defining user classes and
  tasks, enabling the creation of virtual users that interact with Dmart's systems concurrently. You can define realistic user behavior
  patterns within the script.
