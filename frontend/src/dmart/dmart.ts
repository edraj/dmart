import axios from 'axios';

enum Status {
  success = "success",
  failed = "failed"
};

type Error = {
  type: string,
  code: number,
  message: string,
  info: any

};

type ApiResponseRecord = {
  resource_type: string,
  shortname: string,
  branch_name: string,
  subpath: string,
  attributes: Record<string, any>
};

type ApiResponse = {
  status: Status,
  error: Error,
  records: Array<ApiResponseRecord>
};

type Translation = {
  "ar": string,
  "en": string,
  "kd": string
};

enum UserType {
  web = "web",
  mobile = "mobile",
  bot = "bot"
};

type LoginResponseRecord = ApiResponseRecord & {
  attributes: {
    access_token: string,
    type: UserType,
    displayname: Translation
  }
};

// type LoginResponse = ApiResponse  & { records : Array<LoginResponseRecord> };


type Permission = {
  allowed_actions: Array<ActionType>,
  conditions: Array<string>,
  restricted_fields: Array<any>,
  allowed_fields_values: Map<string, any> 
};

enum Language {
  arabic = "arabic",
  english = "engligh", 
  kurdish = "kurdish",
  french = "french",
  turkish = "turkish"
};

type ProfileResponseRecord = ApiResponseRecord & {
  attributes: {
    email: string,
    displayname: Translation,
    type: string,
    language: Language,
    is_email_verified: boolean,
    is_msisdn_verified: boolean,
    force_password_change: boolean,
    permissions: Record<string, Permission>

  }
};

enum ActionType {
    query = "query",
    view = "view",
    update = "update",
    create = "create",
    delete = "delete",
    attach = "attach",
    move = "move",
    progress_ticket = "progress_ticket"
};

type ProfileResponse = ApiResponse & {
  records: Array<ProfileResponseRecord>
}

const api_url = "https://api.dmart.cc";

let headers: { [key: string]: string } = {
  "Content-type": "application/json",
  //"Authorization": ""
};


export enum QueryType {
    search = "search",
    subpath = "subpath",
    events = "events",
    history = "history",
    tags = "tags",
    spaces = "spaces",
    counters = "counters",
    reports = "reports"
};

enum SortyType {
    ascending = "ascending",
    descending = "descending"
};

// enum NotificationPriority {
//   high = "high",
//   medium = "medium",
//   low = "low"
// };

type QueryRequest = {
  type: QueryType,
  space_name: string,
  subpath: string,
  filter_types?: Array<string>,
  filter_schema_names?: Array<string>,
  filter_shortnames?: Array<string>,
  search: string,
  from_date?: string,
  to_date?: string,
  sort_by?: string,
  sort_type?: SortyType,
  retrieve_json_payload?: boolean,
  retrieve_attachments?: boolean,
  validate_schema?: boolean,
  jq_filter?: string,
  limit?: number,
  offset?: number
};

export enum RequestType {
  create = "create",
  update = "update",
  replace = "replace",
  delete = "delete",
  move = "move"
};


enum ResourceType {
    user = "user",
    group = "group",
    folder = "folder",
    schema = "schema",
    content = "content",
    acl = "acl",
    comment = "comment",
    media = "media",
    locator = "locator",
    relationship = "relationship",
    alteration = "alteration",
    history = "history",
    space = "space",
    branch = "branch",
    permission = "permission",
    role = "role",
    ticket = "ticket",
    json = "json",
    plugin_wrapper = "plugin_wrapper",
    notification = "notification",
};


enum ContentType {
    text = "text",
    markdown = "markdown",
    json = "json",
    image = "image",
    python = "python",
    pdf = "pdf",
    audio = "audio"
};

type Payload = {
  content_type: ContentType,
  schema_shortname: string,
  checksum: string, 
  body: string | Record<string, any>,
  last_validated: string,
  validation_status: "valid" |  "invalid"

};

type ResponseRecord = {
  resource_type: ResourceType,
  uuid: string,
  shortname: string,
  subpath: string,
  attributes: {
    is_active: boolean, 
    displayname: Translation,
    description: Translation,
    tags: Set<string>,
    created_at: string,
    updated_at: string,
    owner_shortname: string,
    payload: Payload
  }
};

type ActionResponse = {
  records: Array<ResponseRecord & {attachments: { media: Array<ResponseRecord>, json: Array<ResponseRecord> }}>
};

type ActionRequestRecord = {
  resource_type: ResourceType,
  uuid: string,
  shortname: string,
  subpath: string,
  attributes: Record<string, any>,
  attachments: Record<ResourceType, Array<any>>

};

type ActionRequest = {
  space_name: string,
  request_type: RequestType,
  records: Array<ActionRequestRecord>
};

export async function login(shortname: string, password: string) {
  const { data } = await axios.post<ApiResponse  & { records : Array<LoginResponseRecord> }>( api_url + "/user/login", {shortname, password}, {headers});
  //console.log(JSON.stringify(data, null, 2));
  // FIXME settins Authorization is only needed when the code is running on the server
  headers.Authorization = "";
  if (data.status == Status.success && data.records.length > 0) {
    headers.Authorization = "Bearer " + data.records[0].attributes.access_token;
  }
  return data;
}

export async function logout() {
  const { data } = await axios.post<ApiResponse>( api_url + "/user/logout", {}, {headers});
  return data;
};

export async function getProfile() {
  const { data } = await axios.get<ProfileResponse>(
    api_url + "/user/profile", { headers}
  );
  return data;

};
export async function query(query: QueryRequest) : Promise<ApiResponse> {
  const { data } = await axios.post<ApiResponse & {attributes: {total: number, returned: number}}>( api_url + "/managed/query", query, {headers});
  return data;
};

export async function request(action: ActionRequest) {
  const { data } = await axios.post<ActionResponse>( api_url + "/managed/request", action, {headers});
  return data;
};

