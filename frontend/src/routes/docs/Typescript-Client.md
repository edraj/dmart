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

### **TypeScript Client Library for DMART**

---

A TypeScript implementation of the Dmart that depends on axios.

#### **APIs**

- `login(shortname: string, password: string) -> Promise<ApiResponse>` - Performs a login action.
- `logout() -> Promise<ApiResponse>` - Performs a logout action.
- `create_user(request: any) -> Promise<ActionResponse>` - Creates a new user.
- `update_user(request: any) -> Promise<ActionResponse>` - Updates an existing user.
- `check_existing(prop: string, value: string) -> Promise<ResponseEntry | null>` - Checks if a user exists.
- `get_profile() -> Promise<ProfileResponse | null>` - Gets the profile of the current user.

- `query(query: QueryRequest) -> Promise<ApiQueryResponse | null>` - Performs a query action.

- `csv(query: any) -> Promise<ApiQueryResponse>` - Queries the entries as a CSV file.

- `space(action: ActionRequest) -> Promise<ActionResponse>` - Performs actions on spaces.

- `request(action: ActionRequest) -> Promise<ActionResponse>` - Performs a request action.

- `retrieve_entry(resource_type: ResourceType, space_name: string, subpath: string, shortname: string, retrieve_json_payload: boolean = false, retrieve_attachments: boolean = false, validate_schema: boolean = true) -> Promise<ResponseEntry|null>` - Performs a retrieve action.

- `upload_with_payload(space_name: string, subpath: string, shortname: string, resource_type: ResourceType, payload_file: File, content_type?: ContentType, schema_shortname?: string) -> Promise<ApiResponse>` - Uploads a file with a payload.

- `fetchDataAsset(resourceType: string, dataAssetType: string, spaceName: string, subpath: string, shortname: string, query_string?: string, filter_data_assets?: string[], branch_name?: string) -> Promise<any>` - Fetches a data asset.

- `get_spaces() -> Promise<ApiResponse | null>` - Gets the spaces (user query).

- `get_children(space_name: string, subpath: string, limit: number = 20, offset: number = 0, restrict_types: Array<ResourceType> = []) -> Promise<ApiResponse | null>` - Gets the children of a space (user query).

- `get_attachment_url(resource_type: ResourceType, space_name: string, subpath: string, parent_shortname: string, shortname: string, ext: string) -> string` - Constructs the URL of an attachment.

- `get_space_health(space_name: string) -> Promise<ApiQueryResponse & { attributes: { folders_report: Object } }>` - Gets the health check of a space.

- `get_attachment_content(resource_type: string, space_name: string, subpath: string, shortname: string) -> Promise<any>` - Gets the content of an attachment.

- `get_payload(resource_type: string, space_name: string, subpath: string, shortname: string, ext: string = ".json") -> Promise<any>` - Gets the payload of a resource.

- `get_payload_content(resource_type: string, space_name: string, subpath: string, shortname: string, ext: string = ".json") -> Promise<any>` - Gets the content of a payload.

- `progress_ticket(space_name: string, subpath: string, shortname: string, action: string, resolution?: string, comment?: string) -> Promise<ApiQueryResponse & { attributes: { folders_report: Object } }>` - Performs a progress ticket action.

- `submit(spaceName: string, schemaShortname: string, subpath: string, record: any) -> Promise<any>` - Submits a record (log/feedback) to DMART.

- `get_manifest() -> Promise<any>` - Gets the manifest of the current instance.

- `get_settings() -> Promise<any>` - Gets the settings of the current instance.

**Link**:

> [https://github.com/edraj/tsdmart](https://github.com/edraj/tsdmart)
