import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from notion_client import Client
from notion_client.errors import APIResponseError


class NotionService:
    def __init__(self):
        self.token = os.getenv("NOTION_INTEGRATION_TOKEN") or os.getenv("NOTION_API_KEY")
        self.course_db_id = os.getenv("NOTION_COURSE_DATABASE_ID") or os.getenv("NOTION_COURSE_DB_ID")
        self.homework_db_id = os.getenv("NOTION_HOMEWORK_DATABASE_ID") or os.getenv("NOTION_CALENDAR_DB_ID")

        # Allow custom property names when database schema differs.
        self.course_relation_property = os.getenv("NOTION_HOMEWORK_COURSE_RELATION_PROPERTY", "相關課程")
        self.homework_name_property = os.getenv("NOTION_HOMEWORK_NAME_PROPERTY", "Name")
        self.homework_tags_property = os.getenv("NOTION_HOMEWORK_TAGS_PROPERTY", "tags")
        self.homework_date_property = os.getenv("NOTION_HOMEWORK_DATE_PROPERTY", "準備時間")
        self.homework_status_property = os.getenv("NOTION_HOMEWORK_STATUS_PROPERTY", "tag")
        self.homework_files_property = os.getenv("NOTION_HOMEWORK_FILES_PROPERTY", "files")

        if not self.token or not self.course_db_id or not self.homework_db_id:
            missing = []
            if not self.token:
                missing.append("NOTION_INTEGRATION_TOKEN")
            if not self.course_db_id:
                missing.append("NOTION_COURSE_DATABASE_ID")
            if not self.homework_db_id:
                missing.append("NOTION_HOMEWORK_DATABASE_ID")
            raise ValueError(f"Missing Notion configuration: {', '.join(missing)}")

        self.client = Client(auth=self.token)
        self.course_data_source_id = self._resolve_data_source_id(self.course_db_id)
        self.homework_data_source_id = self._resolve_data_source_id(self.homework_db_id)
        self.course_name_property = self._detect_course_name_property()
        self.homework_property_types = self._load_homework_property_types()
        self._align_homework_property_names()

    def _resolve_data_source_id(self, database_id: str) -> Optional[str]:
        db = self.client.databases.retrieve(database_id=database_id)
        data_sources = db.get("data_sources", [])
        if data_sources:
            return data_sources[0].get("id")
        return None

    def _detect_course_name_property(self) -> str:
        # Highest priority: explicit override for non-standard schema.
        override = (
            os.getenv("NOTION_COURSE_NAME_PROPERTY")
            or os.getenv("NOTION_COURSE_TITLE_PROPERTY")
        )
        if self.course_data_source_id:
            ds = self.client.data_sources.retrieve(data_source_id=self.course_data_source_id)
            props = ds.get("properties", {})
        else:
            db = self.client.databases.retrieve(database_id=self.course_db_id)
            props = db.get("properties", {})

        if override:
            if override in props:
                return override
            raise ValueError(f"Course property '{override}' not found in course database.")

        for prop_name, schema in props.items():
            if schema.get("type") == "title":
                return prop_name

        # Fallback for non-title naming columns in customized schema.
        for prop_name, schema in props.items():
            if schema.get("type") in {"rich_text", "select", "status", "formula"}:
                return prop_name

        raise ValueError(
            "Unable to detect a usable course name property. "
            "Please set NOTION_COURSE_NAME_PROPERTY in .env."
        )

    def _load_homework_property_types(self) -> Dict[str, str]:
        if self.homework_data_source_id:
            ds = self.client.data_sources.retrieve(data_source_id=self.homework_data_source_id)
            props = ds.get("properties", {})
        else:
            db = self.client.databases.retrieve(database_id=self.homework_db_id)
            props = db.get("properties", {})
        return {prop_name: schema.get("type", "") for prop_name, schema in props.items()}

    def _pick_existing_property(self, candidates: List[str], expected_type: Optional[str] = None) -> Optional[str]:
        for name in candidates:
            if name in self.homework_property_types:
                if expected_type is None or self.homework_property_types.get(name) == expected_type:
                    return name
        return None

    def _align_homework_property_names(self) -> None:
        # Resolve real property names from schema to avoid strict naming mismatches.
        self.homework_name_property = self._pick_existing_property(
            [self.homework_name_property, "Name", "name"],
            expected_type="title",
        ) or self.homework_name_property
        self.homework_tags_property = self._pick_existing_property(
            [self.homework_tags_property, "Tags", "tags", "Tag"],
        ) or self.homework_tags_property
        self.homework_date_property = self._pick_existing_property(
            [self.homework_date_property, "準備時間", "Due Date", "date"],
            expected_type="date",
        ) or self.homework_date_property
        self.homework_status_property = self._pick_existing_property(
            [self.homework_status_property, "status", "Status"],
        ) or self.homework_status_property
        self.homework_files_property = self._pick_existing_property(
            [self.homework_files_property, "files", "Files", "附件"],
            expected_type="files",
        ) or self.homework_files_property

    def _query_rows(self, *, database_id: str, data_source_id: Optional[str], **kwargs) -> Dict[str, Any]:
        if data_source_id:
            return self.client.data_sources.query(
                data_source_id=data_source_id,
                **kwargs,
            )
        return self.client.databases.query(
            database_id=database_id,
            **kwargs,
        )

    @staticmethod
    def _extract_title(title_value: List[Dict[str, Any]]) -> str:
        if not title_value:
            return ""
        return "".join(part.get("plain_text", "") for part in title_value).strip()

    @staticmethod
    def _extract_property_text(prop: Dict[str, Any]) -> str:
        if not prop:
            return ""
        prop_type = prop.get("type")
        if prop_type == "title":
            return NotionService._extract_title(prop.get("title", []))
        if prop_type == "rich_text":
            return "".join(x.get("plain_text", "") for x in prop.get("rich_text", [])).strip()
        if prop_type == "select" and prop.get("select"):
            return prop["select"].get("name", "") or ""
        if prop_type == "status" and prop.get("status"):
            return prop["status"].get("name", "") or ""
        if prop_type == "formula":
            formula = prop.get("formula", {})
            if formula.get("type") == "string":
                return formula.get("string") or ""
        return ""

    @staticmethod
    def _normalize_date(raw_date: Optional[str]) -> Optional[str]:
        if not raw_date:
            return None
        try:
            return datetime.fromisoformat(raw_date).date().isoformat()
        except ValueError:
            return raw_date

    def list_courses(self) -> List[Dict[str, str]]:
        response = self._query_rows(
            database_id=self.course_db_id,
            data_source_id=self.course_data_source_id,
            page_size=100,
        )
        courses = []
        for item in response.get("results", []):
            name_obj = item.get("properties", {}).get(self.course_name_property, {})
            course_name = self._extract_property_text(name_obj)
            courses.append(
                {
                    "id": item["id"],
                    "name": course_name or "(未命名課程)",
                }
            )
        return courses

    def list_homeworks_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        if not course_id:
            raise ValueError("course_id is required")

        response = self._query_rows(
            database_id=self.homework_db_id,
            data_source_id=self.homework_data_source_id,
            filter={
                "property": self.course_relation_property,
                "relation": {
                    "contains": course_id,
                },
            },
            page_size=100,
        )

        rows: List[Dict[str, Any]] = []
        for item in response.get("results", []):
            props = item.get("properties", {})
            title_obj = props.get(self.homework_name_property, {})
            tags_obj = props.get(self.homework_tags_property, {})
            date_obj = props.get(self.homework_date_property, {})
            status_obj = props.get(self.homework_status_property, {})
            files_obj = props.get(self.homework_files_property, {})

            tags = []
            if tags_obj.get("type") == "multi_select":
                tags = [x.get("name", "") for x in tags_obj.get("multi_select", []) if x.get("name")]
            elif tags_obj.get("type") == "select" and tags_obj.get("select"):
                tags = [tags_obj["select"].get("name", "")]

            status = None
            if status_obj.get("type") == "status" and status_obj.get("status"):
                status = status_obj["status"].get("name")
            elif status_obj.get("type") == "select" and status_obj.get("select"):
                status = status_obj["select"].get("name")

            date_value = date_obj.get("date", {}) if date_obj else {}
            rows.append(
                {
                    "id": item["id"],
                    "name": self._extract_title(title_obj.get("title", [])),
                    "tags": tags,
                    "date": self._normalize_date((date_value or {}).get("start")),
                    "status": status,
                    "files": files_obj.get("files", []) if files_obj.get("type") == "files" else [],
                    "url": item.get("url"),
                }
            )
        return rows

    def create_homework(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        course_id = payload.get("course_id")
        name = (payload.get("name") or "").strip()
        due_date = payload.get("due_date")
        tags = payload.get("tags", [])
        status = payload.get("status")
        file_url = payload.get("file_url")
        file_name = payload.get("file_name")

        if not course_id:
            raise ValueError("course_id is required")
        if not name:
            raise ValueError("name is required")

        if isinstance(tags, str):
            raw = tags.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        tags = [str(t).strip() for t in parsed if str(t).strip()]
                    else:
                        tags = [raw]
                except json.JSONDecodeError:
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
            else:
                tags = [t.strip() for t in tags.split(",") if t.strip()]
        if not isinstance(tags, list):
            raise ValueError("tags must be a list or comma-separated string")

        properties: Dict[str, Any] = {
            self.homework_name_property: {"title": [{"text": {"content": name}}]},
            self.course_relation_property: {"relation": [{"id": course_id}]},
        }

        if due_date:
            properties[self.homework_date_property] = {"date": {"start": due_date}}

        if tags and self.homework_tags_property in self.homework_property_types:
            tags_type = self.homework_property_types.get(self.homework_tags_property)
            if tags_type == "select":
                properties[self.homework_tags_property] = {"select": {"name": tags[0]}}
            else:
                properties[self.homework_tags_property] = {"multi_select": [{"name": t} for t in tags]}

        if status and self.homework_status_property in self.homework_property_types:
            status_type = self.homework_property_types.get(self.homework_status_property)
            if status_type == "select":
                properties[self.homework_status_property] = {"select": {"name": status}}
            else:
                properties[self.homework_status_property] = {"status": {"name": status}}

        if file_url and self.homework_files_property in self.homework_property_types:
            properties[self.homework_files_property] = {
                "files": [
                    {
                        "name": file_name or "homework.pdf",
                        "external": {"url": file_url},
                    }
                ]
            }

        parent = {"database_id": self.homework_db_id}
        if self.homework_data_source_id:
            parent = {"data_source_id": self.homework_data_source_id}

        page = self.client.pages.create(parent=parent, properties=properties)

        return {
            "id": page["id"],
            "url": page.get("url"),
        }

    def attach_homework_file(self, homework_page_id: str, file_url: str, file_name: str) -> Dict[str, Any]:
        if not homework_page_id:
            raise ValueError("homework_page_id is required")
        if not file_url:
            raise ValueError("file_url is required")

        if self.homework_files_property not in self.homework_property_types:
            raise ValueError(f"Files property '{self.homework_files_property}' does not exist in homework database.")

        page = self.client.pages.retrieve(page_id=homework_page_id)
        props = page.get("properties", {})
        files_obj = props.get(self.homework_files_property, {})
        existing_files = files_obj.get("files", []) if files_obj.get("type") == "files" else []

        updated_files = list(existing_files)
        updated_files.append(
            {
                "name": file_name or "homework.pdf",
                "external": {"url": file_url},
            }
        )

        updated_page = self.client.pages.update(
            page_id=homework_page_id,
            properties={
                self.homework_files_property: {
                    "files": updated_files,
                }
            },
        )
        return {
            "id": updated_page["id"],
            "url": updated_page.get("url"),
        }

    @staticmethod
    def format_api_error(error: Exception) -> str:
        if isinstance(error, APIResponseError):
            return f"Notion API error ({error.code}): {str(error)}"
        return str(error)
