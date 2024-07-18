<script>
    import Flutter from "./assets/flutter.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

<img class="center" src={Flutter} width="500">

**عميل دارت**

تنفيذ Dart لـديمارت  يعتمد على dio.

**واجهات برمجة التطبيقات (APIs)**

- `void initDmart({bool isDioVerbose = false})` - تهيئة مثيل شبكة Dio.

- `Future<dynamic> getManifest()` - استرداد بيان DMART.

- `Future<dynamic> getSettings()` - استرداد إعدادات DMART.

- `Future<(LoginResponse?, Error?)> login(LoginRequest loginRequest)` - مصادقة المستخدم وإرجاع معلومات تسجيل الدخول.

- `Future<(CreateUserResponse?, Error?)> createUser(CreateUserRequest createUserRequest)` - إنشاء مستخدم جديد.

- `Future<(ApiResponse?, Error?)> logout()` - تسجيل خروج المستخدم.

- `Future<(ProfileResponse?, Error?)> getProfile()` - استرداد ملف تعريف المستخدم الحالي.

- `Future<(ApiQueryResponse?, Error?)> query(QueryRequest query, {String scope = "managed"})` - تنفيذ استعلام على واجهة DMART الخلفية.

- `Future<(ActionResponse?, Error?)> request(ActionRequest action)` - تنفيذ إجراء على نظام DMART.

- `Future<(ResponseEntry?, Error?)> retrieveEntry(RetrieveEntryRequest request, {String scope = "managed"})` - جلب إدخال معين من DMART.

- `Future<(ActionResponse?, Error?)> createSpace(ActionRequest action)` - إنشاء مساحة جديدة.

- `Future<(ApiQueryResponse?, Error?)> getSpaces()` - استرداد قائمة بالمساحات.

- `Future<dynamic> getPayload(GetPayloadRequest request)` - استرداد بيانات الحمولة.

- `Future<(ApiQueryResponse?, Error?)> progressTicket(ProgressTicketRequest request)` - تحديث تذكرة تقدم.

- `Future<(Response?, Error?)> createAttachment({required String shortname, required String entitySubpath, required File payloadFile, required String spaceName, bool isActive = true, String resourceType = "media"})` - تحميل مرفق.

- `Future<(ActionResponse?, Error?)> submit(String spaceName, String schemaShortname, String subpath, Map<String, dynamic> record)` - تقديم سجل (سجل / ملاحظات) إلى DMART.

- `String getAttachmentUrl(String resourceType, String spaceName, String subpath, String parentShortname, String shortname, String ext)` - بناء عنوان URL للمرفق.

**استخدام أساسي**

**يجب دائمًا تهيئة مثيل Dmart قبل استخدامه.**

```dart

Dmart.initDmart();

// أو بوضع الإسهاب لأغراض التصحيح 

Dmart.initDmart(isDioVerbose: true);

```

**الحصول على بيانات التطبيق والإعدادات**


```dart

// جلب بيانات التطبيق الوصفية 
var (respManifests, _) = await  Dmart.getManifest();

// جلب الإعدادات 

var (respSettings, _) = await  Dmart.getSettings();

```

**إنشاء مستخدم بدور مدير**

```dart

final  CreateUserAttributes createUserAttributes = CreateUserAttributes(
displayname: Displayname(en: 'test'),
invitation: 'ABC',
password: '@Jimmy123_',
roles: ['super_admin'],
);
var (responseCreateUser, error) = await  Dmart.createUser(CreateUserRequest(
shortname: 'jimmy',
attributes: createUserAttributes,
));

```

**تسجيل دخول**

```dart

// By using shortname and password
var (responseLogin, _) = await  Dmart.login(
LoginRequest(shortname: 'jimmy', password: '@Jimmy123_'),
);
// By using email or msisdn instead of shortname
LoginRequest.withEmail
LoginRequest.withMsisdn
// By passing directly a token
Dmart.token = 'xxx.yyy.zzz';
```

**صفحة ملف المستخدم**

```dart
var (respProfile, _) = await  Dmart.getProfile();
```

**عرض كافة المساحات**

```dart
var (respSpaces, _) = await  Dmart.getSpaces();
```

**إنشاء مساحة**

