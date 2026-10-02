from datetime import datetime, timezone

from app.config import settings
from app.importers.limits import ImportItemError
from app.importers.base import Importer
from app.importers.canonical import (
    CanonicalItem,
    CanonicalMessage,
    ConversationPayload,
    SourceProvider,
)
from app.importers.sources import ChatGPTSource


class ChatGPTImporter(Importer[ChatGPTSource]):
    def import_data(
        self,
        source: ChatGPTSource,
    ) -> list[CanonicalItem]:
        return [
            self.import_conversation(conversation)
            for conversation in source.conversations
        ]

    def import_conversation(
        self,
        conversation: dict,
    ) -> CanonicalItem:
        if not isinstance(conversation, dict):
            raise ImportItemError("INVALID_ITEM", "Conversation must be an object")
        external_id = conversation.get("conversation_id") or conversation.get("id")
        if not isinstance(external_id, str) or not external_id.strip() or len(external_id) > 255:
            raise ImportItemError("INVALID_ID", "Conversation needs a valid source identifier")
        title = conversation.get("title") or "Untitled"
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 255:
            raise ImportItemError("INVALID_TITLE", "Conversation title must be 1–255 characters")
        messages = self._extract_active_branch(
            conversation,
        )

        if not messages:
            raise ImportItemError("EMPTY_CONVERSATION", "No supported text messages on the active branch")
        return CanonicalItem(
            provider=SourceProvider.CHATGPT,
            external_id=external_id,
            title=title.strip(),
            source_updated_at=self._to_datetime(conversation.get("update_time")),
            locator=f"https://chatgpt.com/c/{external_id}",
            parser_version="chatgpt-active-text-v1",
            completeness="complete",
            event_at=self._to_datetime(
                conversation.get("create_time")
            ),
            payload=ConversationPayload(
                messages=messages,
            ),
        )

    def _extract_active_branch(
        self,
        conversation: dict,
    ) -> list[CanonicalMessage]:
        mapping = conversation.get("mapping", {})
        current_node = conversation.get("current_node")

        if not isinstance(mapping, dict):
            raise ImportItemError("INVALID_GRAPH", "Conversation message mapping must be an object")
        if len(mapping) > settings.import_max_nodes_per_item:
            raise ImportItemError("ITEM_LIMIT", "Conversation exceeds the message-node limit")
        visited: set[str] = set()
        nodes: list[dict] = []

        while current_node is not None:
            if not isinstance(current_node, str) or current_node in visited:
                raise ImportItemError("INVALID_GRAPH", "Conversation branch contains an invalid or cyclic link")
            visited.add(current_node)
            node = mapping.get(current_node)

            if not isinstance(node, dict):
                raise ImportItemError("INVALID_GRAPH", "Conversation branch references a missing or invalid node")

            nodes.append(node)
            current_node = node.get("parent")

        nodes.reverse()

        messages: list[CanonicalMessage] = []

        for node in nodes:
            message = node.get("message")

            if message is None:
                continue

            author = message.get("author") or {}
            role = author.get("role")

            if role not in {"user", "assistant"}:
                continue

            content = message.get("content") or {}
            parts = content.get("parts") or []

            text_parts = [
                part
                for part in parts
                if isinstance(part, str) and part.strip()
            ]

            if not text_parts:
                continue

            messages.append(
                CanonicalMessage(
                    role=role,
                    message_id=message.get("id") or node.get("id"),
                    content="\n".join(text_parts),
                    created_at=self._to_datetime(
                        message.get("create_time")
                    ),
                )
            )

        return messages

    def _to_datetime(
        self,
        timestamp: float | int | None,
    ) -> datetime | None:
        if timestamp is None:
            return None

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )
