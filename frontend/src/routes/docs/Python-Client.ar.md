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

### **مكتبة عميل بايثون لديمارت**

`pydmart` 
هذا هو عميل Python Dmart يُستخدم للتفاعل مع مثيل Dmart

**تثبيت**

يتم توزيع Pydmart عبر PyPI:

`pip install pydmart`

**مثال**

ما عليك سوى خطوات بسيطة وستكون جاهزًا للتفاعل مع مثيل ديمارت الخاص بك

1. إنشاء كائن `d_client = DmartService({dmart_instance_url}, {username}, {password})`
2. قم بتوصيل العميل بمثيل Dmart وقم بمصادقة المستخدم الخاص بك `في انتظار d_client.connect()`

ثم ستتمكن من استرداد ملف التعريف الخاص بك بهذه البساطة في انتظار d_client.get_profile()

**وصلة**
> [https://pypi.org/project/pydmart/](https://pypi.org/project/pydmart/)
