## تعليمات التثبيت والإعداد

---

**الحاوية (موصى به)**

باستخدام podman (أو docker) ، يمكن إعداد dmart وتكوينه بالكامل في غضون دقائق قليلة.

كل ما تحتاجه هو وحدة تحكم سطر الأوامر ، git و podman (أو docker).

**الخطوات**

```
# استنساخ مستودع git
git clone https://github.com/edraj/dmart.git
cd dmart/admin_scripts/docker

# بناء الحاوية
podman build -t dmart -f Dockerfile

# تشغيل الحاوية
podman run --name dmart -p 8000:8000 -d -it dmart

# تعيين كلمة مرور المسؤول
podman exec -it -w /home/backend dmart /home/venv/bin/python3 ./set_admin_passwd.py

# تحميل بيانات مساحات العينة
podman exec -it -w /home/backend dmart bash -c 'source /home/venv/bin/activate && ./reload.sh'

# تشغيل الاختبارات التلقائية
podman exec -it -w /home/backend dmart ./curl.sh

# افتح المتصفح لتسجيل الدخول إلى أداة المسؤول وانقر فوق تسجيل الدخول.
# اسم المستخدم: dmart
# كلمة المرور: كلمة المرور التي أدخلتها في خطوة set_admin_passwd أعلاه.
# الرابط: http://localhost:8000

```

**التثبيت اليدوي (للمستخدمين المتقدمين)**

**المتطلبات**

- git
- jq
- python >= 3.11
- pip
- redis >= 7.2
- RedisJSON (rejson) >= 2.6
- RediSearch >= 2.8
- python venv

**الخطوات**

```bash

# تمكين kefahi dnf من copr لتنزيل وحدات redis
sudo dnf copr enable kefah/RediSearch

# تنزيل حزم النظام الضرورية
sudo dnf install jq redis rejson redisearch python3-pip python3
echo 'loadmodule /usr/lib64/redis/modules/librejson.so
loadmodule /usr/lib64/redis/modules/redisearch.so' | sudo tee -a /etc/redis/redis.conf
sudo systemctl start redis


git clone https://github.com/edraj/dmart.git

cd dmart

# إنشاء مجلد السجلات
mkdir logs

# نسخ هيكل مساحات العينة
cp -a sample/spaces ../


cd backend

# إنشاء البيئة الافتراضية
python -m venv env

# تفعيل البيئة الافتراضية
source env/bin/activate

# تثبيت وحدات بايثون
pip install --user -r requirements.txt

# اختياريًا ، اضبط تكوينك
cp config.env.sample config.env

# تعيين كلمة مرور المسؤول
./set_admin_passwd.py

# بدء تشغيل خدمة DMART المجهرية
./main.py


# اختياريًا: التحقق من مجلد المسؤول لسكريبتات systemd

```