<script>
  import Permission from "./assets/create_permission.png";
  import Role from "./assets/create_role.png";
  import Schema from "./assets/create_schema.png";
  import User from "./assets/create_user.png";
  import AdminUI1 from "./assets/admin_ui_1.png";
  import AdminUI2 from "./assets/admin_ui_2.png";
  import Entry from "./assets/create_entry.png";
</script>

<style>
  .center {
    display: block;
    margin-left: auto;
    margin-right: auto;
    width: 50%;
  }
</style>

### **أداة إدارة النظام الرسومية (GUI)**

---

**مقدمة**

أداة إدارة النظام الرسومية (GUI) هي واجهة إدارة قوية مصممة لتسهيل إدارة الإدخالات داخل النظام. إنها توفر لمسؤولي النظام القدرة على عرض وتحديث وحذف الإدخالات بناءً على دورهم والأذونات المرتبطة بهم. تعمل هذه الأداة كمنصة مركزية للوصول إلى البيانات والتلاعب بها، على غرار التفاعل مع قاعدة البيانات. لدى DMART واجهة إدارة شاملة تتفاعل مع الخلفية بالكامل عبر واجهة برمجة تطبيقات رسمية. وهي مبنية باستخدام Svelte و Routify3 و SvelteStrap.

```bash
cd dmart/frontend
yarn install

# تكوين عنوان URL الخلفي لخادم DMART في src/config.ts

# للتشغيل في وضع التطوير
yarn dev

# للبناء والتشغيل في وضع الإنتاج / وضع تقديم الملفات الثابتة (أي بدون nodejs) باستخدام Caddy
yarn build
caddy run
```