```dart
ActionRequest createSpaceActionRequest = ActionRequest(
spaceName: 'my_space',
requestType: RequestType.create,
records: [
ActionRequestRecord(
resourceType: ResourceType.space,
shortname: 'my_space',
subpath: '/',
attributes: {
'displayname': {'en': 'Space'},
'shortname': 'space',
},),]);
var (respCreateSpace, _) = await  Dmart.createSpace(createSpaceActionRequest);
```

**إستعلام عن مسار فرعي في المساحة**

```dart
var (respQuery, _) = await  Dmart.query(
QueryRequest(
queryType: QueryType.subpath,
spaceName: 'management',
subpath: 'users',
retrieveJsonPayload: true,
),);
for (var record in respQuery?.records ?? []) {
print(record.shortname);
}
```

**استرجاع الإدخال**

```dart
var (respEntry, _) = await  Dmart.retrieveEntry(
RetrieveEntryRequest(
resourceType: ResourceType.user,
spaceName: 'management',
subpath: 'users',
shortname: 'jimmy',
retrieveJsonPayload: true,
));
```

**جلب حمولة الإدخال**

```dart
var (respEntryPayload, _) = await  Dmart.getPayload(GetPayloadRequest(
resourceType: ResourceType.content,
spaceName: 'myspace',
subpath: 'mysubpath',
shortname: 'myentry'
));
```

**إنشاء محتوى**


```dart
// إنشاء مجلد 
ActionRequestRecord actionRequestRecord = ActionRequestRecord(
  resourceType: ResourceType.folder,
  subpath: '/',
  shortname: 'my_subpath',
  attributes: subpathAttributes,
);
ActionRequest action = ActionRequest(
  spaceName: 'my_space',
  requestType: RequestType.create,
  records: [actionRequestRecord],
);
var (respRequestFolder, err) = await Dmart.request(action);

// إنشاء محتوى 
ActionRequestRecord actionRequestRecord = ActionRequestRecord(
    resourceType: ResourceType.content,
    subpath: 'my_subpath',
    shortname: 'my_content',
    attributes: {
        "is_active": true,
        "relationships": [],
        "payload": {
            "content_type": "json",
            "schema_shortname": null,
            "body": {
              "isAlive": true
            }
        }
    },
);
ActionRequest action = ActionRequest(
    spaceName: 'my_space',
    requestType: RequestType.create,
    records: [actionRequestRecord],
);
var (respRequestContent, err) = await Dmart.request(action);

// إنشاء مرفقات (صورة ...) 
ActionRequestRecord actionRequestRecord = ActionRequestRecord(
    resourceType: ResourceType.json,
    subpath: 'my_subpath/my_content',
    shortname: 'auto',
    attributes: {
        "is_active": true,
        "payload": {
            "content_type": "json",
            "schema_shortname": null,
            "body": {
                "attachmentName": "my attachment",
                "isImportant": "very important"
            }
        }
    },
);
ActionRequest action = ActionRequest(
    spaceName: 'my_space',
    requestType: RequestType.create,
    records: [actionRequestRecord],
);
var (respRequestAttachment, err) = await Dmart.request(action);
```

**تقدم تذكرة**

```dart
var (respProgression, _) = await  Dmart.progressTicket(
ProgressTicketRequest(
spaceName: "myspace",
subpath: "test",
shortname: "myticket",
action: "rejected",
)
);
```

**إنشاء مرفقات**

```dart

File img = File("/path/to/myimg.jpg");
var (respAttachmentCreation, _) = await  Dmart.createAttachment(
spaceName: "myspace",
entitySubpath: "mysubpath",
entityShortname: "myshortname",
attachmentShortname: "auto",
attachmentBinary: img,
);



```

**جلب رابط المرفقات**

```dart

String attachmentURL = await  Dmart.getAttachmentUrl(
spaceName: "myspace",
entitySubpath: "mysubpath",
entityShortname: "myshortname",
attachmentShortname: "myAttachment",
);
```

**إرسال مدخلة**

```dart
var (respSubmitEntry, _) = await  Dmart.submit(
"applications",
"log",
"logs",
{
"shortname": "myentry",
"resource_type": ResourceType.content.name,
"state": "awesome entry it is !"
}, );

```

**تسجيل خروج**

```dart
var (respLogout, _) = await  Dmart.logout();

```

**مراجع**:

> https://pub.dev/packages/dmart
