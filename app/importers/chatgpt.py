from datetime import datetime, timezone

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
        messages = self._extract_active_branch(
            conversation,
        )

        return CanonicalItem(
            provider=SourceProvider.CHATGPT,
            external_id=conversation.get("conversation_id"),
            title=conversation.get("title") or "Untitled",
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

        nodes: list[dict] = []

        while current_node is not None:
            node = mapping.get(current_node)

            if node is None:
                break

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
