<script>

  import PYTest from "./assets/pytest.png";

</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

## **Automated Testing using Pytest**

---

**Introduction**

Automated testing is a critical aspect of software development, ensuring that changes to code do not inadvertently introduce bugs or regressions. Pytest is a widely-used testing framework for Python that allows developers to write simple and scalable tests. This documentation provides guidelines and examples for automated testing using Pytest in the context of a FastAPI application.

**Setting Up**

Before writing tests, ensure that your environment is properly configured for testing. You will need:

- Python environment with Pytest installed

- FastAPI application with appropriate endpoints

- Test client for making HTTP requests to the FastAPI application

- Redis and plugin manager configurations (if applicable)

**Writing Tests**

Pytest follows a simple syntax for writing tests, using functions prefixed with `test_`. These functions contain assertions that verify the expected behavior of your code.

**Example Test File Structure**

```python

# test_myapp.py

import json
from fastapi.testclient import TestClient
from main import app
from utils.redis_services import RedisServices
from utils.plugin_manager import plugin_manager
from utils.settings import settings
from fastapi import status
from models.api import Query
from models.enums import QueryType, ResourceType

client = TestClient(app)

# Test cases go here...

```

**Example Test Functions**

```python
def test_set_superman_cookie():
    response = client.post("/set_superman_cookie")
    assert response.status_code == status.HTTP_200_OK
    assert response.cookies.get("superman") is not None

def test_set_alibaba_cookie():
    response = client.post("/set_alibaba_cookie")
    assert response.status_code == status.HTTP_200_OK
    assert response.cookies.get("alibaba") is not None

def test_init_test_db():
    response = client.post("/init_test_db")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"status": "success"}
```

**Test Setup and Teardown**

Pytest allows you to define setup and teardown functions using fixtures. These functions run before and after each test function, respectively.

```python

import pytest

@pytest.fixture(autouse=True)
def setup():
    # Setup logic goes here...
    yield
    # Teardown logic goes here...


```

**Example Assertion Functions**

Pytest provides various assertion functions to validate test outcomes. Some common assertions include:

- `assert response.status_code == 200`: Verify HTTP status code

- `assert response.json()['status'] == 'success'`: Verify JSON response attributes

- `assert 'error' not in response.json()`: Verify absence of errors

**Running Tests**

To run tests using Pytest, navigate to the directory containing your test files and run the following command:

```bash
pytest

```

Pytest will automatically discover and execute all test functions within the directory.

<img class="center" src={PYTest} width="450">
