## Automated Testing Documentation

**Introduction**

Automated testing is a crucial practice in software development that involves using tools and scripts to automatically execute test cases, validate software functionality, and detect defects early in the development process. This documentation provides an overview of different types of automated testing, including

1. [Unit testing with Pytest](Automated-Testing-Pytest,md)
2. [Load testing with Locust](Automated-Load-Testing.md)
3. [API testing with cURL.](curl-sh.md)

**1. Unit Testing with Pytest**

**What is Pytest?**
Pytest is a widely used testing framework for writing simple and scalable test cases in Python. It provides easy-to-use syntax and powerful features for writing and executing tests.

**Writing Unit Tests with Pytest**

To write unit tests with pytest, follow these steps:

1. Install pytest:

bash

     pip install pytest

2.  Write test functions using the assert statement to verify expected outcomes.
3.  Save the test functions in files prefixed with test\_ or suffixed with \_test.py.
4.  Run pytest in the terminal to execute the tests:

bash

    pytest

Example:

python

    # test_math_functions.py

    def test_addition():
        assert 2 + 2 == 4

    def test_subtraction():
        assert 5 - 3 == 2

**2. Load Testing with Locust**

**What is Locust?**
Locust is an open-source load testing tool written in Python. It allows you to define user behavior as code and simulate thousands of concurrent users to test the performance of your web applications.
Writing Load Tests with Locust

To write load tests with Locust, follow these steps:

1. Install Locust:

bash

    pip install locust

2. Define user behavior as tasks within a Python class subclassed from HttpUser.

3. Run Locust in the terminal:

bash

    locust -f my_load_test.py

4. Access the Locust web interface to configure the number of users and hatch rate, then start the test.

**Example:**

python

    # my_load_test.py

    from locust import HttpUser, between, task

    class MyUser(HttpUser):
        wait_time = between(1, 2)

        @task
        def my_task(self):
            self.client.get("/my-endpoint")

**3. API Testing with cURL**

**What is cURL?**
cURL is a command-line tool for transferring data using various protocols. It is commonly used for testing APIs by sending HTTP requests and inspecting responses.

**Writing API Tests with cURL**
To write API tests with cURL, follow these steps:

1. Construct HTTP requests using cURL commands in the terminal.

2. Send requests to API endpoints and analyze the responses.

**Example:**

bash

    # Send a GET request to retrieve user data
    curl http://api.example.com/users/123

    # Send a POST request to create a new user
    curl -X POST -H "Content-Type: application/json" -d '{"username": "john", "email": "john@example.com"}' http://api.example.com/users
