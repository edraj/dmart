<script>
  import {QueryType} from "@/dmart";
  import ListView from "@/components/management/ListView.svelte";
  import Tree from "./assets/tree.png"
</script>

### أمثلة

---

_في هذا المثال سوف نستخدم تلك السمات_
`space = dmart_data`
`subpath= content`
`schema = product`.

1. **تحديد المخطط (النموذج) الخاص بك**

لنفترض أننا بحاجة إلى تحديد نموذج المنتج باستخدام الحقول التالية:

- عنوان
- وصف
- سعر
- فئة
- صورة

باستخدام JSON هكذا سيكون مخططنا:

```json

{
  "title": "Product",
  "additionalProperties": false,
  "type": "object",
  "properties": {
    "title": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "price": {
      "type": "number"
    },
    "category": {
      "type": "string"
    },
    "image": {
      "type": "string"
    }
  }
}
```

_يرجى ملاحظة أنه يجب إنشاء جميع المخططات ضمن المسار الفرعي `schema`_

2. **إنشاء إدخال**

حدد الموقع وبيانات التعريف وبيانات الحمولة (بيانات المنتج الفعلية).

```json
{
    "space_name": "dmart_data",
    "request_type": "create",، // تم شرحه في المفاهيم -> أنواع الطلبات
    "records": [ // يقبل قائمة السجلات التي سيتم إنشاؤها
        {
            "resource_type": "content",  // تم شرحه في المفاهيم -> أنواع الموارد
            "subpath": "products",
            "shortname": "auto",  // auto هي كلمة سحرية تطلب من النظام إنشاء اسم قصير فريد
            "attributes": {
                "is_active": true, // بيانات التعريف
                "tags": ["red", "awesome"], // بيانات التعريف

                "payload": {
                    "content_type": "json",  // موضح في المفاهيم -> أنواع المحتوى
                    "schema_shortname": "product", // الاسم المختصر للمخطط الذي تم إنشاؤه
                    // قيم سمات المنتج
                    "body": {
                        "title": "Iphone 14",
                        "description": "Red, 128GB",
                        "price": 799.99,
                        "category": "Mobile Phones",
                        "image": "https://dmart.com/media/iphone-14-red"
                    }
                }
            }
        }
    ]
}
```

الآن يسترد النظام المخطط الذي قدمته في `attributes.payload.schema_shortname` من نفس المساحة والمسار الفرعي `المخطط`، ويتحقق من صحة `attributes.payload.body` مقابله،
إذا كان صالحًا، يقوم النظام بتخزين الإدخال ضمن `dmart_data/products`.

3. **بحث**

يمكنك الآن إجراء بحث في كامل النص أو بحث يعتمد على سمات هذا الحقل.
على سبيل المثال، لنفترض أننا نريد استرداد كافة المجلدات الفرعية ضمن مساحة **mysapce**
نحن نسمي واجهة برمجة التطبيقات `/query` بنص الطلب التالي

```json
{
  "filter_shortnames": [],
  "type": "subpath",
  "search": "",
  "space_name": "myspace",
  "subpath": "/",
  "exact_subpath": true,
  "limit": 15,
  "offset": 0,
  "retrieve_json_payload": true,
  "sort_type": "ascending",
  "sort_by": "created_at"
}
```

وستكون النتائج:

<ListView
type={QueryType.subpath}
space_name={"myspace"}
subpath={"/"}
is_clickable={false}
scope={"public"}
/>

