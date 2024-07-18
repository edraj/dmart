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

## **الاختبار الآلي باستخدام Pytest**

---

**مقدمة**

يعد الاختبار الآلي جانبًا مهمًا في تطوير البرامج، مما يضمن أن التغييرات في التعليمات البرمجية لا تؤدي عن غير قصد إلى ظهور أخطاء أو تراجعات. Pytest هو إطار اختبار واسع الاستخدام لـ Python يسمح للمطورين بكتابة اختبارات بسيطة وقابلة للتطوير. توفر هذه الوثائق إرشادات وأمثلة للاختبار الآلي باستخدام Pytest في سياق تطبيق FastAPI.

**اعداد**

قبل كتابة الاختبارات، تأكد من تكوين بيئتك بشكل صحيح للاختبار. سوف تحتاج:

- بيئة بايثون مع تثبيت Pytest

- تطبيق FastAPI مع نقاط النهاية المناسبة

- اختبار العميل لإجراء طلبات HTTP لتطبيق FastAPI

- تكوينات Redis ومدير المكونات الإضافية (إن أمكن)

**كتابة الاختبارات**

يتبع Pytest بناء جملة بسيطًا لكتابة الاختبارات، باستخدام وظائف مسبوقة بـ `test_`. تحتوي هذه الوظائف على تأكيدات تتحقق من السلوك المتوقع للتعليمات البرمجية الخاصة بك.

**مثال على بنية ملف الاختبار**

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


**مثال عن وظائف الاختبار**

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

**اختبار الإعداد والتفكيك**

يسمح لك Pytest بتحديد وظائف الإعداد والتفكيك باستخدام التركيبات. تعمل هذه الوظائف قبل وبعد كل وظيفة اختبار، على التوالي.

```python

import pytest

@pytest.fixture(autouse=True)
def setup():
    # منطق الإعداد هنا ...
    yield
    #منطق التدمير هنا...
```

**أمثلة على وظائف التأكيد**

يوفر Pytest وظائف تأكيد مختلفة للتحقق من صحة نتائج الاختبار. تتضمن بعض التأكيدات الشائعة ما يلي:

- `assert response.status_code == 200`: التحقق من رمز حالة HTTP

- `assert response.json()['status'] == 'success'` التحقق من سمات استجابة جيسون

- `assert 'error' not in response.json()`: تحقق من عدم وجود أخطاء

**اختبارات التشغيل**

لإجراء الاختبارات باستخدام Pytest، انتقل إلى الدليل الذي يحتوي على ملفات الاختبار الخاصة بك وقم بتشغيل الأمر التالي:

```bash
pytest
```

سوف يكتشف Pytest تلقائيًا جميع وظائف الاختبار وينفذها داخل الدليل.

<img class="center" src={PYTest} width="450">