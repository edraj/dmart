<script>
    import TypeScript from "./assets/ts.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

<img class="center" src={TypeScript} width="500">

### **مكتبة عملاء TypeScript لـ DMART**

---

تنفيذ TypeScript لـ Dmart يعتمد على axios.

#### **واجهات برمجة التطبيقات (APIs)**

- `login(shortname: string, password: string) -> Promise<ApiResponse>` - يقوم بعملية تسجيل دخول.
- `logout() -> Promise<ApiResponse>` - يقوم بعملية تسجيل خروج.
- `create_user(request: any) -> Promise<ActionResponse>` - إنشاء مستخدم جديد.
- `update_user(request: any) -> Promise<ActionResponse>` - تحديث مستخدم موجود.
- `check_existing(prop: string, value: string) -> Promise<ResponseEntry | null>` - التحقق من وجود مستخدم.
- `get_profile() -> Promise<ProfileResponse | null>` - الحصول على ملف تعريف المستخدم الحالي.

- `query(query: QueryRequest) -> Promise<ApiQueryResponse | null>` - إجراء استعلام.

- `csv(query: any) -> Promise<ApiQueryResponse>` - استعلام الإدخالات كملف CSV.

- `space(action: ActionRequest) -> Promise<ActionResponse>` - إجراء عمليات على المساحات.

- `request(action: ActionRequest) -> Promise<ActionResponse>` - إجراء طلب.

- `retrieve_entry(resource_type: ResourceType, space_name: string, subpath: string, shortname: string, retrieve_json_payload: boolean = false, retrieve_attachments: boolean = false, validate_schema: boolean = true) -> Promise<ResponseEntry|null>` - تنفيذ إجراء استرداد.

- `upload_with_payload(space_name: string, subpath: string, shortname: string, resource_type: ResourceType, payload_file: File, content_type?: ContentType, schema_shortname?: string) -> Promise<ApiResponse>` - تحميل ملف مع حمولة.

- `fetchDataAsset(resourceType: string, dataAssetType: string, spaceName: string, subpath: string, shortname: string, query_string?: string, filter_data_assets?: string[], branch_name?: string) -> Promise<any>` - جلب أحد أصول البيانات.

- `get_spaces() -> Promise<ApiResponse | null>` - الحصول على المساحات (استعلام المستخدم).

- `get_children(space_name: string, subpath: string, limit: number = 20, offset: number = 0, restrict_types: Array<ResourceType> = []) -> Promise<ApiResponse | null>` - الحصول على عناصر فرعية لمساحة (استعلام المستخدم).

- `get_attachment_url(resource_type: ResourceType, space_name: string, subpath: string, parent_shortname: string, shortname: string, ext: string) -> string` - بناء عنوان URL للمرفق.

- `get_space_health(space_name: string) -> Promise<ApiQueryResponse & { attributes: { folders_report: Object } }>` - الحصول على فحص صحة للمساحة.

- `get_attachment_content(resource_type: string, space_name: string, subpath: string, shortname: string) -> Promise<any>` - الحصول على محتوى المرفق.

- `get_payload(resource_type: string, space_name: string, subpath: string, shortname: string, ext: string = ".json") -> Promise<any>` - الحصول على حمولة المورد.

- `get_payload_content(resource_type: string, space_name: string, subpath: string, shortname: string, ext: string = ".json") -> Promise<any>` - الحصول على محتوى الحمولة.

- `progress_ticket(space_name: string, subpath: string, shortname: string, action: string, resolution?: string, comment?: string) -> Promise<ApiQueryResponse & { attributes: { folders_report: Object } }>` - تنفيذ إجراء تذكرة تقدم.

- `submit(spaceName: string, schemaShortname: string, subpath: string, record: any`

- `get_manifest() -> Promise<any>` - يحصل على بيان المثيل الحالي.

- `get_settings() -> Promise<any>` - يحصل على إعدادات المثيل الحالي.

**مراجع**:

> [github.com/edraj/tsdmart](https://github.com/edraj/tsdmart)