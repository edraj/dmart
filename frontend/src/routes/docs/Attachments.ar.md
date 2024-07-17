### المرفقات

---

تشمل المرفقات داخل Dmart أي ملف أو مستند إضافي مرتبط بكيان بيانات داخل مساحة. تعمل هذه المرفقات على إثراء البيانات المرتبطة من خلال توفير الملفات ذات الصلة مثل الصور أو المستندات أو جداول البيانات أو الوسائط المتعددة، وبالتالي تعزيز شمولية البيانات وفائدتها.

**أنواع المرفقات المدعومة في Dmart تشمل:**

- **Reaction**: يسمح للمستخدمين بإضافة ردود فعل على المنشور.
- **Share**: تسهل مشاركة المنشور.
- **JSON**: يدعم إرفاق مستندات JSON.
- **Reply**: يتيح للمستخدمين الرد على التعليق.
- **Comment**: يسمح للمستخدمين بالتعليق على منشور ما.
- **Lock**: يستخدمه النظام لقفل/فتح قفل الإدخالات.
- **Media**: يدعم إرفاق ملفات الصور.
- **Data Asset**: يدعم إرفاق ملفات JSONL وCSV وParquet وDuckDB.
- **Relationship**: إنشاء رابط لإدخال آخر.
- **Alteration**: يمكّن المستخدمين من إرسال طلبات التعديل للمراجعة والموافقة من قبل المسؤولين.

#### إنشاء مرفق

بالنسبة للمرفقات التي ليست ملفات، وهي: التفاعل والمشاركة والرد والتعليق وjson والعلاقة والتعديل، يمكنك استخدام واجهة برمجة التطبيقات /managed/request، كما يلي:

```json
{
    "space_name": "dmart_data",
    "request_type": "create",
    "records": [
        {
            "resource_type": "comment", // Must be one of the attachment types that is not file
            "shortname": "my_comment",
            "subpath": "{parent_entry_subpath}/{parent_entry_shortname}",
            "attributes": {
                "is_active": true, // Attachments have meta fields also
                "tags": ["one", "two"],
                "body": "Very Intersting entry" // The comment
            }
        }
    ]
}
```

وبالنسبة لمرفقات الملفات، وهي الوسائط و data_asset، يمكنك استخدام /managed/resource_with_payload API. فهو يقبل ثلاثة مدخلات

ملف request_record، يتكون من بيانات السجل، على سبيل المثال

```json
{
    "resource_type": "csv",
        "subpath": "asset_csv/test_csv",
        "shortname": "auto",
        "attributes": {
        "is_active": true,
        "payload": {
            "content_type": "csv",
            "schema_shortname": "users",
            "body": {}
        }
    }
}
```

الملف المرفق نفسه
اسم المساحة

> للحصول على المزيد من أمثلة واجهة برمجة التطبيقات، راجع القسم

`Managed -> Content -> Attachment`

في [Postman API collection](https://www.postman.com/galactic-desert-723527/workspace/dmart/collection/5491055-c2a1ccd1-6554-4890-b6c8-59b522983e2f)
