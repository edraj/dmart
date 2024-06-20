<script>
  import CLITest from "./assets/curl-test.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

### **Automated Testing using curl.sh**

---

**Overview:**
Automated testing is an essential practice in modern software development workflows to ensure the reliability, functionality, and performance of applications. In the context of APIs and web services, automated testing involves systematically sending requests to API endpoints and verifying the responses against expected outcomes. The curl.sh script provided here exemplifies an approach to automated testing using the cURL command-line tool, a powerful utility for making HTTP requests.

**Script Description:**

The curl.sh script is a Bash script designed to automate the testing of various API endpoints exposed by a web service. It utilizes the cURL command-line tool to send HTTP requests and capture responses, along with parsing and validation using tools like jq. The script is organized into multiple sections, each targeting specific API endpoints or functionalities.

**Key Features:**

**API URL Configuration:** The script allows for easy configuration of the target API URL, making it adaptable to different environments.

**Authentication Handling:** It demonstrates handling authentication mechanisms, such as token-based authentication, by extracting authentication tokens from the response headers.

**Request Composition:** Requests are composed using JSON payloads and sent with appropriate headers, such as Content-Type and Authorization.

**Response Validation:** The script validates response status codes and content using jq and standard Bash utilities, ensuring the API behaves as expected.

**Error Handling:** Error handling mechanisms are in place to capture and handle errors during request execution, preventing script termination and providing informative output.

**Usage:**

To use the curl.sh script:

- Set the appropriate values for API_URL, CT, and other variables
  according to your API configuration.
- Ensure that any dependent scripts or files (such as login_creds.sh)
  are available and properly configured.
- Execute the script in a Bash environment, providing necessary
  permissions if required

.

**Conclusion:**

The curl.sh script serves as a valuable tool for automating the testing of API endpoints, enabling developers to rapidly verify the correctness and stability of their web services. By systematically exercising various functionalities and scenarios, automated testing helps identify bugs, regressions, and performance issues early in the development lifecycle, contributing to overall software quality and reliability.
<img class="center" src={CLITest} width="300">
