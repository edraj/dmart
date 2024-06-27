<script>
    import Python from "./assets/python.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 44%;
}
</style>
<img class="center" src={Python} width="500">

### **Python Client Library for DMART**

---

**Pydmart**

This is a Python Dmart client used to interact with a Dmart instance

**Installation**

Pydmart is distributed via PyPI:

pip install pydmart

**Example**

Just simple steps and you will be ready to interact with your Dmart instance

1.  instantiate an object `d_client = DmartService({dmart_instance_url}, {username}, {password})`
2.  connect the client to the Dmart instance and authenticate your user `await d_client.connect()`

then you will be able to retrieve your profile as simple as await d_client.get_profile()

**Link**

> [https://pypi.org/project/pydmart/](https://pypi.org/project/pydmart/)
